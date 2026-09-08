"""Probe rows and the verdict that picks a detector (design: 2026-09-07 rig).

The verdict is the one place in this branch where numbers, not opinion, choose
the detector. So the tests here are written to fail when the verdict can be
talked into an answer: every failure assertion names the *reason string*, not
just the flipped flag, because a fail for the wrong reason sends the operator
to the wrong sensor.
"""

from __future__ import annotations

import math

import pytest

from rosy_core.docking.probe import (ACQUIRE_RATE_MIN, FIELDS,
                                     IR_ONSET_MIN_M, LATERAL_RMS_MAX_M,
                                     MIN_ABSENT, MIN_STAGING, STAGING_BAND_M,
                                     ProbeFormatError, ProbeRow, ProbeVerdict,
                                     append_row, read_rows, verdict)

#: The grid `dock_sweep.py` ships, kept in step with its `--distances` default
#: because the envelope walk has to survive the spacing of the sweep that feeds
#: it. If the two drift apart the walk is being tested against a grid nobody
#: measures, which is how a comment starts asserting a correspondence that no
#: longer holds.
GRID = (0.08, 0.12, 0.16, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55,
        0.60, 0.68, 0.70, 0.72, 0.85, 1.00)
LATERALS = (-0.15, -0.08, -0.03, 0.0, 0.03, 0.08, 0.15)
YAWS = (-20.0, -10.0, 0.0, 10.0, 20.0)


def test_the_schema_is_one_table_for_all_three_candidates():
    # Splitting the CSV per candidate splits the verdict into three, and at
    # that moment the candidates stop being comparable.
    assert FIELDS[:3] == ("lane", "candidate", "dock_present")
    for name in ("fit_y", "int_target", "int_baseline", "ir_l", "ir_r", "ambient"):
        assert name in FIELDS


def test_a_row_round_trips_through_csv_with_blanks_preserved(tmp_path):
    path = tmp_path / "rows.csv"
    geometry = ProbeRow(lane="sim", candidate="geometry", truth_x=0.7,
                        truth_y=0.02, truth_yaw=0.0, fit_x=0.68, fit_y=0.021,
                        fit_yaw=0.01, residual=0.002, points=22, confidence=0.8)
    infrared = ProbeRow(lane="bench", candidate="ir", truth_x=0.04,
                        truth_y=-0.01, truth_yaw=0.0, ambient="direct-sun",
                        ir_l=812, ir_mid=903, ir_r=511)
    append_row(path, geometry)
    append_row(path, infrared)

    back = read_rows(path)
    assert len(back) == 2
    assert back[0].fit_y == 0.021
    assert back[0].ir_l is None          # blank stays blank, not zero
    assert back[1].ambient == "direct-sun"
    assert back[1].fit_x is None
    assert back[1].ir_mid == 903


def test_the_header_is_written_once(tmp_path):
    path = tmp_path / "rows.csv"
    for _ in range(3):
        append_row(path, ProbeRow(lane="sim", candidate="geometry",
                                  truth_x=0.5, truth_y=0.0, truth_yaw=0.0,
                                  fit_x=0.48, fit_y=0.001))
    assert path.read_text(encoding="utf-8").count("truth_x") == 1
    assert len(read_rows(path)) == 3


def test_a_dock_absent_row_is_explicit_rather_than_a_missing_truth(tmp_path):
    # False positives are the strongest criterion, so "there was no dock" has
    # to be a stated fact and not an empty cell that could mean anything.
    path = tmp_path / "rows.csv"
    append_row(path, ProbeRow(lane="sim", candidate="geometry",
                              dock_present=False, truth_x=math.nan,
                              truth_y=math.nan, truth_yaw=math.nan))
    back = read_rows(path)
    assert back[0].dock_present is False
    assert math.isnan(back[0].truth_x)


# --- hand-edited CSVs, which are the expected input ------------------------

def _hand_written(tmp_path, body, name="hand.csv", encoding="utf-8"):
    path = tmp_path / name
    path.write_text(",".join(FIELDS) + "\n" + body, encoding=encoding)
    return path


