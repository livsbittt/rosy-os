"""ROS-free adaptive motion contracts for the exact v2 mapping run."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "launch" / "map_v2_traversal.py"


def _mod():
    spec = importlib.util.spec_from_file_location("map_v2_traversal", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_open_space_can_use_the_sim_ceiling_but_narrow_space_crawls():
    mod = _mod()
    limits = mod.TraversalLimits(robot_diameter_m=0.172, max_linear_mps=0.10)

    assert mod.adaptive_speed(1.0, 0.5, 0.0, limits) == pytest.approx(0.10)
    narrow = mod.adaptive_speed(0.13, 0.11, 0.0, limits)
    assert limits.crawl_linear_mps <= narrow < 0.10
    assert mod.adaptive_speed(0.095, 0.095, 0.0, limits) == 0.0


def test_curvature_can_only_reduce_the_clearance_speed():
    mod = _mod()
    limits = mod.TraversalLimits(robot_diameter_m=0.172, max_linear_mps=0.10)
    straight = mod.adaptive_speed(0.5, 0.3, 0.0, limits)
    bend = mod.adaptive_speed(0.5, 0.3, 4.0, limits)

    assert 0.0 < bend < straight <= limits.max_linear_mps


def test_reverse_distance_is_geometry_and_rear_clearance_derived_not_fixed():
    mod = _mod()
    limits = mod.TraversalLimits(robot_diameter_m=0.172)

    short = mod.recovery_reverse_distance(
        front_clearance_m=0.08,
        rear_clearance_m=0.30,
        turn_sweep_radius_m=0.10,
        limits=limits,
    )
    roomy = mod.recovery_reverse_distance(
        front_clearance_m=0.03,
        rear_clearance_m=0.50,
        turn_sweep_radius_m=0.10,
        limits=limits,
    )
    constrained = mod.recovery_reverse_distance(
        front_clearance_m=0.03,
        rear_clearance_m=0.13,
        turn_sweep_radius_m=0.10,
        limits=limits,
    )

    assert 0.0 < short < roomy
    assert roomy > 0.08
    assert 0.0 <= constrained < short


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.01])
def test_invalid_or_negative_clearance_fails_closed(bad):
    mod = _mod()
    limits = mod.TraversalLimits(robot_diameter_m=0.172)

    assert mod.adaptive_speed(bad, 0.2, 0.0, limits) == 0.0
    assert mod.recovery_reverse_distance(0.03, bad, 0.10, limits) == 0.0
