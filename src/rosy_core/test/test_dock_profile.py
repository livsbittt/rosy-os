"""Dock shape fitting from a flat scan (design: 2026-09-07 rig)."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from rosy_core.docking.profile import DockProfile, ProfileFit, SensorOffset


def test_the_default_profile_is_the_three_posts_the_design_settled_on():
    profile = DockProfile()
    assert profile.post_lateral_m == (-0.075, -0.015, 0.075)
    assert profile.post_radius_m == 0.015


def test_a_mirror_symmetric_layout_is_refused_at_config_time():
    # A symmetric layout admits a mirror solution, so yaw has no sign, and it
    # is also what two furniture legs plus a third look like. The design chose
    # asymmetry deliberately; the config refuses to lose it.
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, 0.0, 0.075))


def test_fewer_than_three_posts_is_refused():
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, 0.075))


def test_the_scanner_offset_defaults_to_where_the_c1_actually_sits():
    # rplidar_link is 17 mm behind base_link. A detector that forgets this
    # reports the dock 17 mm closer than it is, every time.
    sensor = SensorOffset()
    assert sensor.x == pytest.approx(-0.017)
    assert sensor.y == 0.0
    assert sensor.yaw == 0.0


def test_an_empty_fit_is_a_value_not_an_exception():
    empty = ProfileFit(reason="nothing tried")
    assert empty.found is False
    assert empty.observation is None


import random

from rosy_core.docking.profile import fit

STEP_SIM = math.radians(360.0 / 640.0)      # Gazebo declares 640 samples
STEP_C1 = math.radians(0.24)                # C1 DenseBoost, denser


def _scan_of_posts(profile, x, y, yaw, step=STEP_SIM, sigma=0.0, seed=1,
                   half=0.6, hide=()):
    """Raycast the posts of `profile` with the dock at a known sensor-frame pose.

    Returns (ranges, angle_min, angle_increment) the way a LaserScan carries it.
    `hide` drops posts by index, which is how occlusion is simulated.
    """
    rng = random.Random(seed)
    centres = []
    for index, lateral in enumerate(sorted(profile.post_lateral_m)):
        if index in hide:
            continue
        centres.append((x - lateral * math.sin(yaw), y + lateral * math.cos(yaw)))

    count = int(half / step)
    angle_min = -count * step
    ranges = []
    for index in range(2 * count + 1):
        bearing = angle_min + index * step
        dx, dy = math.cos(bearing), math.sin(bearing)
        best = math.inf
        for cx, cy in centres:
            along = dx * cx + dy * cy
            offset = cx * cx + cy * cy - profile.post_radius_m ** 2
            disc = along * along - offset
            if disc < 0.0 or along <= 0.0:
                continue
            hit = along - math.sqrt(disc)
            if 0.0 < hit < best:
                best = hit
        if math.isinf(best):
            ranges.append(math.inf)
        else:
            ranges.append(best + (rng.gauss(0.0, sigma) if sigma else 0.0))
    return ranges, angle_min, step


def _scan_of_wall(distance=0.5, step=STEP_SIM, half=0.6):
    count = int(half / step)
    angle_min = -count * step
    ranges = [distance / math.cos(angle_min + i * step)
              for i in range(2 * count + 1)]
    return ranges, angle_min, step


def test_an_empty_scan_is_refused_with_a_reason():
    profile = DockProfile()
    got = fit([math.inf] * 200, -0.6, STEP_SIM, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.reason


def test_a_plain_wall_is_never_a_dock():
    # The strongest criterion in the design: a confident wrong pose drives the
    # robot somewhere that is not the dock. A wall is one continuous cluster.
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_wall()
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.clusters == 1


def test_two_visible_posts_are_not_a_dock():
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(profile, 0.5, 0.0, 0.0, hide=(1,))
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.clusters == 2


def test_three_posts_cluster_as_three_even_at_pessimistic_noise():
    # Clustering on range discontinuity loses 398 of 400 fits at sigma = 20 mm.
    # Angular gaps are noise-free, and this pins that choice.
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(
        profile, 0.5, 0.0, 0.0, sigma=0.020, seed=3)
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.clusters == 3