def test_a_genuinely_blank_truth_cell_reads_as_nan_not_zero(tmp_path):
    # `_encode(math.nan)` writes the literal text "nan", so a row built in
    # Python never exercises this branch. A human deleting a cell does, and
    # reading that blank as 0.0 means "the dock was on top of the robot".
    path = _hand_written(tmp_path, "sim,geometry,1,,,,,,,,,,,,,,,\n")
    row = read_rows(path)[0]
    assert math.isnan(row.truth_x)
    assert math.isnan(row.truth_y)
    assert math.isnan(row.truth_yaw)
    assert row.fit_x is None


def test_a_blank_dock_present_cell_reads_as_present(tmp_path):
    # Reading a blank as "no dock" would silently inflate the false-positive
    # count and drop a candidate that should have passed.
    path = _hand_written(tmp_path, "sim,geometry,,0.7,0.0,0.0,,0.7,0.0,,,,,,,,,\n")
    assert read_rows(path)[0].dock_present is True


@pytest.mark.parametrize("text,expected", [("1", True), ("true", True),
                                           ("TRUE", True), ("yes", True),
                                           ("0", False), ("false", False),
                                           ("FALSE", False), ("no", False)])
def test_dock_present_accepts_both_spellings_case_insensitively(tmp_path, text,
                                                                expected):
    path = _hand_written(tmp_path,
                         f"sim,geometry,{text},0.7,0.0,0.0,,0.7,0.0,,,,,,,,,\n")
    assert read_rows(path)[0].dock_present is expected


@pytest.mark.parametrize("text", ["off", "0.0", "maybe", "-1"])
def test_an_unrecognised_dock_present_cell_is_refused_not_guessed(tmp_path, text):
    # The old denylist read every one of these as "the dock was there".
    path = _hand_written(tmp_path,
                         f"sim,geometry,{text},0.7,0.0,0.0,,0.7,0.0,,,,,,,,,\n")
    with pytest.raises(ProbeFormatError) as caught:
        read_rows(path)
    assert "dock_present" in str(caught.value)


def test_an_unreadable_cell_names_the_file_row_and_column(tmp_path):
    path = _hand_written(tmp_path,
                         "sim,geometry,1,0.7,0.0,0.0,,None,,,,,,,,,,\n",
                         name="measured.csv")
    with pytest.raises(ProbeFormatError) as caught:
        read_rows(path)
    message = str(caught.value)
    assert "measured.csv" in message
    assert ":2" in message                 # the data row, not the header
    assert "column fit_x" in message
    assert "'None'" in message


def test_a_utf8_bom_does_not_blank_the_lane(tmp_path):
    # Excel writes a BOM. Read as plain utf-8 the first header becomes
    # "﻿lane", every lane reads empty, and the per-lane floors cannot be
    # applied to anything.
    path = _hand_written(tmp_path, "sim,geometry,1,0.7,0.0,0.0,,0.7,0.0,,,,,,,,,\n",
                         encoding="utf-8-sig")
    assert read_rows(path)[0].lane == "sim"


# --- geometry -------------------------------------------------------------

def _grid_rows(acquires=(0.30, 1.00), lateral_error=0.002, lane="sim",
               laterals=LATERALS, yaws=YAWS, distances=GRID,
               acquire_share=1.0):
    """A sweep over the shipped grid that acquires only inside `acquires`.

    `acquire_share` misses a fraction of the samples everywhere it does
    acquire, which is how a marginal detector actually looks.
    """
    rows = []
    per_distance = len(laterals) * len(yaws)
    acquired_per_distance = round(acquire_share * per_distance)
    for distance in distances:
        inside = acquires[0] - 1e-9 <= distance <= acquires[1] + 1e-9
        index = 0
        for lateral in laterals:
            for yaw in yaws:
                got = inside and index < acquired_per_distance
                index += 1
                rows.append(ProbeRow(
                    lane=lane, candidate="geometry", truth_x=distance,
                    truth_y=lateral, truth_yaw=math.radians(yaw),
                    fit_x=distance if got else None,
                    fit_y=(lateral + lateral_error) if got else None,
                    fit_yaw=math.radians(yaw) if got else None,
                    residual=0.001 if got else None,
                    points=22 if got else None,
                    confidence=0.9 if got else None))
    return rows


