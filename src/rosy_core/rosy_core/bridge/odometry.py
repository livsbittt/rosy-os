"""Odometry-derived geometry the bridge used to compute inline. ROS-free.

Undocking measures how far it has come with this and nothing else — no sensor
confirms it — so a wrong answer drives the robot into the dock or leaves it
short of clearance, and neither shows up in a boot smoke test.
"""

from __future__ import annotations

import math
from typing import Optional

Point = Optional[tuple[float, float]]


def travelled_m(mark: Point, current: Point) -> float:
    """Straight-line distance from the mark, or 0.0 when there is no baseline.

    Zero is the safe answer for a missing mark: the caller reads this as "not
    far enough yet" and keeps waiting, where a large number would read as
    "clear" and stop a reverse early. Straight-line is deliberate — undocking
    reverses along one axis, so path length would only add drift.
    """
    if mark is None or current is None:
        return 0.0
    return math.hypot(current[0] - mark[0], current[1] - mark[1])
