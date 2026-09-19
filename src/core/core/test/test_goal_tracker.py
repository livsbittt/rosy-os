"""Nav2 목표 세대 관리 (moving goal 이 깨뜨린 단일 핸들 전제).

핸들은 불투명한 객체다 — rclpy 없이 전부 확인할 수 있다.
"""

from __future__ import annotations

from core.bridge.goal_tracker import GoalTracker


def test_a_result_for_the_current_goal_is_current():
    tracker = GoalTracker()
    generation = tracker.opening()
    assert tracker.accepted(generation, "h1") is True

    assert tracker.finished(generation) is True
    assert tracker.live_count == 0


def test_a_result_for_a_superseded_goal_is_not_current():
    """선점된 목표의 abort 를 현재 목표의 실패로 읽으면 상태가 무너진다."""
    tracker = GoalTracker()
    first = tracker.opening()
    tracker.accepted(first, "h1")
    second = tracker.opening()
    tracker.accepted(second, "h2")

    assert tracker.finished(first) is False
    assert tracker.finished(second) is True


def test_an_acceptance_that_arrives_after_a_cancel_is_refused():
    """send 와 accept 사이의 취소 창. 등록해 버리면 아무도 못 거둔다."""
    tracker = GoalTracker()
    generation = tracker.opening()

    assert tracker.cancel_all() == []
    assert tracker.accepted(generation, "late") is False
    assert tracker.live_count == 0


def test_cancel_returns_every_live_handle_not_just_the_last():
    tracker = GoalTracker()
    for name in ("h1", "h2", "h3"):
        tracker.accepted(tracker.opening(), name)

    assert sorted(tracker.cancel_all()) == ["h1", "h2", "h3"]
    assert tracker.live_count == 0


def test_cancel_makes_every_outstanding_result_stale():
    tracker = GoalTracker()
    generation = tracker.opening()
    tracker.accepted(generation, "h1")

    tracker.cancel_all()

    assert tracker.finished(generation) is False


def test_a_rejection_is_current_only_for_the_latest_goal():
    tracker = GoalTracker()
    first = tracker.opening()
    second = tracker.opening()

    assert tracker.rejected(first) is False
    assert tracker.rejected(second) is True
