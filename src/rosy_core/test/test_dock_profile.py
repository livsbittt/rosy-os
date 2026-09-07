"""Dock shape fitting from a flat scan (design: 2026-09-07 rig)."""

from __future__ import annotations

import math
import random
import statistics

import pytest
from pydantic import ValidationError

from rosy_core.docking.profile import (
    DockProfile,
    ProfileFit,
    SensorOffset,
    _procrustes,
    fit,
)

STEP_SIM = math.radians(360.0 / 640.0)      # Gazebo declares 640 samples
STEP_C1 = math.radians(0.24)                # C1 DenseBoost, denser


# --- scene builders ----------------------------------------------------------

def _post_centres(profile, x, y, yaw, hide=()):
    """Sensor-frame centres of `profile`'s posts with the dock at (x, y, yaw).

    The dock frame's +x points away from the robot -- the robot meets the -x
    face -- so a post with a negative forward coordinate stands nearer the
    scanner. Getting that sign backwards would push the middle post into the
    dock instead of out of it, and every yaw number here would be measuring
    the wrong shape.
    """
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    centres = []
    for index, (forward, lateral) in enumerate(profile.post_points()):
        if index in hide:
            continue
        centres.append((x + forward * cos_y - lateral * sin_y,
                        y + forward * sin_y + lateral * cos_y))
    return centres


def _raycast(centres, radius, angle_min, step, count, sigma=0.0, seed=1,
             wall=None):
    """Ideal flat raycast against vertical cylinders, with optional background.

    `wall` puts a flat surface across every bearing at that distance. Without
    it the scene is a void, and a void is a scene that cannot happen in a
    room -- which is exactly how the angular-gap-only clustering rule went
    unchallenged for as long as it did.
    """
    rng = random.Random(seed)
    ranges = []
    for index in range(count):
        bearing = angle_min + index * step
        best = math.inf
        if wall is not None and abs(math.cos(bearing)) > 0.3:
            behind = wall / math.cos(bearing)
            if behind > 0.0:
                best = behind
        for cx, cy in centres:
            along = math.cos(bearing) * cx + math.sin(bearing) * cy
            offset = cx * cx + cy * cy - radius ** 2
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
    return ranges


def _scan_of_posts(profile, x, y, yaw, step=STEP_SIM, sigma=0.0, seed=1,
                   half=0.6, hide=(), wall=None):
    """Returns (ranges, angle_min, angle_increment) the way a LaserScan carries
    it. `hide` drops posts by index, which is how occlusion is simulated."""
    count = int(half / step)
    angle_min = -count * step
    ranges = _raycast(_post_centres(profile, x, y, yaw, hide),
                      profile.post_radius_m, angle_min, step, 2 * count + 1,
                      sigma=sigma, seed=seed, wall=wall)
    return ranges, angle_min, step


def _scan_all_round(profile, x, y, yaw, angle_min, step=STEP_SIM):
    """A full 2 pi sweep, which is what the C1 actually publishes."""
    count = int(2.0 * math.pi / step)
    ranges = _raycast(_post_centres(profile, x, y, yaw), profile.post_radius_m,
                      angle_min, step, count)
    return ranges, angle_min, step


def _scan_of_wall(distance=0.5, step=STEP_SIM, half=0.6):
    count = int(half / step)
    angle_min = -count * step
    ranges = [distance / math.cos(angle_min + i * step)
              for i in range(2 * count + 1)]
    return ranges, angle_min, step


# --- the profile is a config-time refusal ------------------------------------

def test_the_default_profile_is_the_three_posts_the_design_settled_on():
    profile = DockProfile()
    assert profile.post_lateral_m == (-0.075, -0.015, 0.075)
    assert profile.post_radius_m == 0.015


def test_the_default_posts_are_not_collinear():
    # Collinear posts are invariant under a mirror about their own axis, so a
    # random triple can match either handedness and the residual never sees
    # more than "collinear at the right spacing". The measured price of that
    # is in the module docstring's table. This pins the shape decision so a
    # tidy-up cannot quietly flatten the layout again.
    forwards = {forward for forward, _ in DockProfile().post_points()}
    assert len(forwards) > 1
    assert DockProfile().post_forward_m == (0.0, -0.020, 0.0)
    # Negative x is toward the robot: the middle post stands proud of the face.
    assert min(DockProfile().post_forward_m) < 0.0


