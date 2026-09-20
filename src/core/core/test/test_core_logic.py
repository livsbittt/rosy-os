"""순수 로직 단위 테스트 — 중재/워치독/안전/웨이포인트/이벤트/네비 (ROS 무의존)."""

import time

import pytest

from core_features.command.arbitration import Mode, ModeMachine, Priority, SourceRegistry
from core_features.command.manager import CommandManager, Twist
from core_events.events.bus import EventBus
from core_features.navigation.manager import NavigationManager, NavGoalSpec
from core_features.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits
from core_features.state.manager import StateManager
from core_features.waypoints.manager import Waypoint, WaypointManager


@pytest.fixture
def bus():
    return EventBus("rosy_01", buffer_size=8)


@pytest.fixture
def safety(bus):
    return SafetyManager(
        SpeedLimits(max_linear=0.20, max_angular=0.80, manual_linear=0.15, manual_angular=0.60),
        BatteryPolicy(), events=bus,
    )


def test_speed_limits_from_config_prefer_profile_then_yaml():
    class Profile:
        max_linear_velocity = 0.21
        max_angular_velocity = 0.81

    limits = SpeedLimits.from_config(
        profile=Profile(),
        nav_cfg={"max_linear_velocity": 0.10, "max_angular_velocity": 0.20},
        safety_cfg={
            "manual_linear": 0.05,
            "manual_angular": 0.07,
            "fleet_linear": 0.09,
            "fleet_angular": 0.11,
        },
    )
    assert limits.max_linear == 0.21
    assert limits.max_angular == 0.81
    assert limits.manual_linear == 0.05
    assert limits.fleet_linear == 0.09

    class Empty:
        max_linear_velocity = None
        max_angular_velocity = None

    fallback = SpeedLimits.from_config(
        profile=Empty(),
        nav_cfg={"max_linear_velocity": 0.20, "max_angular_velocity": 0.80},
        safety_cfg={},
    )
    assert fallback.max_linear == 0.20
    assert fallback.fleet_linear == 0.20


class TestArbitration:
    def test_registry_rejects_unknown_source(self):
        reg = SourceRegistry()
        assert reg.is_active_source("manual")
        assert not reg.is_active_source("evil")

    def test_mode_transitions(self):
        m = ModeMachine()
        assert m.transition(Mode.MANUAL)[0]
        assert m.transition(Mode.NAVIGATION)[0]
        assert m.transition(Mode.EMERGENCY)[0]
        assert not m.transition(Mode.NAVIGATION)[0]      # EMERGENCY에서 NAV 불가
        assert m.release_emergency()[0]
        assert m.mode is Mode.IDLE

    def test_docking_reserved_disabled(self):
        reg = SourceRegistry({"manual": 3, "navigation": 5})
        assert reg.priority_of("docking") is None