def _absent_rows(false_positives=0, count=None, lane="sim"):
    total = MIN_ABSENT[lane] if count is None else count
    return [ProbeRow(lane=lane, candidate="geometry", dock_present=False,
                     truth_x=math.nan, truth_y=math.nan, truth_yaw=math.nan,
                     fit_x=0.5 if index < false_positives else None,
                     fit_y=0.0 if index < false_positives else None)
            for index in range(total)]


def _with_staging_count(rows, count):
    """Trim the staging band down to exactly `count` samples."""
    kept, out = 0, []
    for row in rows:
        in_band = (row.dock_present and math.isfinite(row.truth_x)
                   and STAGING_BAND_M[0] <= row.truth_x <= STAGING_BAND_M[1])
        if in_band:
            kept += 1
            if kept > count:
                continue
        out.append(row)
    return out


def _only(rows, **kwargs):
    got = verdict(rows, **kwargs)
    assert len(got) == 1, got
    return got[0]


def test_a_clean_geometry_sweep_passes():
    got = _only(_grid_rows() + _absent_rows())
    assert got.candidate == "geometry"
    assert got.lane == "sim"
    assert got.passed is True, got.reasons
    assert got.metrics["lateral_rms_m"] < LATERAL_RMS_MAX_M
    assert got.metrics["acquire_rate"] == 1.0


def test_lateral_error_over_the_gate_fails_and_says_so():
    got = _only(_grid_rows(lateral_error=0.018) + _absent_rows())
    assert got.passed is False
    assert any(reason.startswith("lateral RMS 18.0 mm over 10 mm")
               for reason in got.reasons), got.reasons


def test_one_false_positive_fails_the_candidate():
    # Zero is the criterion. One confident wrong pose drives the robot into
    # something that is not the dock.
    got = _only(_grid_rows() + _absent_rows(false_positives=1))
    assert got.passed is False
    assert got.reasons == ("1 false positive(s)",)
    assert got.metrics["false_positives"] == 1.0


def test_no_dock_absent_samples_is_a_failure_not_a_pass():
    # A sweep that never looked at an empty room has not tested the criterion.
    got = _only(_grid_rows())
    assert got.passed is False
    assert "no dock-absent samples, so false positives are untested" in got.reasons


def test_a_sweep_that_never_acquires_fails_on_the_rate():
    got = _only(_grid_rows(acquires=(9.0, 9.0)) + _absent_rows())
    assert got.passed is False
    assert got.metrics["acquire_rate"] == 0.0
    assert f"acquisition 0.0% below {ACQUIRE_RATE_MIN:.0%}" in got.reasons


def test_an_acquisition_rate_just_under_the_criterion_fails():
    # 80% acquisition is a detector that loses the dock one staging approach
    # in five. The criterion is 95% and it is pinned here, not eyeballed.
    got = _only(_grid_rows(acquire_share=0.8) + _absent_rows())
    assert got.passed is False
    assert got.metrics["acquire_rate"] == pytest.approx(0.8)
    assert "acquisition 80.0% below 95%" in got.reasons


# --- C1: the envelope lower bound -----------------------------------------

def test_the_usable_envelope_lower_bound_is_the_bottom_not_the_top():
    # The bug this pins returned the TOP of the working range, because the
    # sweep grid puts holes in fixed-width bins and the walk stopped at the
    # first hole. This number sets a dock type's docking_threshold_m.
    got = _only(_grid_rows(acquires=(0.30, 1.00)) + _absent_rows())
    assert got.metrics["envelope_low_m"] == pytest.approx(0.30)


@pytest.mark.parametrize("acquires,expected", [((0.25, 0.85), 0.25),
                                               ((0.25, 0.70), 0.25),
                                               ((0.40, 1.00), 0.40),
                                               ((0.60, 0.72), 0.60)])
def test_the_envelope_lower_bound_is_exact_over_the_shipped_grid(acquires,
                                                                 expected):
    rows = _grid_rows(acquires=acquires) + _absent_rows()
    assert _only(rows).metrics["envelope_low_m"] == pytest.approx(expected)