def test_a_mirror_symmetric_layout_is_refused_at_config_time():
    # A symmetric layout admits a mirror solution, so yaw has no sign, and it
    # is also what two furniture legs plus a third look like. The design chose
    # asymmetry deliberately; the config refuses to lose it.
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, 0.0, 0.075))


def test_fewer_than_three_posts_is_refused():
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, 0.075))


def test_posts_closer_together_than_two_radii_are_refused():
    # A layout whose posts overlap, or nearly touch, can never resolve into
    # three clusters no matter how good the scan is. Refusing arrangements
    # that cannot work is this validator's whole job, and duplicates are the
    # degenerate case of the same mistake.
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, -0.075, 0.075))
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, -0.055, 0.075))
    # 2 * radius exactly is still refused: touching posts are one obstacle.
    with pytest.raises(ValidationError):
        DockProfile(post_lateral_m=(-0.075, -0.045, 0.075))
    DockProfile(post_lateral_m=(-0.075, -0.040, 0.075))


def test_a_forward_tuple_that_does_not_match_the_posts_is_refused():
    with pytest.raises(ValidationError):
        DockProfile(post_forward_m=(0.0, -0.020))


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


# --- the fit itself ----------------------------------------------------------

def test_an_empty_scan_is_refused_with_a_reason():
    profile = DockProfile()
    got = fit([math.inf] * 200, -0.6, STEP_SIM, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.reason


def test_no_input_makes_fit_raise():
    """`fit` returns failures as values. Nothing gets to raise out of it.

    This is the contract `DockAgent.poll()` set for the whole docking package,
    and the rig depends on it: a sweep that dies halfway throws away an
    expensive run. The cases below are the ones a real LaserScan can carry --
    empty arrays, non-numbers, NaN ranges, a zero or backwards increment.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    ranges, angle_min, step = _scan_of_posts(profile, 0.5, 0.0, 0.0)
    hostile = [
        ([], -0.6, STEP_SIM),
        ([None] * 50, -0.6, STEP_SIM),
        (["abc"] * 50, -0.6, STEP_SIM),
        ([math.nan] * 50, -0.6, STEP_SIM),
        ([0.5] * 50, -0.6, 0.0),
        (ranges, angle_min, 0.0),
        (ranges, angle_min, -step),
        (ranges, angle_min, math.nan),
        (ranges, angle_min, math.inf),
        (ranges, math.nan, step),
    ]
    for values, start, increment in hostile:
        got = fit(values, start, increment, profile, sensor, now=1.0)
        assert isinstance(got, ProfileFit)


def test_a_plain_wall_is_never_a_dock():
    # The strongest criterion in the design: a confident wrong pose drives the
    # robot somewhere that is not the dock. A wall is one continuous cluster,
    # far too wide to be a post.
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_wall()
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.candidates == 0


def test_two_visible_posts_are_not_a_dock():
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(profile, 0.5, 0.0, 0.0, hide=(1,))
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.candidates == 2


def test_a_lone_return_is_not_a_post_candidate():
    """One stray range is not a post, and letting it count is how a scene with
    two posts and a speck of dust becomes a three-post candidate set."""
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(profile, 0.5, 0.0, 0.0, hide=(1,))
    stray = int((0.45 - angle_min) / step)          # well clear of both posts
    ranges = list(ranges)
    ranges[stray] = 0.70
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.candidates == 2, "a single return was admitted as a post"
    assert "need 3" in (got.reason or "")


def test_three_posts_cluster_as_three_even_at_pessimistic_noise():
    # Clustering on range discontinuity with a 30 mm threshold lost 398 of 400
    # fits at sigma = 20 mm because 30 mm sits inside the noise. The threshold
    # is now 4 sigma and measured against the running cluster mean; this pins
    # that it no longer splits a post on noise alone.
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(
        profile, 0.5, 0.0, 0.0, sigma=0.020, seed=3)
    got = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert got.clusters == 3
    assert got.candidates == 3


def test_an_exact_scan_recovers_the_pose_in_base_link():
    profile = DockProfile()
    sensor = SensorOffset()
    ranges, angle_min, step = _scan_of_posts(
        profile, 0.500, 0.030, math.radians(8.0), step=STEP_C1)
    got = fit(ranges, angle_min, step, profile, sensor, now=12.5)

    assert got.found is True
    # base_link = sensor frame shifted by the scanner offset. Tolerances are
    # ~3x the worst error measured over a 0.30-0.70 m grid (0.5 mm, 0.6 mm,
    # 0.32 deg), not the 25x they used to be -- a loose tolerance here cannot
    # tell a working estimator from a broken one.
    assert got.observation.x == pytest.approx(0.500 + sensor.x, abs=0.0015)
    assert got.observation.y == pytest.approx(0.030, abs=0.0015)
    assert got.observation.yaw == pytest.approx(math.radians(8.0),
                                                abs=math.radians(1.0))
    assert got.observation.at == 12.5
    assert got.residual_m is not None and got.residual_m < profile.max_residual_m


def test_the_fitted_depth_pins_the_chord_mean_constant():
    """Depth is where the (pi/4) * radius term lives, so depth is what pins it.

    A cylinder's visible face runs from d - r head on to d at the edge, and
    equally spaced rays sample that face uniformly along the *chord*, whose
    mean is d - (pi/4) r. The arc-length mean, 2/pi, is a different average of
    the same surface and is wrong for this sampling; it would shift depth by
    (pi/4 - 2/pi) * 15 mm = 2.2 mm, and dropping the correction entirely
    shifts it by 3.2 mm. 1 mm here holds the constant to about +/-0.07.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    for step in (STEP_SIM, STEP_C1):
        ranges, angle_min, increment = _scan_of_posts(
            profile, 0.500, 0.0, 0.0, step=step)
        got = fit(ranges, angle_min, increment, profile, sensor, now=1.0)
        assert got.found is True
        assert got.observation.x == pytest.approx(0.500 + sensor.x, abs=0.001)


def test_the_scanner_offset_is_applied_and_not_forgotten():
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(profile, 0.500, 0.0, 0.0, step=STEP_C1)
    zero = fit(ranges, angle_min, step, profile, SensorOffset(0.0, 0.0, 0.0), now=1.0)
    real = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert zero.observation.x - real.observation.x == pytest.approx(0.017, abs=1e-6)


def test_a_layout_that_does_not_match_is_refused_by_the_residual_gate():
    # Three posts really are there, but not at this profile's spacing. The
    # residual is what separates "the dock" from "three things".
    seen = DockProfile()
    ranges, angle_min, step = _scan_of_posts(
        DockProfile(post_lateral_m=(-0.100, 0.010, 0.090)),
        0.500, 0.0, 0.0, step=STEP_C1)
    got = fit(ranges, angle_min, step, seen, SensorOffset(), now=1.0)
    assert got.found is False
    assert "residual" in (got.reason or "")


# --- the scan is a full circle, and its bearings wrap ------------------------

def test_a_full_circle_scan_is_fitted_whatever_its_angle_min():
    """The C1 publishes 360 degrees, and where the sweep starts is a driver
    detail, not a property of the dock.

    At angle_min = 0 the forward window is split across the wrap: half the
    posts land near bearing 0 and half near 2 pi. Without the wrap the second
    half is discarded and there is no dock; with the wrap but without sorting,
    the surviving points arrive out of bearing order and cluster into
    nonsense. Both halves of that are load-bearing, so both are asserted.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    for angle_min in (-math.pi, 0.0):
        ranges, start, step = _scan_all_round(
            profile, 0.500, 0.020, math.radians(6.0), angle_min)
        got = fit(ranges, start, step, profile, sensor, now=3.0)
        assert got.found is True, f"angle_min={angle_min}: {got.reason}"
        assert got.candidates == 3
        assert got.observation.x == pytest.approx(0.500 + sensor.x, abs=0.003)
        assert got.observation.y == pytest.approx(0.020, abs=0.003)


def test_the_posts_may_be_declared_in_any_order():
    """A config file is written by a person, and people do not sort tuples.

    The correspondence between clusters and model posts holds in bearing
    order, so the model has to be sorted -- and the forward coordinate has to
    travel with its own lateral when that happens, or the middle post's 20 mm
    lands on an outer post.
    """
    tidy = DockProfile()
    shuffled = DockProfile(post_lateral_m=(0.075, -0.075, -0.015),
                           post_forward_m=(0.0, 0.0, -0.020))
    assert shuffled.post_points() == tidy.post_points()

    ranges, angle_min, step = _scan_of_posts(
        tidy, 0.500, 0.020, math.radians(8.0), step=STEP_C1)
    ordered = fit(ranges, angle_min, step, tidy, SensorOffset(), now=1.0)
    jumbled = fit(ranges, angle_min, step, shuffled, SensorOffset(), now=1.0)
    assert ordered.found is True and jumbled.found is True
    assert jumbled.observation.x == pytest.approx(ordered.observation.x, abs=1e-9)
    assert jumbled.observation.y == pytest.approx(ordered.observation.y, abs=1e-9)
    assert jumbled.observation.yaw == pytest.approx(ordered.observation.yaw, abs=1e-9)


# --- the dock stands in a room, not in a void --------------------------------

def test_a_wall_behind_the_posts_is_still_a_dock():
    """The case nothing covered, and the one the C1 will actually see.

    Angular gaps only exist if nothing is behind the posts inside
    max_range_m. In a room a wall fills every bearing, no gap exists anywhere,
    and the whole scene used to collapse into one cluster: at 0.60 m and
    1.00 m the shipped fit returned found=False with clusters=1. A rig run
    that way would report a near-zero detection rate and the verdict would be
    about the clustering rule, not about the dock.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    for wall in (0.60, 0.80, 1.00, 1.19):
        for sigma in (0.0, 0.020):
            ranges, angle_min, step = _scan_of_posts(
                profile, 0.500, 0.0, 0.0, sigma=sigma, seed=7, wall=wall)
            got = fit(ranges, angle_min, step, profile, sensor, now=1.0)
            assert got.found is True, f"wall {wall} m sigma {sigma}: {got.reason}"
            assert got.observation.x == pytest.approx(0.500 + sensor.x, abs=0.005)
            assert got.observation.y == pytest.approx(0.0, abs=0.005)
            # The wall is still in the scene: it fragments into clusters that
            # are too wide to be posts, and the candidate filter drops them.
            assert got.clusters > got.candidates


def test_a_dock_pressed_against_its_background_cannot_be_separated():
    """The mechanical requirement, asserted rather than assumed.

    Splitting on a range step means the posts must stand more than
    max_range_step_m in front of whatever is behind them at scan height
    (95 mm off the floor). 80 mm of clearance works; 65 mm does not. The dock
    does not exist yet, so this is an input to its mechanical design, and a
    test is the place it will not be forgotten.
    """
    profile = DockProfile()
    ranges, angle_min, step = _scan_of_posts(
        profile, 0.500, 0.0, 0.0, wall=0.55)
    tight = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert tight.found is False
    assert tight.candidates < 3

    ranges, angle_min, step = _scan_of_posts(
        profile, 0.500, 0.0, 0.0, wall=0.58)
    roomy = fit(ranges, angle_min, step, profile, SensorOffset(), now=1.0)
    assert roomy.found is True


def test_the_dock_is_picked_out_of_a_cluttered_scene():
    """More than three post-shaped clusters is the normal case, not a failure.

    The shipped fit rejected any scan whose cluster count was not exactly
    three, which is why a background killed it. The subset search is what
    replaced that, and this is the case it exists for.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    centres = _post_centres(profile, 0.500, 0.0, 0.0)
    for bearing, distance in ((-0.50, 0.40), (0.35, 0.75), (0.52, 1.00)):
        centres.append((distance * math.cos(bearing), distance * math.sin(bearing)))
    count = int(0.6 / STEP_SIM)
    angle_min = -count * STEP_SIM
    ranges = _raycast(centres, profile.post_radius_m, angle_min, STEP_SIM,
                      2 * count + 1)
    got = fit(ranges, angle_min, STEP_SIM, profile, sensor, now=1.0)
    assert got.found is True, got.reason
    assert got.candidates == 6
    assert got.observation.x == pytest.approx(0.500 + sensor.x, abs=0.003)
    assert got.observation.y == pytest.approx(0.0, abs=0.003)


def test_too_many_candidates_is_refused_rather_than_explored():
    """This runs inside a control tick, and the search is cubic in candidates.

    Twelve candidates is 220 subsets, which is nothing. A forest of posts is
    not a dock scene, so the answer is a reason, not a longer search.
    """
    profile = DockProfile()
    centres = [(1.0 * math.cos(-0.56 + 0.08 * k), 1.0 * math.sin(-0.56 + 0.08 * k))
               for k in range(15)]
    count = int(0.6 / STEP_SIM)
    angle_min = -count * STEP_SIM
    ranges = _raycast(centres, profile.post_radius_m, angle_min, STEP_SIM,
                      2 * count + 1)
    got = fit(ranges, angle_min, STEP_SIM, profile, SensorOffset(), now=1.0)
    assert got.found is False
    assert got.candidates > 12
    assert "cap" in (got.reason or "")


# --- the angular gap has a floor and a ceiling, and both were measured -------

def test_one_dropped_return_never_breaks_a_far_post():
    """Signal loss with incidence angle is on the design's unmodelled list.

    At 1.10 m a post is only three rays wide. A gap factor of 1.5 -- or 1.01 --
    splits it on a single dropout into 1 + 1, both below min_points_per_post,
    and the scan loses a candidate: 3 of the 9 single dropouts break the fit
    that way. At 2.5 it is 0 of 9. Being maximally brittle to exactly the
    physics the model omits is not a value worth defending.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    ranges, angle_min, step = _scan_of_posts(profile, 1.10, 0.0, 0.0)
    hits = [index for index, value in enumerate(ranges) if math.isfinite(value)]
    assert len(hits) >= 9
    for index in hits:
        dropped = list(ranges)
        dropped[index] = math.inf
        got = fit(dropped, angle_min, step, profile, sensor, now=1.0)
        assert got.found is True, f"dropping ray {index} lost the dock: {got.reason}"


def test_a_yawed_dock_still_separates_into_three_posts():
    """The ceiling on the gap factor. Yaw crowds the posts in bearing.

    The sweep grid goes to +/-20 deg. At 0.60 m and 20 deg a factor of 3.0
    glues all three posts into one cluster -- one candidate, no dock. 2.5
    keeps them apart, which is what sets the upper end of the window.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    for yaw_deg in (15.0, 20.0, -20.0):
        ranges, angle_min, step = _scan_of_posts(
            profile, 0.600, 0.0, math.radians(yaw_deg))
        got = fit(ranges, angle_min, step, profile, sensor, now=1.0)
        assert got.candidates == 3, f"yaw {yaw_deg}: {got.reason}"
        assert got.found is True, f"yaw {yaw_deg}: {got.reason}"


# --- the internal fit cannot be fed mismatched sets --------------------------

def test_procrustes_refuses_a_point_set_it_cannot_score():
    """`zip` stops at the shorter side, so an over-long observation would be
    scored on its first few points and report an artificially low residual --
    silence that manufactures false positives. `fit` always passes equal
    lengths, so this can only fire on a caller bug, and a caller bug should
    be loud."""
    model = [(0.0, -0.075), (-0.020, -0.015), (0.0, 0.075)]
    with pytest.raises(ValueError):
        _procrustes(model, model + [(0.0, 0.2)])
    with pytest.raises(ValueError):
        _procrustes(model, model[:2])
    with pytest.raises(ValueError):
        _procrustes([], [])


# --- the measured budgets ----------------------------------------------------

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
    # Measured: 0.70 mm RMS, 0 misses out of 200.
    rms, misses, trials = _lateral_rms(0.020)
    assert misses == 0, f"{misses}/{trials} scans produced no fit"
    assert rms <= 0.010, f"lateral RMS {rms * 1000:.2f} mm over the 10 mm gate"


def test_lateral_accuracy_barely_moves_when_range_noise_drops_sixfold():
    """This is the whole reason posts beat the V. If a change makes lateral
    accuracy track sigma, the shape decision no longer holds.

    One seed is not evidence: over twelve seeds the ratio spans 1.20-1.35 at
    the simulator's step and 1.52-1.78 at the C1's finer step, and the finer
    step is the harder case because discretisation stops masking the noise
    term. The old test quoted 1.46 from its single luckiest seed while the
    C1 step it never ran at was sitting at 1.88-1.99 against this same 2.0
    bound. So: the median of several seeds, at both step sizes, and no fit
    may be missing on either leg.
    """
    for step, name in ((STEP_SIM, "sim"), (STEP_C1, "c1")):
        ratios = []
        for seed in (11, 12, 13, 14, 15):
            coarse, coarse_misses, trials = _lateral_rms(0.020, trials=150,
                                                         step=step, seed=seed)
            fine, fine_misses, _ = _lateral_rms(0.0035, trials=150, step=step,
                                                seed=seed)
            assert coarse_misses == 0 and fine_misses == 0, (
                f"{name} seed {seed}: {coarse_misses}/{fine_misses} of {trials} "
                "scans produced no fit, so the ratio is measured on a subset")
            ratios.append(coarse / fine)
        median = statistics.median(ratios)
        assert median < 2.0, (
            f"{name}: median lateral RMS moved {median:.2f}x with sigma "
            f"(spread {min(ratios):.2f}-{max(ratios):.2f}); "
            "the estimator has started depending on range noise")


def test_the_yaw_error_stays_where_the_rig_measured_it():
    """Yaw is a recorded column, not a gate -- `_tick_approaching` steers on
    atan2(y, x) and never reads it. It is pinned anyway because it is the
    quantity the layout change was supposed to buy, and an unpinned number
    that nobody gates on is a number that silently rots.

    Measured at sigma = 20 mm: 4.08 deg RMS at the simulator's step, 2.68 deg
    at the C1's. The bound below is roughly 1.5x the worse of those.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    for step, bound in ((STEP_SIM, 6.0), (STEP_C1, 4.5)):
        rng = random.Random(11)
        errors, misses = [], 0
        for trial in range(200):
            x = rng.uniform(0.25, 0.70)
            y = rng.uniform(-0.06, 0.06)
            yaw = math.radians(rng.uniform(-15.0, 15.0))
            ranges, angle_min, increment = _scan_of_posts(
                profile, x, y, yaw, step=step, sigma=0.020, seed=trial)
            got = fit(ranges, angle_min, increment, profile, sensor,
                      now=float(trial))
            if not got.found:
                misses += 1
                continue
            errors.append(math.degrees(got.observation.yaw - yaw))
        assert misses == 0, f"{misses}/200 scans produced no fit"
        rms = math.sqrt(sum(e * e for e in errors) / len(errors))
        assert rms <= bound, f"yaw RMS {rms:.2f} deg over the {bound:.1f} deg bound"


def test_the_residual_gate_separates_a_noisy_right_dock_from_a_wrong_layout():
    """The gate only means something if it sits between the two populations.

    Measured: noisy-correct worst 13.0 mm over 400 trials, wrong-layout
    21.8 mm with no noise at all, gate 18 mm. Squeeze either side and the
    gate stops being able to do both jobs -- which is exactly what happened
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


def test_random_three_cylinder_scenes_rarely_pass_the_gate():
    """The design's hardest criterion is zero false positives, and this fit
    does not meet it. The number is asserted rather than hidden.

    Three cylinders of the dock's own radius, dropped at random bearings and
    ranges inside the search window, pass the 18 mm gate 0.177% of the time
    over 120,000 scenes. Breaking the layout's collinearity removed the
    mirror degeneracy and took that from 0.187%, which is the whole size of
    the effect; a rigid three-point match is three side lengths inside a
    tolerance, and that tolerance volume barely depends on the shape. Zero
    needs a fourth post or a second signal, and the rig's verdict is what
    should choose. Until then this bound catches a regression that made it
    worse without pretending the criterion is met.
    """
    profile = DockProfile()
    sensor = SensorOffset()
    rng = random.Random(5)
    count = int(0.6 / STEP_SIM)
    angle_min = -count * STEP_SIM
    passed = 0
    for scene in range(2000):
        centres = []
        for _ in range(3):
            bearing = rng.uniform(-0.45, 0.45)
            distance = rng.uniform(0.25, 1.00)
            centres.append((distance * math.cos(bearing),
                            distance * math.sin(bearing)))
        ranges = _raycast(centres, profile.post_radius_m, angle_min, STEP_SIM,
                          2 * count + 1)
        if fit(ranges, angle_min, STEP_SIM, profile, sensor, now=0.0).found:
            passed += 1
    assert passed <= 12, (
        f"{passed}/2000 random three-cylinder scenes were called a dock; "
        "3 is the measured figure and 12 is a 3-sigma ceiling on it")