class TestCommandManager:
    def _make(self, bus, safety):
        reg = SourceRegistry()
        modes = ModeMachine()
        modes.transition(Mode.MANUAL)
        return CommandManager(reg, modes, safety, events=bus), modes

    def test_manual_blocks_nav_and_vice_versa(self, bus, safety):
        cmd, _ = self._make(bus, safety)
        cmd.set_nav_twist(Twist(0.2, 0.0))
        assert cmd.select_output(now=time.monotonic()).linear == 0.0   # MANUAL 중 Nav 차단 (§8.1)

    def test_watchdog_zero_after_timeout(self, bus, safety):
        cmd, _ = self._make(bus, safety)
        ok, _ = cmd.teleop(0.1, 0.0)
        assert ok
        t0 = time.monotonic()
        assert cmd.select_output(now=t0).linear == pytest.approx(0.1)
        assert cmd.select_output(now=t0 + 0.6).linear == 0.0          # SAF-002 만료

    def test_navigation_twist_expires_instead_of_replaying_stale_motion(self, bus, safety):
        reg = SourceRegistry()
        modes = ModeMachine()
        modes.transition(Mode.NAVIGATION)
        cmd = CommandManager(reg, modes, safety, events=bus)
        t0 = time.monotonic()

        cmd.set_nav_twist(Twist(0.2, 0.0), now=t0)

        assert cmd.select_output(now=t0 + 0.1).linear == pytest.approx(0.2)
        assert cmd.select_output(now=t0 + 0.6).linear == 0.0

    def test_teleop_rejected_outside_manual(self, bus, safety):
        reg = SourceRegistry()
        modes = ModeMachine()
        cmd = CommandManager(reg, modes, safety, events=bus)
        ok, code = cmd.teleop(0.1, 0.0)
        assert not ok and code == "MODE_CONFLICT"

    def test_estop_blocks_everything(self, bus, safety):
        cmd, modes = self._make(bus, safety)
        safety.trigger_estop("test")
        ok, code = cmd.teleop(0.1, 0.0)
        assert not ok and code == "EMERGENCY_ACTIVE"
        cmd.set_nav_twist(Twist(0.2, 0.0))
        assert cmd.select_output(now=time.monotonic()).linear == 0.0

    def test_speed_clipping(self, bus, safety):
        cmd, _ = self._make(bus, safety)
        cmd.teleop(5.0, 99.0)
        assert cmd.select_output(now=time.monotonic()).linear == pytest.approx(0.15)
        assert cmd.select_output(now=time.monotonic()).angular == pytest.approx(0.60)


class TestSafety:
    def test_estop_events(self, bus, safety):
        assert safety.trigger_estop("web")
        assert not safety.trigger_estop("web")          # 중복 무시
        events = bus.history()
        assert events[-1].type == "safety.estop" and events[-1].severity.value == "critical"
        safety.release(by="admin")
        assert bus.history()[-1].type == "safety.estop_released"

    def test_battery_policy_crossing(self, bus, safety):
        assert safety.on_battery_percent(50) is None
        assert safety.on_battery_percent(15) == "warn"  # 임계 통과 시 1회
        assert safety.on_battery_percent(12) is None
        assert safety.on_battery_percent(9) == "RETURN_HOME"
        types = [e.type for e in bus.history()]
        assert "battery.low" in types and "battery.critical" in types


class TestPersonAdvisory:
    """SAF-006: 사람은 metric 정지의 확대 사유다. YOLO advisory는 속도 상한만
    낮추고, 못 보면 기존 정지가 그대로이며, 사라지면 프로필로 복귀한다."""

    def _advisory(self, safety, now, **kwargs):
        from core_features.safety.manager import PersonAdvisory
        options = dict(present=True, confidence=0.9, observed_at=now, max_age_s=1.0)
        options.update(kwargs)
        advisory = PersonAdvisory(**options)
        safety.set_person_advisory(advisory)
        return advisory

    def test_no_advisory_leaves_clip_unchanged(self, safety):
        assert safety.clip(0.20, 0.50) == (pytest.approx(0.20), pytest.approx(0.50))

    def test_fresh_person_caps_linear_only(self, safety):
        now = time.monotonic()
        self._advisory(safety, now)
        linear, angular = safety.clip(0.20, 0.50, now=now)
        assert linear == pytest.approx(0.05)
        assert angular == pytest.approx(0.50)   # 선회율은 손대지 않는다

    def test_below_cap_passes_through(self, safety):
        now = time.monotonic()
        self._advisory(safety, now)
        assert safety.clip(0.03, 0.10, now=now)[0] == pytest.approx(0.03)

    def test_stale_advisory_is_ignored(self, safety):
        now = time.monotonic()
        self._advisory(safety, now - 2.0)       # max_age 1.0 s 초과
        assert safety.clip(0.20, 0.50, now=now)[0] == pytest.approx(0.20)

    def test_absent_person_is_ignored(self, safety):
        now = time.monotonic()
        self._advisory(safety, now, present=False)
        assert safety.clip(0.20, 0.50, now=now)[0] == pytest.approx(0.20)

    def test_cleared_advisory_restores_profile(self, safety):
        now = time.monotonic()
        self._advisory(safety, now)
        assert safety.clip(0.20, 0.50, now=now)[0] == pytest.approx(0.05)
        safety.set_person_advisory(None)        # 사람 소멸 → 자동 복귀
        assert safety.clip(0.20, 0.50, now=now)[0] == pytest.approx(0.20)

    def test_advisory_never_raises_the_cap(self, safety):
        """낮추기만 한다 — session cap과 같은 규칙. min() 구조라 위로 못 간다."""
        now = time.monotonic()
        self._advisory(safety, now)
        assert safety.clip(0.20, 0.50, now=now)[0] <= 0.20

    def test_bad_advisory_is_rejected(self, safety):
        from core_features.safety.manager import PersonAdvisory
        with pytest.raises(ValueError):
            safety.set_person_advisory(PersonAdvisory(
                present=True, confidence=1.5, observed_at=0.0, max_age_s=1.0))
        with pytest.raises(ValueError):
            safety.set_person_advisory(PersonAdvisory(
                present=True, confidence=0.9, observed_at=0.0, max_age_s=0.0))
        with pytest.raises(ValueError):
            safety.set_person_advisory("person!")