def test_a_sweep_that_never_loses_the_dock_has_not_measured_the_bound():
    # Acquiring at every distance on the grid does not mean the bound is
    # 0.02 m; it means the grid ran out first. Reporting 0.02 would put an
    # unmeasured number into robot configuration.
    got = _only(_grid_rows(acquires=(0.0, 9.0)) + _absent_rows())
    assert math.isnan(got.metrics["envelope_low_m"])
    assert got.passed is False
    assert any("envelope lower bound was not measured" in reason
               for reason in got.reasons), got.reasons


def test_a_nan_envelope_cannot_pass_silently():
    # nan > threshold is False, so before the fix an unmeasured bound was
    # indistinguishable from a good one: passed=True, reasons=().
    rows = _grid_rows(acquires=(0.30, 0.60)) + _absent_rows()
    got = _only(rows)
    assert math.isnan(got.metrics["envelope_low_m"])   # staging never acquired
    assert got.passed is False
    assert any("envelope lower bound was not measured" in reason
               for reason in got.reasons), got.reasons


def test_a_grid_too_coarse_to_bracket_the_bound_stops_at_what_it_knows():
    # 0.60 -> 0.45 is a 0.15 m step. The sweep cannot tell whether the fit
    # survives at 0.50, so the answer is the lowest distance it actually
    # measured as working, never an interpolation through the gap.
    coarse = (0.40, 0.45, 0.60, 0.68, 0.70, 0.72)
    rows = _grid_rows(acquires=(0.45, 1.00), distances=coarse) + _absent_rows()
    assert _only(rows).metrics["envelope_low_m"] == pytest.approx(0.60)


# --- C2: a NaN metric must not pass ---------------------------------------

def test_a_blank_truth_lateral_cannot_produce_a_passing_rms():
    # Somebody deletes the truth_y column. Every (fit_y - nan) ** 2 is nan,
    # the RMS is nan, and `nan > LATERAL_RMS_MAX_M` is False.
    rows = [ProbeRow(lane="sim", candidate="geometry", truth_x=row.truth_x,
                     truth_y=math.nan, truth_yaw=row.truth_yaw,
                     fit_x=row.fit_x, fit_y=row.fit_y, fit_yaw=row.fit_yaw)
            for row in _grid_rows()]
    got = _only(rows + _absent_rows())
    assert got.passed is False
    assert "no fits inside the gate window" in got.reasons
    assert not math.isnan(got.metrics["lateral_rms_m"])


def test_a_fit_that_returned_nan_everywhere_is_not_an_acquisition():
    # `fit_x is not None` counted a nan fit as a pose, so a sweep whose fit
    # collapsed reported acquire_rate = 1.0 and passed.
    rows = [ProbeRow(lane="sim", candidate="geometry", truth_x=row.truth_x,
                     truth_y=row.truth_y, truth_yaw=row.truth_yaw,
                     fit_x=math.nan, fit_y=math.nan, fit_yaw=math.nan)
            for row in _grid_rows()]
    got = _only(rows + _absent_rows())
    assert got.metrics["acquire_rate"] == 0.0
    assert got.passed is False
    assert "acquisition 0.0% below 95%" in got.reasons


# --- C3: the design's sample floors ---------------------------------------

@pytest.mark.parametrize("lane", ["sim", "bench"])
def test_dock_absent_samples_one_under_the_lane_floor_fail(lane):
    floor = MIN_ABSENT[lane]
    rows = _grid_rows(lane=lane) + _absent_rows(count=floor - 1, lane=lane)
    got = _only(rows)
    assert got.passed is False
    assert (f"{floor - 1} dock-absent samples, under the {lane} floor of "
            f"{floor}") in got.reasons


@pytest.mark.parametrize("lane", ["sim", "bench"])
def test_dock_absent_samples_at_the_lane_floor_pass(lane):
    floor = MIN_ABSENT[lane]
    rows = _grid_rows(lane=lane) + _absent_rows(count=floor, lane=lane)
    got = _only(rows)
    assert got.passed is True, got.reasons
    assert got.metrics["absent_samples"] == float(floor)


@pytest.mark.parametrize("lane", ["sim", "bench"])
def test_staging_samples_one_under_the_lane_floor_fail(lane):
    floor = MIN_STAGING[lane]
    rows = _with_staging_count(_grid_rows(lane=lane), floor - 1)
    got = _only(rows + _absent_rows(lane=lane))
    assert got.passed is False
    assert (f"{floor - 1} staging samples, under the {lane} floor of "
            f"{floor}") in got.reasons


