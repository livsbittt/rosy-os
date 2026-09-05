"""추종이 실제 NavigationManager·목표 세대 관리와 만나는 지점.

기존 swarm 테스트는 전부 `FakeNav` 를 끼워 SwarmManager 만 본다. 리뷰가 잡아낸
결함 두 개(HOLD 취소가 Nav2 에 닿지 않음, NAV-006 무력화)는 정확히 그 사이 —
SwarmManager → NavigationManager → NavExecutor, 그리고 브리지가 되돌려주는
콜백 순서 — 에 살아 있었다. 여기서는 진짜 매니저를 쓰고 브리지 콜백을 재생한다.
"""

from __future__ import annotations

import math

import pytest
from rosy_core.bridge.goal_tracker import GoalTracker
from rosy_core.capability import Capability
from rosy_core.navigation.manager import NavGoalSpec, NavigationError, NavigationManager
from rosy_core.navigation.swarm import ReferencePose, SwarmError, SwarmManager
from rosy_core.protocol.schemas import NavigationState, SwarmFollowParams
from rosy_core.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits
from rosy_core.state.manager import StateManager


class FakeClock:
    def __init__(self) -> None:
        self.now = 500.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeEvents:
    def __init__(self) -> None:
        self.published = []

    def publish(self, type_, severity="info", source="", data=None):
        self.published.append((type_, data or {}))

    def types(self):
        return [t for t, _ in self.published]


class FakeHandle:
    def __init__(self, accepted: bool = True) -> None:
        self.accepted = accepted
        self.cancelled = False

    def cancel_goal_async(self):
        self.cancelled = True


class BridgeExecutor:
    """브리지가 하는 일을 rclpy 없이 재생한다.

    핵심은 Nav2 의 선점 의미다: 새 목표를 받으면 이전 목표는 **abort 로**
    끝나고, 그 결과 콜백이 뒤늦게 도착한다.
    """

    def __init__(self, nav: NavigationManager) -> None:
        self._nav = nav
        self.goals: list[NavGoalSpec] = []
        self.handles: list[FakeHandle] = []
        self.tracker = GoalTracker()
        self._pending: list[tuple[int, FakeHandle]] = []

    # --- NavExecutor -----------------------------------------------------------

    def send_goal(self, spec: NavGoalSpec) -> None:
        self.goals.append(spec)
        generation = self.tracker.opening()
        self._pending.append((generation, FakeHandle()))

    def cancel_goal(self) -> None:
        for handle in self.tracker.cancel_all():
            handle.cancel_goal_async()

    def send_initial_pose(self, x, y, yaw):
        pass

    def save_map(self, name):
        return "map"

    # --- 브리지 콜백 재생 --------------------------------------------------------

    def settle(self) -> None:
        """서버가 목표를 받아들이고, 선점된 이전 목표를 abort 로 끝낸다."""
        superseded = [item for item in self._pending[:-1]]
        newest = self._pending[-1:]
        self._pending = []
        for generation, handle in superseded + newest:
            self.handles.append(handle)
            if self.tracker.accepted(generation, handle):
                self._nav.on_goal_accepted()
            else:
                handle.cancel_goal_async()
        # Nav2 는 선점된 목표를 abort 로 종료한다. 결과는 뒤늦게 도착한다.
        for generation, _handle in superseded:
            if self.tracker.finished(generation):
                self._nav.on_result(False, "PREEMPTED")

    @property
    def cancelled_handles(self) -> int:
        return sum(1 for handle in self.handles if handle.cancelled)


def build():
    clock = FakeClock()
    events = FakeEvents()
    state = StateManager(robot_id="rosy_01")
    safety = SafetyManager(SpeedLimits(), BatteryPolicy(), events)

    class Waypoints:
        def get(self, name):
            raise KeyError(name)

    nav = NavigationManager(events, state, Waypoints(), safety, stuck_timeout_s=30.0)
    executor = BridgeExecutor(nav)
    nav.executor = executor
    docking = {"active": False}
    swarm = SwarmManager(events, state, nav, safety,
                         Capability({"swarm": {"follow": True, "lead": True}}),
                         clock=clock,
                         docking_active_provider=lambda: docking["active"])
    # services.py 와 같은 배선. 세션을 닫는 모든 길이 추종자에게 닿는다.
    nav.session_closed_listener = swarm.on_navigation_session_closed
    safety.estop_listeners.append(swarm.on_estop)
    return swarm, nav, executor, clock, events, safety, docking


def params(**overrides):
    body = {"target_robot_id": "rosy_02", "distance": 0.5, "lateral": 0.0}
    body.update(overrides)
    return SwarmFollowParams(**body)