class TestPersonAdvisoryFromEvidence:
    """D-137 T2→SAF-006 주입 고리: 신선한 person 검출만 자문이 된다.
    revision 게이트(known-model registry)는 vision 슬라이스 몫 — 여기 없음."""

    def _evidence(self, **kwargs):
        from core_common.protocol.detections import Detection, DetectionEvidence
        detections = kwargs.pop("detections", [
            Detection(label="person", x=0.4, y=0.3, w=0.2, h=0.4, confidence=0.8)])
        options = dict(model_revision="yolo11n-r1", observed_at=1000.0, seq=41,
                       input_width=640, input_height=640, input_fps=10.0,
                       detections=detections)
        options.update(kwargs)
        return DetectionEvidence(**options)

    def test_fresh_person_becomes_advisory(self, safety):
        from core_features.safety.manager import person_advisory_from
        advisory = person_advisory_from(self._evidence(), now=1000.1)
        assert advisory is not None and advisory.present
        safety.set_person_advisory(advisory)
        assert safety.clip(0.20, 0.0, now=1000.1)[0] == pytest.approx(0.05)

    def test_stale_evidence_becomes_nothing(self, safety):
        from core_features.safety.manager import person_advisory_from
        assert person_advisory_from(self._evidence(), now=1001.0) is None

    def test_absence_becomes_nothing(self, safety):
        from core_features.safety.manager import person_advisory_from
        assert person_advisory_from(self._evidence(detections=[]), now=1000.1) is None

    def test_low_confidence_person_becomes_nothing(self, safety):
        from core_common.protocol.detections import Detection
        from core_features.safety.manager import person_advisory_from
        ev = self._evidence(detections=[
            Detection(label="person", x=0.4, y=0.3, w=0.2, h=0.4, confidence=0.2)])
        assert person_advisory_from(ev, now=1000.1) is None


class TestEventBus:
    def test_seq_monotone_and_history(self, bus):
        bus.publish("nav.completed")
        bus.publish("safety.estop", severity="critical")
        assert bus.last_seq == 2
        assert [e.seq for e in bus.history(since_seq=1)] == [2]

    def test_ring_buffer(self, bus):
        for i in range(12):
            bus.publish(f"e{i}")
        assert len(bus.history()) == 8                   # EVT-004 링 버퍼


class TestWaypoints:
    def test_crud_and_home(self, bus, tmp_path):
        wm = WaypointManager(tmp_path / "wp.json", events=bus)
        wm.create(Waypoint(name="zone_a", x=1.0, y=2.0, map_id="m1"))
        wm.create(Waypoint(name="__home__", x=0.0, y=0.0))
        with pytest.raises(Exception):
            wm.create(Waypoint(name="zone_a", x=3.0, y=0.0))        # WAYPOINT_EXISTS
        reloaded = WaypointManager(tmp_path / "wp.json")
        assert reloaded.get("zone_a").x == 1.0                        # 영속화 (D-9)
        wm.delete("zone_a")
        with pytest.raises(Exception):
            reloaded_after = WaypointManager(tmp_path / "wp.json")
            reloaded_after.get("zone_a")