@pytest.mark.parametrize("lane", ["sim", "bench"])
def test_staging_samples_at_the_lane_floor_pass(lane):
    floor = MIN_STAGING[lane]
    rows = _with_staging_count(_grid_rows(lane=lane), floor)
    got = _only(rows + _absent_rows(lane=lane))
    assert got.passed is True, got.reasons
    assert got.metrics["staging_samples"] == float(floor)


def test_a_two_row_table_cannot_certify_zero_false_positives():
    # This passed outright before the floors landed. So did 400 copies of one
    # pose: "zero false positives" certified from a single empty-room sample.
    rows = [ProbeRow(lane="sim", candidate="geometry", truth_x=0.70,
                     truth_y=0.0, truth_yaw=0.0, fit_x=0.70, fit_y=0.001),
            ProbeRow(lane="sim", candidate="geometry", dock_present=False,
                     truth_x=math.nan, truth_y=math.nan, truth_yaw=math.nan)]
    got = _only(rows)
    assert got.passed is False
    assert "1 dock-absent samples, under the sim floor of 500" in got.reasons
    assert "1 staging samples, under the sim floor of 100" in got.reasons

    repeated = _only([rows[0]] * 400 + [rows[1]])
    assert repeated.passed is False
    assert "1 dock-absent samples, under the sim floor of 500" in repeated.reasons


# --- lanes ----------------------------------------------------------------

def test_each_lane_gets_its_own_verdict():
    rows = (_grid_rows(lane="sim") + _absent_rows(lane="sim")
            + _grid_rows(lane="bench", laterals=(-0.03, 0.0, 0.03),
                         yaws=(-10.0, 0.0, 10.0))
            + _absent_rows(lane="bench"))
    got = verdict(rows)
    assert [(one.candidate, one.lane) for one in got] == [
        ("geometry", "bench"), ("geometry", "sim")]
    assert all(one.passed for one in got), [one.reasons for one in got]


def test_a_bad_bench_lane_does_not_contaminate_the_sim_lane():
    # Ruler-read bench truth and exact sim truth cannot share one RMS, and
    # 500 sim rows would dilute 50 bench rows until neither number means
    # anything. Pooled, this table passed on the sim rows' weight.
    rows = (_grid_rows(lane="sim") + _absent_rows(lane="sim")
            + _grid_rows(lane="bench", lateral_error=0.05,
                         laterals=(-0.03, 0.0, 0.03),
                         yaws=(-10.0, 0.0, 10.0))
            + _absent_rows(lane="bench"))
    bench, sim = verdict(rows)
    assert sim.lane == "sim" and sim.passed is True, sim.reasons
    assert bench.lane == "bench" and bench.passed is False
    assert any(reason.startswith("lateral RMS 50.0 mm") for reason in bench.reasons)


def test_asking_for_one_lane_answers_for_that_lane_only():
    rows = (_grid_rows(lane="sim") + _absent_rows(lane="sim")
            + _grid_rows(lane="bench", lateral_error=0.05,
                         laterals=(-0.03, 0.0, 0.03),
                         yaws=(-10.0, 0.0, 10.0))
            + _absent_rows(lane="bench"))
    got = _only(rows, lane="sim")
    assert got.lane == "sim"
    assert got.passed is True, got.reasons
    assert _only(rows, lane="bench").passed is False


def test_a_lane_with_no_rows_is_a_failure_not_an_empty_answer():
    got = _only(_grid_rows(lane="sim") + _absent_rows(), lane="bench")
    assert got.passed is False
    assert any("no rows" in reason for reason in got.reasons), got.reasons


def test_an_unknown_lane_cannot_be_judged_against_a_per_lane_floor():
    # A blank lane is what a BOM used to produce, and the floors are declared
    # per lane, so there is nothing to check it against.
    rows = _grid_rows(lane="") + _absent_rows(lane="sim")
    got = verdict(rows)
    unknown = [one for one in got if one.lane == ""]
    assert unknown and unknown[0].passed is False
    assert any("unknown lane" in reason for reason in unknown[0].reasons)


