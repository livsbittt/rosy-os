"""Probe rows and the verdict that picks a detector (design: 2026-09-07 rig)."""

from __future__ import annotations

import math

from rosy_core.docking.probe import FIELDS, ProbeRow, append_row, read_rows


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