class FakeExecutor:
    def __init__(self):
        self.sent, self.canceled = [], 0

    def send_goal(self, spec):
        self.sent.append(spec)

    def cancel_goal(self):
        self.canceled += 1

    def send_initial_pose(self, x, y, yaw):
        pass


class TestNavigation:
    def _make(self, bus, safety, tmp_path):
        from core_features.waypoints.manager import WaypointManager
        wm = WaypointManager(tmp_path / "wp.json")
        wm.create(Waypoint(name="dock_1", x=2.5, y=1.8, yaw=1.57, map_id="m1"))
        state = StateManager("rosy_01")
        nav = NavigationManager(bus, state, wm, safety)
        nav.executor = FakeExecutor()
        return nav, state, wm

    def test_goal_via_waypoint_and_map_mismatch(self, bus, safety, tmp_path):
        nav, state, _ = self._make(bus, safety, tmp_path)
        state.set_map_id("m1")
        nav.goal(nav.resolve_goal(waypoint="dock_1"))
        assert nav.nav_state.value == "PLANNING"
        state.set_map_id("other_map")
        with pytest.raises(Exception) as e:
            nav.goal(nav.resolve_goal(waypoint="dock_1"))
        assert e.value.code == "MAP_MISMATCH"                          # MAP-002

    def test_lifecycle_and_events(self, bus, safety, tmp_path):
        nav, _, _ = self._make(bus, safety, tmp_path)
        nav.goal(nav.resolve_goal(x=1.0, y=1.0))
        nav.on_goal_accepted()
        assert nav.nav_state.value == "NAVIGATING"
        with pytest.raises(Exception) as e:
            nav.goal(nav.resolve_goal(x=2.0, y=2.0))
        assert e.value.code == "NAVIGATION_ACTIVE"
        nav.on_result(True)
        assert nav.nav_state.value == "ARRIVED"
        types = [ev.type for ev in bus.history()]
        assert "nav.started" in types and "nav.completed" in types

    def test_stuck_detection(self, bus, safety, tmp_path):
        nav, _, _ = self._make(bus, safety, tmp_path)
        nav._stuck_timeout = 0.05
        # NAV-006 의 시계는 주입된다(브리지가 ROS 시계를 끼운다). 모듈의 `time.monotonic`
        # 을 몽키패치해도 이제 매니저는 그것을 보지 않는다.
        now = [0.0]
        nav.clock = lambda: now[0]
        nav.goal(nav.resolve_goal(x=1.0, y=1.0))
        nav.on_goal_accepted()
        nav.on_pose_progress(0.0, 0.0)
        now[0] = 1.0                                                   # 진척 없이 시간 경과
        nav.on_pose_progress(0.0, 0.0)
        assert nav.nav_state.value == "CANCELED"                       # NAV-006
        assert "nav.stuck" in [ev.type for ev in bus.history()]


def test_manual_active_reports_a_live_teleop_session():
    """도킹 복귀는 수동 조작 중이면 미뤄야 한다 (MANUAL 3 > DOCKING 4).
    그 판정에 쓸 신호가 CommandManager 에 있어야 한다."""
    from core_features.command.arbitration import Mode, ModeMachine, SourceRegistry
    from core_features.command.manager import CommandManager
    from core_features.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits

    safety = SafetyManager(SpeedLimits(), BatteryPolicy())
    modes = ModeMachine()
    command = CommandManager(SourceRegistry(), modes, safety)

    assert command.manual_active is False
    modes.transition(Mode.MANUAL)
    accepted, reason = command.teleop(0.1, 0.0)
    assert accepted, reason
    assert command.manual_active is True
    command.clear_manual()
    assert command.manual_active is False
