"""Probe rows and the verdict that picks a detector (design: 2026-09-07 rig)."""

from __future__ import annotations

import math

from rosy_core.docking.probe import (FIELDS, LATERAL_RMS_MAX_M, ProbeRow,
                                     append_row, read_rows)


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
    for index in range(3):
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


from rosy_core.docking.probe import ProbeVerdict, verdict


def _geometry_rows(lateral_error=0.002, acquired=True, count=40):
    rows = []
    for index in range(count):
        truth_x = 0.70 - index * 0.005          # 0.70 down to 0.505
        truth_y = 0.01 if index % 2 else -0.01
        rows.append(ProbeRow(
            lane="sim", candidate="geometry", truth_x=truth_x,
            truth_y=truth_y, truth_yaw=0.0,
            fit_x=truth_x if acquired else None,
            fit_y=(truth_y + lateral_error) if acquired else None,
            fit_yaw=0.0 if acquired else None,
            residual=0.001, points=22, confidence=0.9))
    return rows


def _absent_rows(false_positives=0, count=20):
    rows = []
    for index in range(count):
        hit = index < false_positives
        rows.append(ProbeRow(
            lane="sim", candidate="geometry", dock_present=False,
            truth_x=math.nan, truth_y=math.nan, truth_yaw=math.nan,
            fit_x=0.5 if hit else None, fit_y=0.0 if hit else None))
    return rows


def test_a_clean_geometry_sweep_passes():
    got = verdict(_geometry_rows() + _absent_rows())
    assert len(got) == 1
    assert got[0].candidate == "geometry"
    assert got[0].passed is True, got[0].reasons
    assert got[0].metrics["lateral_rms_m"] < LATERAL_RMS_MAX_M


def test_lateral_error_over_the_gate_fails_and_says_so():
    got = verdict(_geometry_rows(lateral_error=0.018) + _absent_rows())
    assert got[0].passed is False
    assert any("lateral" in reason for reason in got[0].reasons)


def test_one_false_positive_fails_the_candidate():
    # Zero is the criterion. One confident wrong pose drives the robot into
    # something that is not the dock.
    got = verdict(_geometry_rows() + _absent_rows(false_positives=1))
    assert got[0].passed is False
    assert any("false positive" in reason for reason in got[0].reasons)
    assert got[0].metrics["false_positives"] == 1.0


def test_no_dock_absent_samples_is_a_failure_not_a_pass():
    # A sweep that never looked at an empty room has not tested the criterion.
    got = verdict(_geometry_rows())
    assert got[0].passed is False
    assert any("false positive" in reason for reason in got[0].reasons)


def test_a_sweep_that_never_acquires_fails_on_the_rate():
    got = verdict(_geometry_rows(acquired=False) + _absent_rows())
    assert got[0].passed is False
    assert got[0].metrics["acquire_rate"] == 0.0


def test_the_usable_envelope_lower_bound_is_reported():
    rows = _geometry_rows() + _absent_rows()
    # Everything closer than 0.30 m fails to acquire, which is what a real
    # envelope looks like: the posts leave the field of view.
    for index in range(30):
        truth_x = 0.30 - index * 0.008
        rows.append(ProbeRow(lane="sim", candidate="geometry", truth_x=truth_x,
                             truth_y=0.0, truth_yaw=0.0))
    got = verdict(rows)
    assert got[0].metrics["envelope_low_m"] >= 0.30