def stream(swarm, executor, clock, x, *, settle=True):
    swarm.on_reference_pose(ReferencePose("rosy_02", x, 0.0, 0.0))
    if settle:
        executor.settle()
    clock.advance(0.5)


# --- HOLD 는 실제로 Nav2 목표를 거둬야 한다 -------------------------------------


def test_a_preempted_goal_result_does_not_move_the_navigation_state():
    """선점 abort 를 현재 목표의 실패로 읽으면 상태가 FAILED 로 떨어진다."""
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())

    stream(swarm, executor, clock, 1.0)
    stream(swarm, executor, clock, 2.0)

    assert len(executor.goals) == 2
    assert nav.nav_state is NavigationState.NAVIGATING


def test_hold_cancels_the_live_nav2_goal_even_after_a_preemption():
    """리뷰가 재현한 경로: 선점 결과가 FAILED 를 만들면 cancel 이 통째로 무시됐다."""
    swarm, nav, executor, clock, events, _safety, _docking = build()
    swarm.follow(params(stream_timeout_ms=1000))

    stream(swarm, executor, clock, 1.0)
    stream(swarm, executor, clock, 2.0)

    clock.advance(1.0)
    swarm.tick()

    assert "swarm.hold" in events.types()
    assert executor.cancelled_handles >= 1, "the goal must actually be withdrawn"
    assert swarm.active is True and swarm.holding is True


def test_cancel_reaches_nav2_from_any_navigation_state():
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)
    nav.on_result(False, "ABORTED")
    assert nav.nav_state is NavigationState.FAILED

    swarm.cancel()

    assert executor.cancelled_handles >= 1


def test_a_goal_cancelled_before_acceptance_is_still_cancelled():
    """send 와 accept 사이에 취소가 오면 핸들이 아직 없다. 놓치면 안 된다."""
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())
    swarm.on_reference_pose(ReferencePose("rosy_02", 1.0, 0.0, 0.0))

    swarm.cancel()
    executor.settle()

    assert nav.nav_state is not NavigationState.NAVIGATING
    assert executor.tracker.live_count == 0


# --- NAV-006 는 추종 중에도 살아 있어야 한다 (SWM-002) ---------------------------


def test_goal_replacement_does_not_reset_the_stuck_baseline():
    """0.5 초마다 기준점을 초기화하면 30 초 무진척 조건이 성립할 수 없다.

    예전 테스트는 루프 안에서 기준시각을 직접 조작하고 첫 이벤트에서 멈춰,
    조건이 성립한다는 것만 보이고 그 뒤 무한 반복은 보지 못했다. 여기서는
    기준점 자체가 목표 교체를 견디는지만 본다.
    """
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)
    nav.on_pose_progress(0.0, 0.0)
    baseline = nav._last_progress_ts

    for step in range(5):
        swarm.on_reference_pose(ReferencePose("rosy_02", 2.0 + step, 0.0, 0.0))
        executor.settle()
        clock.advance(0.5)

    assert nav._last_progress_ts == baseline
    assert nav._last_progress_pos == (0.0, 0.0)


def test_a_single_goal_still_resets_the_stuck_baseline():
    """추종 세션 밖에서는 기존 동작 그대로여야 한다."""
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    nav.goal(NavGoalSpec(1.0, 0.0, 0.0))
    executor.settle()
    nav.on_pose_progress(0.0, 0.0)
    marked = nav._last_progress_pos

    nav.cancel()
    nav.goal(NavGoalSpec(2.0, 0.0, 0.0))
    executor.settle()

    assert nav._last_progress_pos is None and marked is not None


# --- 소유권과 중재 ---------------------------------------------------------------


def test_an_operator_goal_during_a_follow_is_refused_not_silently_overwritten():
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)

    with pytest.raises(NavigationError) as raised:
        nav.goal(NavGoalSpec(9.0, 9.0, 0.0))

    assert raised.value.code == "NAVIGATION_ACTIVE"
    assert "swarm follow session" in str(raised.value)


def test_the_estop_ends_the_follow_and_release_alone_does_not_restart_it():
    """리뷰가 재현한 경로: 해제 뒤 참조 프레임 하나로 다시 달리기 시작했다."""
    swarm, nav, executor, clock, events, safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)

    safety.trigger_estop("operator")
    swarm.tick()

    assert swarm.active is False
    assert executor.cancelled_handles >= 1
    aborted = [data for type_, data in events.published if type_ == "swarm.aborted"]
    assert aborted and aborted[-1]["reason"] == "estop"

    safety.release("admin")
    before = len(executor.goals)
    swarm.on_reference_pose(ReferencePose("rosy_02", 5.0, 0.0, 0.0))

    assert len(executor.goals) == before, "a pose alone must not re-arm the follow"


