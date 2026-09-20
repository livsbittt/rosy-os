"""ROS-free motion envelope for the map_260905 live mapping runner.

Distances are measured from the robot origin by the simulated lidar.  The
policy accounts for the footprint radius before it decides that clearance is
available.  It can reduce a simulation request only; it grants no physical
speed authority.
"""

from __future__ import annotations

import math


class TraversalLimits:
    def __init__(
        self,
        *,
        robot_diameter_m: float,
        max_linear_mps: float = 0.10,
        crawl_linear_mps: float = 0.02,
        clearance_margin_m: float = 0.010,
        open_clearance_span_m: float | None = None,
        recovery_buffer_ratio: float = 0.25,
    ) -> None:
        values = (
            robot_diameter_m,
            max_linear_mps,
            crawl_linear_mps,
            clearance_margin_m,
            recovery_buffer_ratio,
        )
        if not all(math.isfinite(value) and value >= 0.0 for value in values):
            raise ValueError("traversal limits must be finite and nonnegative")
        if robot_diameter_m <= 0.0 or max_linear_mps <= 0.0:
            raise ValueError("robot diameter and maximum speed must be positive")
        if crawl_linear_mps > max_linear_mps:
            raise ValueError("crawl speed cannot exceed the maximum")
        span = (
            robot_diameter_m * 0.75
            if open_clearance_span_m is None
            else open_clearance_span_m
        )
        if not math.isfinite(span) or span <= 0.0:
            raise ValueError("open clearance span must be positive and finite")
        self.robot_diameter_m = robot_diameter_m
        self.max_linear_mps = max_linear_mps
        self.crawl_linear_mps = crawl_linear_mps
        self.clearance_margin_m = clearance_margin_m
        self.open_clearance_span_m = span
        self.recovery_buffer_ratio = recovery_buffer_ratio

    @property
    def footprint_radius_m(self) -> float:
        return self.robot_diameter_m / 2.0

    @property
    def hard_clearance_m(self) -> float:
        return self.footprint_radius_m + self.clearance_margin_m


def _clearance(value: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0.0:
        return None
    return number


def adaptive_speed(
    front_clearance_m: float,
    side_clearance_m: float,
    curvature_per_m: float,
    limits: TraversalLimits,
) -> float:
    """Return a continuous reducing-only linear cap.

    The closest front/side observation controls the clearance term.  Curvature
    can reduce that cap further but can never compensate for missing space.
    """
    front = _clearance(front_clearance_m)
    side = _clearance(side_clearance_m)
    try:
        curvature = abs(float(curvature_per_m))
    except (TypeError, ValueError):
        return 0.0
    if front is None or side is None or not math.isfinite(curvature):
        return 0.0
    available = min(front, side) - limits.hard_clearance_m
    if available <= 0.0:
        return 0.0
    fraction = min(1.0, available / limits.open_clearance_span_m)
    clearance_cap = limits.crawl_linear_mps + (
        limits.max_linear_mps - limits.crawl_linear_mps
    ) * fraction
    curvature_scale = 1.0 / (1.0 + curvature * limits.footprint_radius_m)
    return max(
        limits.crawl_linear_mps,
        min(limits.max_linear_mps, clearance_cap * curvature_scale),
    )


def recovery_reverse_distance(
    front_clearance_m: float,
    rear_clearance_m: float,
    turn_sweep_radius_m: float,
    limits: TraversalLimits,
) -> float:
    """Distance to back up before retrying a turn, derived from live space.

    The desired retreat creates a full turn-sweep clearance plus a
    footprint-scaled buffer.  Rear clearance bounds it, so there is no fixed
    8 cm command and no reverse motion when the rear safety envelope is full.
    """
    front = _clearance(front_clearance_m)
    rear = _clearance(rear_clearance_m)
    sweep = _clearance(turn_sweep_radius_m)
    if front is None or rear is None or sweep is None:
        return 0.0
    desired = max(0.0, sweep + limits.clearance_margin_m - front)
    desired += limits.robot_diameter_m * limits.recovery_buffer_ratio
    available = max(0.0, rear - limits.hard_clearance_m)
    return min(desired, available)
