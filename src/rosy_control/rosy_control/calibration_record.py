"""Versioned provenance in the same atomic file as ROS parameter YAML.

The JSON comment is ignored by ROS. Consumers must validate this record before
passing parameters to ROS; the digest detects corruption, not hostile forgery.
"""
from datetime import datetime, timezone
import hashlib
import json

import yaml

HEADER = '# rosy-calibration-record: '
CONTEXT_FIELDS = {'robot_id', 'hardware_model', 'geometry_revision', 'sensor_revision', 'data_generation'}
MAX_BYTES = 1024 * 1024


def validate_context(context):
    if not isinstance(context, dict) or set(context) != CONTEXT_FIELDS:
        raise ValueError('Calibration requires complete device and generation context')
    if any(not isinstance(v, str) or not v.strip() or v != v.strip() or len(v) > 128
           for v in context.values()):
        raise ValueError('Invalid calibration context value')
    return dict(context)


def _digest(metadata, parameters):
    data = json.dumps({'metadata': metadata, 'parameters': parameters}, sort_keys=True,
                      separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def encode_record(parameters, context, actor, previous=None):
    context = validate_context(context)
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 128:
        raise ValueError('Calibration writer identity is required')
    metadata = dict(schema_version=1, context=context, actor=actor,
                    recorded_at=datetime.now(timezone.utc).isoformat(),
                    revision=previous['revision'] + 1 if previous else 1,
                    previous_digest=previous['digest'] if previous else None)
    metadata['digest'] = _digest(metadata, parameters)
    text = HEADER + json.dumps(metadata, ensure_ascii=False, separators=(',', ':')) + '\n'
    text += yaml.safe_dump(parameters, sort_keys=False, allow_unicode=True)
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Calibration record exceeds size limit')
    return text


def decode_record(text, expected_context):
    expected = validate_context(expected_context)
    if not text.startswith(HEADER) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Missing or oversized calibration record')
    header, separator, body = text.partition('\n')
    if not separator:
        raise ValueError('Calibration record has no parameters')
    metadata = json.loads(header[len(HEADER):])
    keys = {'schema_version', 'context', 'actor', 'recorded_at', 'revision', 'previous_digest', 'digest'}
    if not isinstance(metadata, dict) or set(metadata) != keys:
        raise ValueError('Invalid calibration metadata')
    if type(metadata['schema_version']) is not int or metadata['schema_version'] != 1:
        raise ValueError('Unsupported calibration schema')
    if validate_context(metadata['context']) != expected:
        raise ValueError('Calibration device, geometry, sensor or generation mismatch')
    if type(metadata['revision']) is not int or metadata['revision'] < 1:
        raise ValueError('Invalid calibration revision')
    parameters = yaml.safe_load(body)
    unsigned = {key: value for key, value in metadata.items() if key != 'digest'}
    if metadata['digest'] != _digest(unsigned, parameters):
        raise ValueError('Calibration digest mismatch')
    return metadata, parameters
