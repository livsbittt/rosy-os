"""NAV-007 lane following — classical CV line error plus loss tracking.

A floor lane is a bright line on a dark floor. This subject turns a BGR frame
into a lateral error; a tracker turns the error stream into TRACKING/LOST.
Loss beyond the grace period means stop (`nav.lane_lost`) — never a blind
search drive. YOLO is not involved by design (SRS NAV-007).
"""

import numpy as np
import pytest

from control.sensing.lane import (
    LANE_MAX_LINEAR_M_S,
    LaneObservation,
    LaneTracker,
    detect_lane_error,
)


def _lane_frame(offset_px: int = 0, width: int = 320, height: int = 240,
                line_px: int = 8) -> np.ndarray:
    """Dark floor, one bright vertical lane."""
    frame = np.full((height, width, 3), 40, dtype=np.uint8)
    cx = width // 2 + offset_px
    frame[:, max(0, cx - line_px // 2):cx + line_px // 2] = 230
    return frame


def test_centred_lane_reads_zero_error():
    obs = detect_lane_error(_lane_frame())
    assert isinstance(obs, LaneObservation)
    assert obs.error == pytest.approx(0.0, abs=0.02)
    assert 0.0 < obs.confidence <= 1.0


def test_right_lane_reads_positive_error():
    """Lane right of centre means steer right: error > 0, bounded to [-1, 1]."""
    obs = detect_lane_error(_lane_frame(offset_px=60))
    assert obs is not None
    assert obs.error == pytest.approx(60.0 / 160.0, abs=0.05)
    assert -1.0 <= obs.error <= 1.0


def test_left_lane_reads_negative_error():
    obs = detect_lane_error(_lane_frame(offset_px=-60))
    assert obs is not None
    assert obs.error < 0.0


def test_blank_floor_is_no_lane_not_a_guess():
    frame = np.full((240, 320, 3), 40, dtype=np.uint8)
    assert detect_lane_error(frame) is None


def test_lane_speed_cap_is_a_crawl():
    assert LANE_MAX_LINEAR_M_S == pytest.approx(0.10)


def test_centred_lane_commands_no_turn():
    from control.sensing.lane import steer_correction
    assert steer_correction(0.0) == pytest.approx(0.0)


def test_right_lane_commands_right_turn():
    """오차 + (차선 우측) → 우회전 = 음각속도 (ROS CCW+)."""
    from control.sensing.lane import steer_correction
    assert steer_correction(0.5, max_angular=1.0) == pytest.approx(-0.5)


def test_steering_saturates_at_max_angular():
    from control.sensing.lane import steer_correction
    assert steer_correction(1.0, gain=2.0, max_angular=0.4) == pytest.approx(-0.4)
    assert steer_correction(-1.0, gain=2.0, max_angular=0.4) == pytest.approx(0.4)


def test_bad_steering_gains_fail_closed():
    from control.sensing.lane import steer_correction
    with pytest.raises(ValueError):
        steer_correction(0.5, gain=-1.0)
    with pytest.raises(ValueError):
        steer_correction(float("inf"))
    # 범위 밖 오차는 던지지 않고 클램프한다 — 센서 글리치가 던지면 주행 중 정지다.
    assert steer_correction(2.0, max_angular=1.0) == pytest.approx(-1.0)


class TestLaneTracker:
    def _tracker(self, now=None):
        clock = now if now is not None else [1000.0]
        return LaneTracker(clock=lambda: clock[0] if isinstance(clock, list) else clock), clock

    def test_observations_track(self):
        tracker, _ = self._tracker()
        tracker.update(detect_lane_error(_lane_frame()), at=1000.0)
        assert tracker.state == "TRACKING"
        assert not tracker.stop_demanded(at=1001.0)

    def test_brief_gap_does_not_stop(self):
        tracker, _ = self._tracker()
        tracker.update(detect_lane_error(_lane_frame()), at=1000.0)
        tracker.update(None, at=1001.0)
        assert tracker.state == "TRACKING"
        assert not tracker.stop_demanded(at=1002.0)

    def test_loss_beyond_grace_demands_stop(self):
        """SRS: 3 s 상실이면 정지 + `nav.lane_lost`. 자동 재탐색 주행 없음."""
        tracker, _ = self._tracker()
        tracker.update(detect_lane_error(_lane_frame()), at=1000.0)
        tracker.update(None, at=1001.0)
        assert tracker.stop_demanded(at=1004.1)
        assert tracker.state == "LOST"

    def test_reacquire_clears_the_loss(self):
        tracker, _ = self._tracker()
        tracker.update(detect_lane_error(_lane_frame()), at=1000.0)
        tracker.update(None, at=1002.5)
        assert not tracker.stop_demanded(at=1002.5)
        tracker.update(detect_lane_error(_lane_frame()), at=1002.6)
        assert tracker.state == "TRACKING"
        assert not tracker.stop_demanded(at=1005.0)   # 재목격 후 2.4 s — 유예 안

    def test_never_seen_is_not_lost(self):
        tracker = LaneTracker()
        assert tracker.state == "IDLE"
        assert not tracker.stop_demanded(at=9999.0)