def test_the_follow_yields_to_a_docking_run():
    """DOCKING(4) > NAVIGATION(5). SAF-005 저배터리 복귀가 이 경로로 간다."""
    swarm, nav, executor, clock, events, _safety, docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)

    docking["active"] = True
    swarm.tick()

    assert swarm.active is False
    aborted = [data for type_, data in events.published if type_ == "swarm.aborted"]
    assert aborted and aborted[-1]["reason"] == "docking"


def test_a_goal_that_lost_the_race_with_a_cancel_is_refused_by_navigation():
    """추종자가 자기 락을 쥔 채 nav 를 부르지 않아도 되는 이유.

    목표에는 세션 토큰이 붙는다. 취소가 먼저 도착하면 토큰이 닫히고, 뒤늦게
    도착한 목표는 nav 의 락 안에서 버려진다 — 아무도 거두지 않는 목표가
    남지 않는다.
    """
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)
    stale_session = nav._moving_session
    before = len(executor.goals)

    swarm.cancel()

    assert nav.moving_goal(NavGoalSpec(9.0, 9.0, 0.0), session=stale_session) is False
    assert len(executor.goals) == before


def test_a_goal_carrying_the_live_session_is_accepted():
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())

    assert nav.moving_goal(NavGoalSpec(1.0, 0.0, 0.0),
                           session=nav._moving_session) is True


def test_a_hold_keeps_the_session_open_so_the_stream_can_resume():
    """HOLD 는 목표만 거둔다. 세션까지 닫으면 돌아온 스트림이 거절당한다."""
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params(stream_timeout_ms=1000))
    stream(swarm, executor, clock, 1.0)

    clock.advance(1.0)
    swarm.tick()
    assert swarm.holding is True

    clock.advance(0.1)
    issued = swarm.on_reference_pose(ReferencePose("rosy_02", 3.0, 0.0, 0.0))

    assert issued is True
    assert executor.goals[-1].x == pytest.approx(2.5)


# --- NAV-006 는 추종을 끝낸다. 자동 재시도가 아니다 -------------------------------


def test_a_stuck_follower_ends_the_session_instead_of_retrying_forever():
    """리뷰가 재현한 경로: 취소하고 0.5 초 뒤 다시 목표를 내며 무한 반복했다."""
    swarm, nav, executor, clock, events, _safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)
    nav.on_pose_progress(0.0, 0.0)

    import time as _time
    nav._last_progress_ts = _time.monotonic() - 60.0
    nav.on_pose_progress(0.0, 0.0)

    assert "nav.stuck" in events.types()
    assert swarm.active is False, "the follow must end; retrying is the operator's call"
    aborted = [data for type_, data in events.published if type_ == "swarm.aborted"]
    assert aborted and aborted[-1]["reason"] == "stuck"

    # 리더가 계속 흘려도 다시 달리지 않는다.
    before = len(executor.goals)
    for step in range(5):
        swarm.on_reference_pose(ReferencePose("rosy_02", 10.0 + step, 0.0, 0.0))
        clock.advance(0.5)
    assert len(executor.goals) == before
    assert events.types().count("nav.stuck") == 1


def test_a_cancel_resets_the_stuck_baseline():
    """남겨 두면 다음 목표가 만료된 기준으로 곧장 다시 stuck 판정을 받는다."""
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    nav.goal(NavGoalSpec(1.0, 0.0, 0.0))
    executor.settle()
    nav.on_pose_progress(0.0, 0.0)
    import time as _time
    nav._last_progress_ts = _time.monotonic() - 60.0

    nav.cancel(source="test")

    assert nav._last_progress_pos is None
    assert nav._last_progress_ts > _time.monotonic() - 1.0


def test_the_formation_geometry_reaches_the_executor_unchanged():
    swarm, _nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params(distance=0.8, lateral=0.3))

    swarm.on_reference_pose(ReferencePose("rosy_02", 2.0, 1.0, math.pi / 2))

    spec = executor.goals[-1]
    assert spec.x == pytest.approx(2.0 - 0.3)
    assert spec.y == pytest.approx(1.0 - 0.8)
    assert spec.frame == "map"


# --- 도킹은 문 앞에서 막는다 -----------------------------------------------------


def test_a_follow_is_refused_while_a_docking_run_owns_navigation():
    """받아들인 뒤 다음 틱에 조용히 푸는 것은 거절보다 나쁘다."""
    swarm, _nav, _executor, _clock, _events, _safety, docking = build()
    docking["active"] = True

    with pytest.raises(SwarmError) as raised:
        swarm.follow(params())

    assert raised.value.code == "DOCKING_ACTIVE"
    assert swarm.active is False


