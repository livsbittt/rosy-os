"""Change-detection latches for the 5 Hz reconcile ticks. ROS-free.

Thin by design, and worth saying why it exists at all: the *policy* for these
two actuators already lives elsewhere — LED colour in `power.battery.resolve_led`,
LiDAR spin intent in `PowerManager`. What was left inline in `ros_bridge.py` is
the latch, and the latch carries a decision the two do not share.

**LED latches even when the call is skipped.** The service may be absent; the
LED is decoration and the tick is 5 Hz, so re-attempting the same colour five
times a second buys nothing. The cost is that a service arriving late is not
driven until the colour next changes.

**LiDAR latches only when the call goes out.** It is a navigation input, so a
driver that comes up late must be reached — not latching means the next tick
tries again, 5 Hz until it lands.

That asymmetry is deliberate (`bridge/AGENTS.md`) and was previously visible
only by reading two functions side by side and noticing that one sets its latch
inside the guard and the other outside it. Here it is a parameter with a name.
"""

from __future__ import annotations

from typing import Any, Callable


def reconcile(desired: Any, applied: Any, act: Callable[[], bool], *,
              latch_on_skip: bool) -> tuple[bool, Any]:
    """Drive `act` only when `desired` differs from `applied`.

    `act` reports whether the action actually went out — for a ROS service that
    is "the endpoint was ready". Returns `(acted, applied)`, where `applied` is
    what the caller should remember.

    With `latch_on_skip=True` a skipped action still counts as applied, so it is
    not retried. With `False` the latch is left alone and the next tick tries
    again.
    """
    if desired == applied:
        return False, applied
    acted = act()
    return acted, (desired if acted or latch_on_skip else applied)