def test_an_empty_table_fails_rather_than_returning_nothing():
    # `all(v.passed for v in verdict(rows))` is the natural shape and all(())
    # is True, so an empty table used to certify every candidate at once.
    got = verdict([])
    assert len(got) == 1
    assert got[0].passed is False
    assert any("nothing was measured" in reason for reason in got[0].reasons)
    assert all(one.passed for one in got) is False


def test_an_unknown_candidate_is_refused():
    got = _only([ProbeRow(lane="sim", candidate="crystal-ball", truth_x=0.5,
                          truth_y=0.0, truth_yaw=0.0)])
    assert got.passed is False
    assert got.reasons == ("unknown candidate",)


# --- the CSV and the verdict have to agree --------------------------------

def test_the_recorded_file_and_the_live_rows_reach_the_same_verdict(tmp_path):
    # append_row -> read_rows -> verdict, against verdict on the same rows in
    # memory. Everything the rig actually decides passes through this path,
    # and nothing tested it end to end: the blank-cell NaN that passed
    # silently only existed on the file side.
    rows = (_grid_rows(lane="bench", laterals=(-0.03, 0.0, 0.03),
                       yaws=(-10.0, 0.0, 10.0))
            + _absent_rows(lane="bench"))
    path = tmp_path / "bench.csv"
    for row in rows:
        append_row(path, row)

    from_file = verdict(read_rows(path))
    live = verdict(rows)
    assert [(one.candidate, one.lane, one.passed, one.reasons) for one in from_file] \
        == [(one.candidate, one.lane, one.passed, one.reasons) for one in live]
    for recorded, expected in zip(from_file, live):
        assert recorded.metrics == pytest.approx(expected.metrics)
    assert live[0].passed is True, live[0].reasons


# --- intensity ------------------------------------------------------------

def _intensity_rows(target=200.0, baseline=40.0, count=12, lane="bench"):
    return [ProbeRow(lane=lane, candidate="intensity",
                     truth_x=0.2 + index * 0.05, truth_y=0.0, truth_yaw=0.0,
                     int_target=target, int_baseline=baseline)
            for index in range(count)]


def test_separated_intensity_passes():
    got = _only(_intensity_rows())
    assert got.candidate == "intensity"
    assert got.passed is True, got.reasons


def test_a_constant_intensity_field_fails_the_candidate():
    # The rviz snapshot in the tree shows min == max == 47, so this is the
    # outcome the design expects if sllidar reports quality and not reflectance.
    got = _only(_intensity_rows(target=47.0, baseline=47.0))
    assert got.passed is False
    assert any(reason.startswith("retro and matte overlap at ")
               for reason in got.reasons), got.reasons


def test_an_empty_room_row_is_not_binned_as_if_the_dock_were_there():
    rows = _intensity_rows()
    rows.append(ProbeRow(lane="bench", candidate="intensity",
                         dock_present=False, truth_x=0.30, truth_y=math.nan,
                         truth_yaw=math.nan, int_target=41.0,
                         int_baseline=300.0))
    got = _only(rows)
    assert got.passed is True, got.reasons


def test_the_intensity_bin_is_not_wide_enough_to_merge_two_distances():
    # The overlap test compares min(target) against max(baseline) inside one
    # bin, so a wider bin is a STRICTER test: it pairs one distance's target
    # with another distance's baseline. That is why this constant is separate
    # from the envelope walk's step limit -- widening one used to tighten the
    # other silently.
    rows = [ProbeRow(lane="bench", candidate="intensity", truth_x=0.20,
                     truth_y=0.0, truth_yaw=0.0, int_target=120.0,
                     int_baseline=100.0),
            ProbeRow(lane="bench", candidate="intensity", truth_x=0.25,
                     truth_y=0.0, truth_yaw=0.0, int_target=400.0,
                     int_baseline=130.0)]
    got = _only(rows)
    assert got.passed is True, got.reasons
    assert got.metrics["worst_margin"] == pytest.approx(20.0)


def test_intensity_with_no_usable_rows_fails():
    got = _only([ProbeRow(lane="bench", candidate="intensity", truth_x=0.3,
                          truth_y=0.0, truth_yaw=0.0)])
    assert got.passed is False
    assert got.reasons == ("no dock-present rows carry both a target and a "
                           "baseline",)


