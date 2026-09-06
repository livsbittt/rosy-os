"""ROS-free decisions inside the slam_toolbox SaveMap call. Imports no ROS type.

The result code is the dangerous one. slam_toolbox reports success as `0`, so
the obvious `if response.result:` reads every success as a failure and every
failure as a success. The bridge has always had this right; what it has never
had is a test saying so, and the CI SaveMap guard checks the request *type*, not
the interpretation of the reply.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


class SaveMapFailed(RuntimeError):
    """slam_toolbox refused or could not complete the save."""


def check_result(code: int) -> None:
    """Raise unless slam_toolbox reported success.

    `RESULT_SUCCESS = 0`; failures are `1` (no map) and `255` (write failed).
    Zero-is-success is the inversion trap — a truthiness test here is silently
    backwards, and the failure mode is a robot that reports a saved map it never
    wrote.
    """
    if code != 0:
        raise SaveMapFailed(f"save_map service failed (result={code})")


def saved_bytes(name: str) -> Optional[bytes]:
    """The written map's content, or None if slam_toolbox wrote somewhere else.

    slam_toolbox appends `.pgm` to the name it is given, but the name may already
    carry an extension or be an absolute path, so both spellings are tried in
    that order. Returning None rather than raising is deliberate: the save itself
    already succeeded, and failing to find the file afterwards must not turn a
    good save into an error.
    """
    for candidate in (Path(f"{name}.pgm"), Path(name)):
        if candidate.is_file():
            return candidate.read_bytes()
    return None


def map_id(name: str, content: Optional[bytes], now: float) -> str:
    """D-13 map id: the name plus a short checksum of what was written.

    The id has to change when the map changes, because MAP-002 refuses a goal
    whose map id does not match the robot's. Hashing the content gives that.

    When the file cannot be found the timestamp stands in — a *distinct* id
    rather than a *stable* one. That is the right trade: a stable fallback would
    make two different maps share an id and MAP-002 would wave through a goal
    from the wrong survey. A changing id only costs a re-teach.
    """
    digest = hashlib.sha1(
        content if content is not None else f"{name}:{now}".encode()
    ).hexdigest()
    return f"{name}:{digest[:8]}"
