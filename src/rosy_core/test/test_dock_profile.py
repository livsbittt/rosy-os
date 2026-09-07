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
