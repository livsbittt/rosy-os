"""`travelled_m` is the only thing undocking measures itself against.

No sensor confirms it. Wrong high and the robot stops before it is clear of the
dock; wrong low and it keeps reversing. It lived inline in `ros_bridge.py`,
which host pytest cannot import, so neither case had an assertion.
"""

from __future__ import annotations

import math

from rosy_core.bridge.odometry import travelled_m


def test_distance_is_straight_line_from_the_mark():
    assert travelled_m((1.0, 1.0), (4.0, 5.0)) == 5.0


def test_direction_does_not_matter():
    assert travelled_m((4.0, 5.0), (1.0, 1.0)) == 5.0


def test_no_mark_reads_as_no_progress():
    """The safe direction: the caller waits instead of concluding it is clear."""
    assert travelled_m(None, (4.0, 5.0)) == 0.0


def test_no_current_pose_reads_as_no_progress():
    assert travelled_m((1.0, 1.0), None) == 0.0


def test_standing_still_is_zero_not_noise():
    assert travelled_m((2.5, -1.25), (2.5, -1.25)) == 0.0


def test_a_reverse_along_one_axis_measures_that_axis():
    """The undocking case: negative displacement is still positive distance."""
    assert travelled_m((0.0, 0.0), (-0.35, 0.0)) == 0.35


def test_diagonal_drift_is_included():
    assert travelled_m((0.0, 0.0), (0.3, 0.4)) == 0.5
    assert math.isclose(travelled_m((0.0, 0.0), (1.0, 1.0)), math.sqrt(2))
