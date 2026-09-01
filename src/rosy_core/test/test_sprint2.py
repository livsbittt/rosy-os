"""P1 2차 스프린트 단위 테스트 — 센서 스토어·진단 수집기·SLAM 세션·메트릭 API."""

import time

import pytest

from rosy_core.api.app import create_app
from rosy_core.diagnostics.collector import (
    DiagnosticsCollector,
    disk_provider,
    topic_freshness_provider,
    worst,
)
from rosy_core.navigation.manager import NavigationManager
from rosy_core.profile import RobotProfile
from rosy_core.protocol.schemas import HealthState
from rosy_core.services import CoreServices
from rosy_core.state.manager import StateManager
from rosy_core.waypoints.manager import WaypointManager

from rosy_core.events.bus import EventBus
from rosy_core.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits

import yaml
from pathlib import Path
from fastapi.testclient import TestClient


CONFIG_DIR = Path(__file__).parent.parent / "config"


@pytest.fixture
def bus():
    return EventBus("rosy_01", buffer_size=8)


@pytest.fixture
def safety(bus):
    return SafetyManager(
        SpeedLimits(max_linear=0.20, max_angular=0.80, manual_linear=0.15, manual_angular=0.60),
        BatteryPolicy(), events=bus,
    )


class TestSensorStore:
    def test_set_get_sensors(self):
        sm = StateManager("rosy_01")
        assert sm.get_sensor("lidar") is None
        sm.set_sensor("lidar", {"num_ranges": 360, "ranges": [1.0]})
        assert sm.get_sensor("lidar")["num_ranges"] == 360
        all_sensors = sm.get_sensors()
        assert "lidar" in all_sensors


class TestDiagnostics:
    def test_collector_ok_and_exception(self):
        dc = DiagnosticsCollector()
        dc.register("ok", lambda: HealthState.OK)
        dc.register("boom", lambda: 1 / 0)
        results = dc.collect()
        assert results["ok"] == HealthState.OK
        assert results["boom"] == HealthState.ERROR          # provider 예외 → ERROR
        assert dc.summary_health() == HealthState.ERROR

    def test_worst_ordering(self):
        assert worst([HealthState.OK, HealthState.WARNING]) == HealthState.WARNING
        assert worst([]) == HealthState.UNKNOWN

    def test_freshness_provider(self):
        last = time.monotonic()
        fresh = topic_freshness_provider(lambda: last, stale_s=60.0)
        assert fresh() == HealthState.OK
        stale = topic_freshness_provider(lambda: last - 10.0, stale_s=2.0)
        assert stale() == HealthState.ERROR
        unknown = topic_freshness_provider(lambda: 0.0)
        assert unknown() == HealthState.UNKNOWN

    def test_disk_provider_real(self):
        assert disk_provider("/")() in list(HealthState)      # 실 / 동작


class TestSlamSession:
    def _nav(self, tmp_path, bus, safety):
        state = StateManager("rosy_01")
        wm = WaypointManager(tmp_path / "wp.json")
        nav = NavigationManager(bus, state, wm, safety)
        nav.executor = FakeExecutor()
        return nav, state

    def test_session_lifecycle(self, tmp_path, bus, safety):
        nav, state = self._nav(tmp_path, bus, safety)
        nav.start_mapping()
        assert nav.mapping_active
        with pytest.raises(Exception) as e:                    # 세션 중 Goal 거부 (NAV-005)
            nav.goal(nav.resolve_goal(x=1.0, y=1.0))
        assert e.value.code == "MAPPING_ACTIVE"
        map_id = nav.save_map("warehouse")
        assert map_id == "warehouse:deadbeef"                  # FakeExecutor 발급 map_id
        assert state.map_id == map_id                           # MAP-001 보고 갱신
        assert "map.saved" in [ev.type for ev in bus.history()]
        nav.stop_mapping()
        assert not nav.mapping_active
        with pytest.raises(Exception) as e:                     # 세션 없는 save 거부
            nav.save_map("again")
        assert e.value.code == "VALIDATION_ERROR"

    def test_nav_active_blocks_mapping(self, tmp_path, bus, safety):
        nav, _ = self._nav(tmp_path, bus, safety)
        nav.goal(nav.resolve_goal(x=1.0, y=1.0))
        nav.on_goal_accepted()
        with pytest.raises(Exception) as e:
            nav.start_mapping()
        assert e.value.code == "NAVIGATION_ACTIVE"


class FakeExecutor:
    def send_goal(self, spec):
        pass

    def cancel_goal(self):
        pass

    def send_initial_pose(self, *a):
        pass

    def save_map(self, name):
        return f"{name}:deadbeef"


@pytest.fixture
def client(tmp_path):
    config = yaml.safe_load((CONFIG_DIR / "rosy_default.yaml").read_text(encoding="utf-8"))
    profile = RobotProfile.load(CONFIG_DIR / "profile.pinky_pro.yaml")
    caps = yaml.safe_load((CONFIG_DIR / "capabilities.yaml").read_text(encoding="utf-8"))
    services = CoreServices.build(config, profile, caps, tmp_path / "wp.json")
    services.nav.executor = FakeExecutor()
    return TestClient(create_app(config, services)), services


OPERATOR = {"Authorization": "Bearer rosy-dev-operator"}
VIEWER = {"Authorization": "Bearer rosy-dev-viewer"}


class TestNewApi:
    def test_sensors_endpoints(self, client):
        tc, svc = client
        svc.state.set_sensor("lidar", {"num_ranges": 10})
        assert tc.get("/api/v1/sensors", headers=VIEWER).json()["sensors"]["lidar"]["num_ranges"] == 10
        assert tc.get("/api/v1/sensors/lidar", headers=VIEWER).status_code == 200
        missing = tc.get("/api/v1/sensors/ghost", headers=VIEWER)
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"

    def test_slam_flow(self, client):
        tc, svc = client
        assert tc.post("/api/v1/slam/start", headers=OPERATOR).json()["mapping"] is True
        goal = tc.post("/api/v1/navigation/goal", json={"x": 1, "y": 1}, headers=OPERATOR)
        assert goal.status_code == 409 and goal.json()["error"]["code"] == "MAPPING_ACTIVE"
        saved = tc.post("/api/v1/slam/save", json={"name": "wh"}, headers=OPERATOR).json()
        assert saved["map_id"] == "wh:deadbeef"
        assert svc.state.map_id == "wh:deadbeef"
        assert tc.post("/api/v1/slam/stop", headers=OPERATOR).json()["mapping"] is False

    def test_metrics_prometheus(self, client):
        tc, _ = client
        r = tc.get("/metrics")
        assert r.status_code == 200
        assert "rosy_uptime_seconds" in r.text
        assert "rosy_events_published_total" in r.text
        assert "text/plain" in r.headers["content-type"]
