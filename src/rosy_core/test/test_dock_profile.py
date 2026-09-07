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


def test_an_exact_scan_recovers_the_pose_in_base_link():
    profile = DockProfile()
    sensor = SensorOffset()
    ranges, angle_min, step = _scan_of_posts(
        profile, 0.500, 0.030, math.radians(8.0), step=STEP_C1)
    got = fit(ranges, angle_min, step, profile, sensor, now=12.5)

    assert got.found is True
    # base_link = sensor frame shifted by the scanner offset
    assert got.observation.x == pytest.approx(0.500 + sensor.x, abs=0.005)
    assert got.observation.y == pytest.approx(0.030, abs=0.003)
    assert got.observation.yaw == pytest.approx(math.radians(8.0), abs=math.radians(3.0))
    assert got.observation.at == 12.5
    assert got.residual_m is not None and got.residual_m < profile.max_residual_m


def test_the_scanner_offset_is_applied_and_not_forgotten():
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(profile, 0.500, 0.0, 0.0, step=STEP_C1)
    zero = fit(ranges, angle_min, step, profile, SensorOffset(0.0, 0.0, 0.0), now=1.0)
    real = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert zero.observation.x - real.observation.x == pytest.approx(0.017, abs=1e-6)


def test_a_layout_that_does_not_match_is_refused_by_the_residual_gate():
    # Three posts really are there, but not at this profile's spacing. The
    # residual is what separates "the dock" from "three things".
    seen = DockProfile(post_lateral_m=(-0.075, -0.015, 0.075))
    ranges, angle_min, step = _scan_of_posts(
        DockProfile(post_lateral_m=(-0.100, 0.010, 0.090)),
        0.500, 0.0, 0.0, step=STEP_C1)
    got = fit(ranges, angle_min, step, seen, SensorOffset(), now=1.0)
    assert got.found is False
    assert "residual" in (got.reason or "")


def _lateral_rms(sigma, trials=200, step=STEP_SIM, seed=11):
    profile = DockProfile()
    sensor = SensorOffset()
    rng = random.Random(seed)
    errors, misses = [], 0
    for trial in range(trials):
        x = rng.uniform(0.25, 0.70)
        y = rng.uniform(-0.06, 0.06)
        yaw = math.radians(rng.uniform(-15.0, 15.0))
        ranges, angle_min, increment = _scan_of_posts(
            profile, x, y, yaw, step=step, sigma=sigma, seed=trial)
        got = fit(ranges, angle_min, increment, profile, sensor, now=float(trial))
        if not got.found:
            misses += 1
            continue
        errors.append(got.observation.y - y)
    rms = math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else math.inf
    return rms, misses, trials


def test_the_lateral_budget_holds_at_the_noise_the_simulator_declares():
    # Gazebo declares sigma = 20 mm, which is worse than the real C1. The gate
    # is 10 mm, so passing here means passing without knowing the C1 number.
    # Measured: 0.87 mm RMS, 0 misses out of 200.
    rms, misses, trials = _lateral_rms(0.020)
    assert misses == 0, f"{misses}/{trials} scans produced no fit"
    assert rms <= 0.010, f"lateral RMS {rms * 1000:.2f} mm over the 10 mm gate"


def test_lateral_accuracy_barely_moves_when_range_noise_drops_sixfold():
    # This is the whole reason posts beat the V. If a change makes lateral
    # accuracy track sigma, the shape decision no longer holds and this fails.
    # Measured ratio 1.46; the bound is 2.0 so the test is not a coin flip.
    coarse, _, _ = _lateral_rms(0.020)
    fine, _, _ = _lateral_rms(0.0035)
    assert coarse / fine < 2.0, (
        f"lateral RMS moved {coarse / fine:.2f}x with sigma; "
        "the estimator has started depending on range noise")


def test_the_residual_gate_separates_a_noisy_right_dock_from_a_wrong_layout():
    """The gate only means something if it sits between the two populations.

    Measured: noisy-correct worst 13.0 mm over 400 trials, wrong-layout
    21.8 mm with no noise at all, gate 18 mm. Squeeze either side and the
    gate stops being able to do both jobs — which is exactly what happened
    with the first estimator that took the minimum range.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    rng = random.Random(5)
    worst = 0.0
    for trial in range(400):
        x = rng.uniform(0.25, 0.70)
        y = rng.uniform(-0.06, 0.06)
        yaw = math.radians(rng.uniform(-15.0, 15.0))
        ranges, angle_min, increment = _scan_of_posts(
            profile, x, y, yaw, step=STEP_SIM, sigma=0.020, seed=1000 + trial)
        got = fit(ranges, angle_min, increment, profile, sensor, now=0.0)
        assert got.found, f"the gate rejected a real dock: {got.reason}"
        worst = max(worst, got.residual_m)

    ranges, angle_min, increment = _scan_of_posts(
        DockProfile(post_lateral_m=(-0.100, 0.010, 0.090)),
        0.500, 0.0, 0.0, step=STEP_C1)
    wrong = fit(ranges, angle_min, increment, profile, sensor, now=0.0)
    assert wrong.found is False
    assert worst < profile.max_residual_m < wrong.residual_m, (
        f"gate {profile.max_residual_m * 1000:.0f} mm no longer sits between "
        f"noisy-correct {worst * 1000:.1f} mm and wrong-layout "
        f"{wrong.residual_m * 1000:.1f} mm")
