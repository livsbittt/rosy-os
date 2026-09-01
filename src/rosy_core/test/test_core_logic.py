"""순수 로직 단위 테스트 — 중재/워치독/안전/웨이포인트/이벤트/네비 (ROS 무의존)."""

import time

import pytest

from rosy_core.command.arbitration import Mode, ModeMachine, Priority, SourceRegistry
from rosy_core.command.manager import CommandManager, Twist
from rosy_core.events.bus import EventBus
from rosy_core.navigation.manager import NavigationManager, NavGoalSpec
from rosy_core.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits
from rosy_core.state.manager import StateManager
from rosy_core.waypoints.manager import Waypoint, WaypointManager


@pytest.fixture
def bus():
    return EventBus("rosy_01", buffer_size=8)


@pytest.fixture
def safety(bus):
    return SafetyManager(
        SpeedLimits(max_linear=0.20, max_angular=0.80, manual_linear=0.15, manual_angular=0.60),
        BatteryPolicy(), events=bus,
    )


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
        from rosy_core.waypoints.manager import WaypointManager
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
        nav.goal(nav.resolve_goal(x=1.0, y=1.0))
        nav.on_goal_accepted()
        import rosy_core.navigation.manager as nm
        nm.time.monotonic = lambda: 0.0                               # 동일 시각 고정
        nav.on_pose_progress(0.0, 0.0)
        nm.time.monotonic = lambda: 1.0                               # 진척 없이 시간 경과
        nav.on_pose_progress(0.0, 0.0)
        assert nav.nav_state.value == "CANCELED"                       # NAV-006
        assert "nav.stuck" in [ev.type for ev in bus.history()]
