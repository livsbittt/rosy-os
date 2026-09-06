"""slam_toolbox reports success as 0. A truthiness test here is backwards.

The bridge has always had this right. It has never had a test saying so, and CI's
SaveMap guard checks the request type rather than how the reply is read — so an
inversion introduced during a refactor would ship, and the symptom is a robot
reporting a map it never wrote.
"""

from __future__ import annotations

import pytest

from rosy_core.bridge.save_map import SaveMapFailed, check_result


def test_zero_is_success():
    check_result(0)          # must not raise


@pytest.mark.parametrize("code", [1, 255])
def test_the_documented_failures_raise(code):
    """1 = no map to save, 255 = write failed."""
    with pytest.raises(SaveMapFailed) as raised:
        check_result(code)
    assert str(code) in str(raised.value)


def test_a_truthiness_test_would_invert_this():
    """Pins the trap directly: the only falsy code is the successful one."""
    assert bool(0) is False          # success, and falsy
    assert bool(1) is True           # failure, and truthy
    check_result(0)
    with pytest.raises(SaveMapFailed):
        check_result(1)


@pytest.mark.parametrize("code", [-1, 2, 3, 256])
def test_any_unknown_code_is_a_failure_not_a_success(code):
    with pytest.raises(SaveMapFailed):
        check_result(code)
