"""FOR-001 대형 → 슬롯 오프셋. 좌표 규약은 rosy_core.navigation.swarm.follow_goal 과 같다:
distance 는 리더 뒤(+), lateral 은 리더 왼쪽(+). 리더는 슬롯 0 이며 목록에 없다."""

import math

import pytest

from rosy_fleet.formation.geometry import (
    MIN_SPACING,
    Formation,
    FormationError,
    SlotOffset,
    slot_world_position,
    slots,
)


def _close(a: SlotOffset, b: tuple[float, float]) -> bool:
    return math.isclose(a.distance, b[0], abs_tol=1e-9) and math.isclose(a.lateral, b[1], abs_tol=1e-9)


def test_column_stacks_behind_the_leader():
    got = slots(Formation.COLUMN, 3, 0.5)
    assert [(s.distance, s.lateral) for s in got] == [(0.5, 0.0), (1.0, 0.0), (1.5, 0.0)]


def test_line_alternates_left_then_right_beside_the_leader():
    got = slots(Formation.LINE, 3, 0.5)
    assert [(s.distance, s.lateral) for s in got] == [(0.0, 0.5), (0.0, -0.5), (0.0, 1.0)]


def test_v_opens_behind_the_leader_alternating_sides():
    got = slots(Formation.V, 2, 0.5)
    assert [(s.distance, s.lateral) for s in got] == [(0.5, 0.5), (0.5, -0.5)]


def test_grid_fills_rows_of_grid_cols_with_the_leader_at_front_left():
    got = slots(Formation.GRID, 3, 0.5, grid_cols=2)
    # 인덱스 0 은 리더 (row 0, col 0). k=1 → (0, col 1) 오른쪽, k=2 → 다음 행 왼쪽, k=3 → 그 오른쪽.
    assert [(s.distance, s.lateral) for s in got] == [(0.0, -0.5), (0.5, 0.0), (0.5, -0.5)]


def test_circle_puts_the_leader_on_the_ring_and_keeps_the_chord_equal_to_spacing():
    s = 0.5
    got = slots(Formation.CIRCLE, 3, s)
    r = s / (2 * math.sin(math.pi / 4))
    assert _close(got[0], (r, r))            # θ = 90°
    assert _close(got[1], (2 * r, 0.0))      # θ = 180°
    assert _close(got[2], (r, -r))           # θ = 270°
    # 인접 현 길이가 spacing 이다 — 두 로봇 사이 직선 거리가 안전 하한을 넘어야 하므로.
    ring = [(0.0, 0.0)] + [(p.distance, p.lateral) for p in got]
    for a, b in zip(ring, ring[1:] + ring[:1]):
        assert math.isclose(math.dist(a, b), s, abs_tol=1e-9)


def test_follow_is_exactly_one_slot_behind():
    assert slots(Formation.FOLLOW, 1, 0.7) == [SlotOffset(0.7, 0.0)]


@pytest.mark.parametrize("bad", [MIN_SPACING - 0.01, 0.0, -1.0, float("inf"), float("nan")])
def test_spacing_below_the_floor_is_refused(bad):
    with pytest.raises(FormationError):
        slots(Formation.COLUMN, 2, bad)


def test_follow_refuses_more_than_one_follower():
    with pytest.raises(FormationError):
        slots(Formation.FOLLOW, 2, 0.6)


@pytest.mark.parametrize("followers", [0, -1])
def test_a_formation_needs_at_least_one_follower(followers):
    with pytest.raises(FormationError):
        slots(Formation.LINE, followers, 0.6)


def test_grid_refuses_zero_columns():
    with pytest.raises(FormationError):
        slots(Formation.GRID, 2, 0.6, grid_cols=0)


def test_slot_world_position_matches_follow_goal_convention():
    # 리더 (1, 2) 가 +y 를 본다. 뒤 1 m 는 (1, 1), 왼쪽 1 m 는 -x 쪽 (0, 2).
    behind = slot_world_position(SlotOffset(1.0, 0.0), 1.0, 2.0, math.pi / 2)
    left = slot_world_position(SlotOffset(0.0, 1.0), 1.0, 2.0, math.pi / 2)
    assert math.isclose(behind[0], 1.0, abs_tol=1e-9) and math.isclose(behind[1], 1.0, abs_tol=1e-9)
    assert math.isclose(left[0], 0.0, abs_tol=1e-9) and math.isclose(left[1], 2.0, abs_tol=1e-9)
