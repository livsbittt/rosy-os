"""Probe rows and the verdict that picks a detector (design: 2026-09-07 rig)."""

from __future__ import annotations

import math

import pytest

from rosy_core.docking.probe import (FIELDS, LATERAL_RMS_MAX_M,
                                     ProbeFormatError, ProbeRow, append_row,
                                     read_rows)


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


def _intensity_rows(target=200.0, baseline=40.0, count=12):
    return [ProbeRow(lane="bench", candidate="intensity",
                     truth_x=0.2 + index * 0.05, truth_y=0.0, truth_yaw=0.0,
                     int_target=target, int_baseline=baseline)
            for index in range(count)]


def test_separated_intensity_passes():
    got = verdict(_intensity_rows())
    assert got[0].candidate == "intensity"
    assert got[0].passed is True, got[0].reasons


def test_a_constant_intensity_field_fails_the_candidate():
    # The rviz snapshot in the tree shows min == max == 47, so this is the
    # outcome the design expects if sllidar reports quality and not reflectance.
    got = verdict(_intensity_rows(target=47.0, baseline=47.0))
    assert got[0].passed is False
    assert any("overlap" in reason for reason in got[0].reasons)


def _ir_rows(band="indoor", monotonic=True, onset_x=0.12):
    rows = []
    # ambient floor, measured with no dock in front of the sensors
    for index in range(4):
        rows.append(ProbeRow(lane="bench", candidate="ir", dock_present=False,
                             truth_x=math.nan, truth_y=math.nan,
                             truth_yaw=math.nan, ambient=band,
                             ir_l=100, ir_mid=100, ir_r=100))
    for index in range(9):
        lateral = -0.020 + index * 0.005
        skew = int(lateral * 20000) if monotonic else 0
        # The dock to the robot's left (+y) lights the left channel more, so
        # (ir_l - ir_r) must RISE with truth_y. Getting this sign backwards is
        # what a real wiring swap looks like, and the verdict has to catch it.
        rows.append(ProbeRow(lane="bench", candidate="ir", truth_x=0.03,
                             truth_y=lateral, truth_yaw=0.0, ambient=band,
                             ir_l=600 + skew, ir_mid=800, ir_r=600 - skew))
    rows.append(ProbeRow(lane="bench", candidate="ir", truth_x=onset_x,
                         truth_y=0.0, truth_yaw=0.0, ambient=band,
                         ir_l=140, ir_mid=180, ir_r=140))
    return rows


def test_a_monotonic_ir_skew_passes():
    got = verdict(_ir_rows())
    assert got[0].candidate == "ir"
    assert got[0].passed is True, got[0].reasons
    assert got[0].metrics["onset_m_indoor"] >= 0.12


def test_a_flat_ir_skew_fails_because_it_cannot_tell_left_from_right():
    got = verdict(_ir_rows(monotonic=False))
    assert got[0].passed is False
    assert any("monotonic" in reason for reason in got[0].reasons)


def test_an_onset_inside_the_contact_tolerance_fails():
    got = verdict(_ir_rows(onset_x=0.02))
    assert got[0].passed is False
    assert any("onset" in reason for reason in got[0].reasons)
