"""Atomic updates to explicitly configured calibration files (no ROS dependency)."""
import math
import os
import tempfile
from pathlib import Path

import yaml


def single_calibration_path(save_path, sign_path):
    """Compatibility inputs must identify one commit, never two files."""
    if any(not isinstance(value, str) or not value.strip() for value in (save_path, sign_path)):
        raise ValueError('Calibration destination is not configured')
    destination = Path(save_path).resolve()
    if destination != Path(sign_path).resolve():
        raise ValueError('Cliff and drive calibration must use one calibration_path')
    return str(destination)


def _finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Calibration contains a non-finite value')
    if isinstance(value, dict):
        for item in value.values():
            _finite(item)
    elif isinstance(value, list):
        for item in value:
            _finite(item)


def _parameters(document):
    if not isinstance(document, dict) or not document:
        raise ValueError('Calibration must be a nonempty node mapping')
    for name, content in document.items():
        if not isinstance(name, str) or not isinstance(content, dict):
            raise ValueError('Calibration node settings must be a mapping')
        if not isinstance(content.get('ros__parameters'), dict):
            raise ValueError('Calibration parameters must be a mapping')
    _finite(document)


def merge_calibration(destination, updates):
    """Merge measured fields only; the caller selects the active generation path.

    This preserves the existing ROS parameter YAML format. Device/schema
    envelopes and activation acknowledgements remain separate migration work.
    """
    if not isinstance(destination, str) or not destination.strip():
        raise ValueError('Calibration destination is not configured')
    path = Path(destination)
    incoming = yaml.safe_load(updates)
    _parameters(incoming)
    existing = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding='utf-8'))
        _parameters(existing)
    # A bare ROS selector only matches the root namespace. Keep the file
    # device-local, but let its node settings survive a robot namespace.
    def scoped(document):
        result = {}
        for name, content in document.items():
            selector = '/**/' + name if '/' not in name else name
            if selector in result:
                raise ValueError('Ambiguous calibration node selectors')
            result[selector] = content
        return result

    existing = scoped(existing)
    incoming = scoped(incoming)
    for name, content in incoming.items():
        owner = existing.setdefault(name, {'ros__parameters': {}})
        owner['ros__parameters'].update(content['ros__parameters'])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', dir=path.parent, encoding='utf-8', delete=False) as stream:
            temporary = stream.name
            yaml.safe_dump(existing, stream, sort_keys=False, allow_unicode=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