# --- IR -------------------------------------------------------------------

#: A well-behaved sensor: the skew rises with truth_y and never inverts.
FINE_SKEWS = (-150, -100, -50, 0, 50, 100, 150)
#: The same sensor reporting coarse integer counts. Zero inversions, but it
#: ties near centre because the quantum is larger than the ruler step.
COARSE_SKEWS = (-100, -100, -50, -50, 0, 0, 0, 50, 50, 100, 100)
#: Well outside the ±20 mm baseline the geometry reverses. Those rows are not
#: part of the measurement, and the band is what keeps them out.
FAR_ROWS = ((-0.15, 400), (-0.10, 200), (0.10, -200), (0.15, -400))


def _ir_rows(band="indoor", skews=FINE_SKEWS, onsets=(0.12,), lane="bench",
             floor=100, respond=180, respond_mid=None, far=FAR_ROWS):
    rows = [ProbeRow(lane=lane, candidate="ir", dock_present=False,
                     truth_x=math.nan, truth_y=math.nan, truth_yaw=math.nan,
                     ambient=band, ir_l=floor, ir_mid=floor, ir_r=floor)
            for _ in range(4)]
    span = 0.040 / (len(skews) - 1)
    for index, skew in enumerate(skews):
        lateral = round(-0.020 + index * span, 5)
        # The dock to the robot's left (+y) lights the left channel more, so
        # (ir_l - ir_r) must RISE with truth_y. Getting this sign backwards is
        # what a real wiring swap looks like, and the verdict has to catch it.
        rows.append(ProbeRow(lane=lane, candidate="ir", truth_x=0.03,
                             truth_y=lateral, truth_yaw=0.0, ambient=band,
                             ir_l=600 + skew, ir_mid=800, ir_r=600 - skew))
    for lateral, skew in far:
        rows.append(ProbeRow(lane=lane, candidate="ir", truth_x=0.03,
                             truth_y=lateral, truth_yaw=0.0, ambient=band,
                             ir_l=600 + skew, ir_mid=800, ir_r=600 - skew))
    middle = respond + 40 if respond_mid is None else respond_mid
    for distance in onsets:
        rows.append(ProbeRow(lane=lane, candidate="ir", truth_x=distance,
                             truth_y=0.0, truth_yaw=0.0, ambient=band,
                             ir_l=respond, ir_mid=middle, ir_r=respond))
    return rows


def test_a_rising_ir_skew_passes():
    got = _only(_ir_rows())
    assert got.candidate == "ir"
    assert got.passed is True, got.reasons
    assert got.metrics["onset_m_indoor"] >= 0.12
    assert got.metrics["no_inversion_share_indoor"] == 1.0


def test_a_sensor_that_only_ties_near_centre_is_not_a_direction_failure():
    # Coarse integer counts tie in the middle of the band. Charging a tie as
    # an inversion failed a sensor with zero inversions at 36% of pairs, and
    # the reason said "monotonic in only 36% of pairs", which is not what
    # went wrong.
    got = _only(_ir_rows(skews=COARSE_SKEWS))
    assert got.passed is True, got.reasons
    assert got.metrics["no_inversion_share_indoor"] == 1.0


def test_an_inverted_ir_skew_fails_and_the_reason_names_the_inversion():
    got = _only(_ir_rows(skews=tuple(reversed(FINE_SKEWS)), far=()))
    assert got.passed is False
    assert any(reason.startswith("indoor: skew inverts in 100% of the ")
               for reason in got.reasons), got.reasons


def test_a_flat_ir_skew_says_the_skew_never_moved():
    # A dead channel is not a direction failure either; it is no measurement.
    got = _only(_ir_rows(skews=(0, 0, 0, 0, 0), far=()))
    assert got.passed is False
    assert "indoor: skew never moved across the band" in got.reasons


def test_the_lateral_band_keeps_out_readings_that_are_not_the_measurement():
    # Widen the band and the reversed far-field rows join the denominator,
    # which is exactly how a band that is too wide fails a good sensor.
    inside = _only(_ir_rows())
    assert inside.metrics["no_inversion_share_indoor"] == 1.0
    wide = _only(_ir_rows(skews=(-100, -50, 0, 50, 100)))
    assert wide.passed is True, wide.reasons