def test_the_estop_listener_ends_the_follow_without_waiting_for_a_tick():
    swarm, _nav, executor, clock, events, safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)

    safety.trigger_estop("operator")

    assert swarm.active is False
    aborted = [data for type_, data in events.published if type_ == "swarm.aborted"]
    assert aborted and aborted[-1]["reason"] == "estop"


def test_an_operator_goal_stays_refused_while_the_follow_is_merely_holding():
    """HOLD 중이라고 목표의 임자가 바뀌지는 않는다 — 돌아온 스트림이 곧 덮는다."""
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params(stream_timeout_ms=1000))
    stream(swarm, executor, clock, 1.0)
    clock.advance(1.0)
    swarm.tick()
    assert swarm.holding is True

    with pytest.raises(NavigationError) as raised:
        nav.goal(NavGoalSpec(9.0, 9.0, 0.0))
    assert raised.value.code == "NAVIGATION_ACTIVE"


# --- A1: 세션을 닫는 길은 추종자 말고도 있다 -------------------------------------


def test_an_operator_navigation_cancel_ends_the_follow():
    """세션만 닫히고 추종이 남으면, 목표를 하나도 못 내면서 스냅샷에는
    active: true 로 보인다 — 참조가 계속 오니 스트림도 신선해 보인다."""
    swarm, nav, executor, clock, events, _safety, _docking = build()
    swarm.follow(params())
    stream(swarm, executor, clock, 1.0)

    nav.cancel(source="api:operator")

    assert swarm.active is False
    aborted = [data for type_, data in events.published if type_ == "swarm.aborted"]
    assert aborted and aborted[-1]["reason"] == "navigation_canceled"

    before = len(executor.goals)
    swarm.on_reference_pose(ReferencePose("rosy_02", 5.0, 0.0, 0.0))
    assert len(executor.goals) == before


def test_the_swarms_own_cancel_does_not_bounce_back_through_the_listener():
    swarm, _nav, _executor, clock, events, _safety, _docking = build()
    swarm.follow(params())

    swarm.cancel()

    assert [t for t, _ in events.published].count("swarm.aborted") == 1


def test_a_follow_never_outlives_its_session():
    """어느 길로 세션이 닫히든 추종 상태와 어긋나지 않는다."""
    for closer in ("api:operator", "mode:operator", "stuck_detector"):
        swarm, nav, _executor, clock, _events, _safety, _docking = build()
        swarm.follow(params())
        stream(swarm, nav.executor, clock, 1.0)

        nav.cancel(source=closer)

        assert swarm.active is False, closer
        assert nav._moving_session is None, closer
        assert swarm.state_payload()["active"] is False, closer


def test_a_refused_arming_leaves_no_session_behind():
    """세션을 여는 것과 무장은 한 구간이다.

    락 밖에서 열면 그 사이에 도착한 cancel 이 임자 없는 세션을 남기고,
    그러면 단발 목표가 영영 NAVIGATION_ACTIVE 로 거절당한다.
    """
    swarm, nav, executor, _clock, _events, safety, _docking = build()
    original = swarm.check_follow

    def trip(body):
        original(body)
        safety.trigger_estop("operator")

    swarm.check_follow = trip
    with pytest.raises(SwarmError):
        swarm.follow(params())

    assert nav._moving_session is None
    safety.release("admin")
    nav.goal(NavGoalSpec(1.0, 0.0, 0.0))
    assert executor.goals[-1].x == pytest.approx(1.0)


def test_a_stale_cancel_does_not_close_a_reissued_follow():
    """추종자가 락을 놓은 사이에 새 follow 가 무장하면, 옛 취소는 남의 세션이다."""
    swarm, nav, executor, clock, _events, _safety, _docking = build()
    swarm.follow(params())
    stale_session = nav._moving_session

    swarm.follow(params(distance=0.9))   # 새 세션
    nav.cancel(source="swarm", session=stale_session)

    assert swarm.active is True
    assert nav._moving_session is not None
    assert swarm.on_reference_pose(ReferencePose("rosy_02", 3.0, 0.0, 0.0)) is True


def test_an_estop_landing_during_arming_does_not_leave_a_follow_armed():
    """check_follow 와 무장 사이의 창. 무장 직전에 한 번 더 본다."""
    swarm, _nav, _executor, _clock, _events, safety, _docking = build()
    original = swarm.check_follow

    def trip(body):
        original(body)
        safety.trigger_estop("operator")

    swarm.check_follow = trip

    with pytest.raises(SwarmError) as raised:
        swarm.follow(params())

    assert raised.value.code == "EMERGENCY_ACTIVE"
    assert swarm.active is False
