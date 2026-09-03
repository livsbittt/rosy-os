"""Write a namespaced Nav2 params file for launch (D-4)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from rosy_navigation.frame_prefix import apply_nav2_frame_prefix


def write_prefixed_nav2_params(
    source: str | Path,
    namespace: str,
    *,
    directory: str | Path = "/tmp",
) -> str:
    params = yaml.safe_load(Path(source).read_text(encoding="utf-8"))
    prefix = f"{namespace}/" if namespace else ""
    dest = tempfile.NamedTemporaryFile(
        prefix="rosy_nav2_params_",
        suffix=".yaml",
        dir=str(directory),
        delete=False,
        mode="w",
        encoding="utf-8",
    )
    with dest:
        yaml.safe_dump(apply_nav2_frame_prefix(params, prefix), dest)
    return dest.name
