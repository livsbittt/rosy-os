"""ROS-free decisions inside the slam_toolbox SaveMap call. Imports no ROS type.

The result code is the dangerous one. slam_toolbox reports success as `0`, so
the obvious `if response.result:` reads every success as a failure and every
failure as a success. The bridge has always had this right; what it has never
had is a test saying so, and the CI SaveMap guard checks the request *type*, not
the interpretation of the reply.
"""

from __future__ import annotations


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