def test_characterising_the_onset_at_many_distances_does_not_fail_the_skew():
    # The IR arm demands both measurements: skew across the band, and the
    # distance at which the sensor starts responding. The onset rows sit at
    # truth_y = 0, so without a contact band they all landed in the skew
    # denominator with diff 0 -- five onset distances failed the candidate,
    # eight failed it harder, and the operator could not see why.
    for count in (1, 5, 8):
        onsets = tuple(0.12 + step * 0.02 for step in range(count))
        got = _only(_ir_rows(onsets=onsets))
        assert got.passed is True, (count, got.reasons)
        assert got.metrics["no_inversion_share_indoor"] == 1.0


def test_an_onset_inside_the_contact_tolerance_fails():
    got = _only(_ir_rows(onsets=(0.02,)))
    assert got.passed is False
    assert (f"indoor: onset 30 mm inside the {IR_ONSET_MIN_M * 1000:.0f} mm "
            f"contact tolerance") in got.reasons


def test_a_sensor_that_never_responded_says_so_instead_of_reporting_zero():
    # "onset 0 mm inside the 50 mm contact tolerance" reads like a range
    # problem. What happened is that nothing ever rose above ambient.
    rows = [row for row in _ir_rows()
            if not row.dock_present]
    rows += [ProbeRow(lane="bench", candidate="ir", truth_x=0.03,
                      truth_y=round(-0.020 + index * 0.01, 5), truth_yaw=0.0,
                      ambient="indoor", ir_l=100 + index, ir_mid=100,
                      ir_r=100 - index)
             for index in range(5)]
    got = _only(rows)
    assert got.passed is False
    assert any("the sensor never responded" in reason
               for reason in got.reasons), got.reasons
    assert not any("contact tolerance" in reason for reason in got.reasons)
    assert math.isnan(got.metrics["onset_m_indoor"])


def test_a_reading_barely_above_the_ambient_floor_is_not_a_response():
    # The floor is a plain max over a handful of ambient rows, so the true
    # ambient ceiling is above it -- and a LARGER onset PASSES. Without a
    # margin, two counts of noise at 0.30 m buys the pass; with it, the onset
    # falls back to the nearest real response and the candidate fails.
    got = _only(_ir_rows(onsets=(0.30,), respond=102, respond_mid=102))
    assert got.metrics["onset_m_indoor"] == pytest.approx(0.03)
    assert got.passed is False
    assert (f"indoor: onset 30 mm inside the {IR_ONSET_MIN_M * 1000:.0f} mm "
            f"contact tolerance") in got.reasons


def test_ir_without_an_ambient_band_is_refused():
    rows = [ProbeRow(lane="bench", candidate="ir", truth_x=0.03, truth_y=0.0,
                     truth_yaw=0.0, ir_l=600, ir_mid=800, ir_r=600)]
    got = _only(rows)
    assert got.passed is False
    assert got.reasons == ("no ambient band recorded",)


def test_ir_without_dock_absent_rows_has_no_ambient_floor():
    rows = [row for row in _ir_rows() if row.dock_present]
    got = _only(rows)
    assert got.passed is False
    assert "indoor: no dock-absent rows to set the ambient floor" in got.reasons


def test_the_brightest_band_can_fail_on_its_own():
    # The verdict is decided by the brightest band: a detector that collapses
    # in sunlight is unusable on a dock by a window.
    rows = _ir_rows(band="dim") + _ir_rows(band="direct-sun", onsets=(0.02,))
    got = _only(rows)
    assert got.passed is False
    assert any(reason.startswith("direct-sun: onset") for reason in got.reasons)
    assert not any(reason.startswith("dim:") for reason in got.reasons)


def test_a_verdict_is_a_value_and_not_an_exception():
    # House style: failures come back as values. Nothing in this module
    # raises on a measurement outcome, only on a file it cannot parse.
    got = _only(_grid_rows(acquires=(9.0, 9.0)))
    assert isinstance(got, ProbeVerdict)
    assert got.reasons
