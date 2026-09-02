"""DNC-001~003 도킹 단위 테스트 — 주입 클럭 기반 순수 로직.

설계: docs/plans/2026-09-02-docking-station-design.md
"""

import json
import math

import pytest

from rosy_core.docking.database import (
    DockDatabase,
    DockError,
    DockInstance,
    DockType,
)


class FakeClock:
    """단조 시계 대역 — 테스트가 시간을 명시적으로 전진시킨다."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


def a_dock(**kwargs) -> DockInstance:
    options = dict(
        id="dock_1",
        type="rosy_v1",
        x=2.5, y=1.8, yaw=0.0,
        map_id="warehouse_a",
        agent_url="http://10.0.0.50",
    )
    options.update(kwargs)
    return DockInstance(**options)


# --- DockType: 기종 (인스턴스와 분리) -----------------------------------------

class TestDockType:
    def test_a_type_carries_the_detector_and_approach_configuration(self):
        dock_type = DockType(name="rosy_v1", detector="simulated",
                             staging_offset_m=0.7, docking_threshold_m=0.05,
                             max_retries=3)
        assert dock_type.detector == "simulated"
        assert dock_type.staging_offset_m == pytest.approx(0.7)
        assert dock_type.max_retries == 3

    def test_the_staging_offset_must_be_positive(self):
        """스테이징은 도크 *앞* 이다. 0이나 음수면 도크 안이나 뒤를 가리킨다."""
        with pytest.raises(ValueError):
            DockType(name="bad", detector="simulated", staging_offset_m=0.0)
        with pytest.raises(ValueError):
            DockType(name="bad", detector="simulated", staging_offset_m=-0.5)

    def test_two_instances_share_one_type(self):
        """설계 §"1:1 구현, 스키마는 풀" — 기종 하나에 도크 여럿."""
        db = DockDatabase.empty()
        db.add_type(DockType(name="rosy_v1", detector="simulated"))
        db.add(a_dock(id="dock_1"))
        db.add(a_dock(id="dock_2", x=9.0))
        assert db.type_of("dock_1") is db.type_of("dock_2")


# --- DockInstance: 개체 --------------------------------------------------------

class TestDockInstance:
    def test_an_instance_carries_pose_map_and_agent_address(self):
        dock = a_dock()
        assert (dock.x, dock.y, dock.yaw) == (2.5, 1.8, 0.0)
        assert dock.map_id == "warehouse_a"
        assert dock.agent_url == "http://10.0.0.50"

    def test_the_staging_pose_is_derived_not_stored(self):
        """가르친 도크 포즈가 낡은 스테이징 포즈를 남기면 안 된다."""
        dock = a_dock(x=2.0, y=0.0, yaw=0.0)
        staging = dock.staging_pose(offset_m=0.7)
        # yaw=0 이면 도크는 +X를 향하고, 스테이징은 그 앞(−X 쪽 0.7 m)이다.
        assert staging.x == pytest.approx(1.3)
        assert staging.y == pytest.approx(0.0)
        # 스테이징에서 도크를 바라봐야 하므로 yaw 는 도크와 같다.
        assert staging.yaw == pytest.approx(0.0)

    def test_the_staging_pose_follows_the_dock_orientation(self):
        dock = a_dock(x=0.0, y=0.0, yaw=math.pi / 2)      # 도크가 +Y를 향한다
        staging = dock.staging_pose(offset_m=1.0)
        assert staging.x == pytest.approx(0.0, abs=1e-9)
        assert staging.y == pytest.approx(-1.0)

    def test_teaching_replaces_the_pose_and_the_staging_follows(self):
        dock = a_dock(x=2.0, y=0.0, yaw=0.0)
        assert dock.staging_pose(0.5).x == pytest.approx(1.5)
        dock = dock.taught_at(x=5.0, y=1.0, yaw=0.0, map_id="warehouse_a")
        assert dock.staging_pose(0.5).x == pytest.approx(4.5)
        assert dock.y == pytest.approx(1.0)

    def test_teaching_records_the_map_it_was_taught_on(self):
        dock = a_dock(map_id="warehouse_a").taught_at(
            x=1.0, y=1.0, yaw=0.0, map_id="warehouse_b")
        assert dock.map_id == "warehouse_b"

    def test_an_id_is_required(self):
        with pytest.raises(ValueError):
            a_dock(id="")


# --- 맵 일치 (MAP-002) ---------------------------------------------------------

class TestMapGuard:
    def test_a_dock_on_another_map_is_rejected(self):
        """resolve_goal 이 waypoint 를 거부하는 방식과 같아야 한다."""
        dock = a_dock(map_id="warehouse_a")
        with pytest.raises(DockError) as excinfo:
            dock.require_map("warehouse_b")
        assert excinfo.value.code == "MAP_MISMATCH"

    def test_a_matching_map_passes(self):
        a_dock(map_id="warehouse_a").require_map("warehouse_a")

    def test_a_dock_with_no_map_is_not_map_checked(self):
        """맵 없이 운용하는 구성(teleop 전용)을 막지 않는다."""
        a_dock(map_id=None).require_map("warehouse_a")

    def test_an_unknown_current_map_does_not_block(self):
        a_dock(map_id="warehouse_a").require_map(None)


# --- DockDatabase --------------------------------------------------------------

class TestDockDatabase:
    def test_it_is_keyed_by_id(self, tmp_path):
        db = DockDatabase.empty()
        db.add_type(DockType(name="rosy_v1", detector="simulated"))
        db.add(a_dock(id="dock_1"))
        assert db.get("dock_1").id == "dock_1"

    def test_an_unknown_id_raises_not_found(self):
        db = DockDatabase.empty()
        with pytest.raises(DockError) as excinfo:
            db.get("nope")
        assert excinfo.value.code == "NOT_FOUND"

    def test_a_duplicate_id_is_refused(self):
        db = DockDatabase.empty()
        db.add_type(DockType(name="rosy_v1", detector="simulated"))
        db.add(a_dock(id="dock_1"))
        with pytest.raises(DockError) as excinfo:
            db.add(a_dock(id="dock_1"))
        assert excinfo.value.code == "DOCK_EXISTS"

    def test_a_dock_of_an_unregistered_type_is_refused(self):
        """기종 없이 개체만 있으면 검출기를 고를 수 없다."""
        db = DockDatabase.empty()
        with pytest.raises(DockError) as excinfo:
            db.add(a_dock(type="ghost"))
        assert excinfo.value.code == "UNKNOWN_DOCK_TYPE"

    def test_it_round_trips_through_json(self, tmp_path):
        path = tmp_path / "docks.json"
        db = DockDatabase(path)
        db.add_type(DockType(name="rosy_v1", detector="simulated",
                             staging_offset_m=0.65))
        db.add(a_dock(id="dock_1"))
        db.add(a_dock(id="dock_2", x=9.0, agent_url="http://10.0.0.51"))

        reloaded = DockDatabase(path)
        assert {d.id for d in reloaded.list()} == {"dock_1", "dock_2"}
        assert reloaded.get("dock_2").agent_url == "http://10.0.0.51"
        assert reloaded.type_of("dock_1").staging_offset_m == pytest.approx(0.65)

    def test_the_file_is_human_readable_beside_waypoints(self, tmp_path):
        path = tmp_path / "docks.json"
        db = DockDatabase(path)
        db.add_type(DockType(name="rosy_v1", detector="simulated"))
        db.add(a_dock())
        document = json.loads(path.read_text(encoding="utf-8"))
        assert set(document) == {"dock_types", "docks"}

    def test_teaching_persists(self, tmp_path):
        path = tmp_path / "docks.json"
        db = DockDatabase(path)
        db.add_type(DockType(name="rosy_v1", detector="simulated"))
        db.add(a_dock(id="dock_1", x=2.0))
        db.teach("dock_1", x=7.0, y=3.0, yaw=1.57, map_id="warehouse_a")
        assert DockDatabase(path).get("dock_1").x == pytest.approx(7.0)

    def test_teaching_an_unknown_dock_raises(self, tmp_path):
        db = DockDatabase(tmp_path / "docks.json")
        with pytest.raises(DockError):
            db.teach("nope", x=0.0, y=0.0, yaw=0.0, map_id=None)

    def test_removing_a_dock_persists(self, tmp_path):
        path = tmp_path / "docks.json"
        db = DockDatabase(path)
        db.add_type(DockType(name="rosy_v1", detector="simulated"))
        db.add(a_dock(id="dock_1"))
        db.remove("dock_1")
        assert DockDatabase(path).list() == []

    def test_an_empty_store_loads_without_a_file(self, tmp_path):
        assert DockDatabase(tmp_path / "missing.json").list() == []

    def test_the_single_dock_shortcut_for_the_one_to_one_deployment(self, tmp_path):
        """구현은 1:1 이다 — "그 도크"를 이름 없이 물을 수 있어야 한다."""
        db = DockDatabase.empty()
        db.add_type(DockType(name="rosy_v1", detector="simulated"))
        assert db.only() is None
        db.add(a_dock(id="dock_1"))
        assert db.only().id == "dock_1"
        db.add(a_dock(id="dock_2"))
        assert db.only() is None            # 둘 이상이면 골라줄 수 없다


# --- 검출기 경계 (감지 방식은 스펙 B 뒤로 유보) --------------------------------

class TestDockObservation:
    def test_it_carries_a_relative_pose_and_a_timestamp(self):
        from rosy_core.docking.detector import DockObservation
        obs = DockObservation(x=0.42, y=-0.03, yaw=0.01, confidence=0.9, at=1000.0)
        assert (obs.x, obs.y) == (0.42, -0.03)
        assert obs.confidence == pytest.approx(0.9)
        assert obs.at == 1000.0

    def test_the_range_is_the_planar_distance_to_the_dock(self):
        from rosy_core.docking.detector import DockObservation
        obs = DockObservation(x=0.3, y=0.4, yaw=0.0, confidence=1.0, at=0.0)
        assert obs.range_m == pytest.approx(0.5)

    def test_confidence_is_bounded(self):
        from rosy_core.docking.detector import DockObservation
        with pytest.raises(ValueError):
            DockObservation(x=0.0, y=0.0, yaw=0.0, confidence=1.5, at=0.0)
        with pytest.raises(ValueError):
            DockObservation(x=0.0, y=0.0, yaw=0.0, confidence=-0.1, at=0.0)


class TestSimulatedDetector:
    def _detector(self, clock, **kwargs):
        from rosy_core.docking.detector import SimulatedDetector
        return SimulatedDetector(clock=clock, **kwargs)

    def test_it_reports_nothing_before_start(self, clock):
        detector = self._detector(clock, script=[(0.5, 0.0, 0.0)])
        assert detector.relative_pose() is None

    def test_it_replays_the_script_after_start(self, clock):
        detector = self._detector(clock, script=[(0.5, 0.0, 0.0), (0.3, 0.01, 0.0)])
        detector.start(a_dock())
        first = detector.relative_pose()
        assert first.x == pytest.approx(0.5)
        clock.advance(0.2)
        assert detector.relative_pose().x == pytest.approx(0.3)

    def test_the_last_scripted_pose_is_held(self, clock):
        detector = self._detector(clock, script=[(0.5, 0.0, 0.0), (0.05, 0.0, 0.0)])
        detector.start(a_dock())
        for _ in range(5):
            clock.advance(0.2)
            observation = detector.relative_pose()
        assert observation.x == pytest.approx(0.05)

    def test_it_reports_nothing_after_stop(self, clock):
        detector = self._detector(clock, script=[(0.5, 0.0, 0.0)])
        detector.start(a_dock())
        assert detector.relative_pose() is not None
        detector.stop()
        assert detector.relative_pose() is None

    def test_it_can_be_told_to_lose_the_dock(self, clock):
        detector = self._detector(clock, script=[(0.5, 0.0, 0.0)])
        detector.start(a_dock())
        assert detector.relative_pose() is not None
        detector.lose()
        assert detector.relative_pose() is None

    def test_it_never_acquires_when_the_script_is_empty(self, clock):
        detector = self._detector(clock, script=[])
        detector.start(a_dock())
        assert detector.relative_pose() is None

    def test_a_stale_observation_is_not_returned_as_current(self, clock):
        """마지막 목격을 계속 돌려주는 검출기는 잃어버린 도크를 확신 있는
        오답으로 바꾼다."""
        detector = self._detector(clock, script=[(0.5, 0.0, 0.0)],
                                  staleness_s=0.5)
        detector.start(a_dock())
        assert detector.relative_pose() is not None
        detector.freeze()                    # 새 표본이 끊긴 상황
        clock.advance(0.4)
        assert detector.relative_pose() is not None
        clock.advance(0.2)                   # 총 0.6s > staleness
        assert detector.relative_pose() is None

    def test_restarting_clears_the_previous_run(self, clock):
        detector = self._detector(clock, script=[(0.5, 0.0, 0.0), (0.3, 0.0, 0.0)])
        detector.start(a_dock())
        clock.advance(0.2)
        detector.relative_pose()
        detector.stop()
        detector.start(a_dock())
        assert detector.relative_pose().x == pytest.approx(0.5)

    def test_it_satisfies_the_detector_protocol(self, clock):
        from rosy_core.docking.detector import DockDetector
        assert isinstance(self._detector(clock, script=[]), DockDetector)


# --- 도크 에이전트 클라이언트 --------------------------------------------------
#
# 도크가 밀어넣지 않고 로봇이 폴링한다. 도크는 어느 로봇이 오는지 모르고,
# 로봇은 자기가 갈 도크를 안다. 그리고 Fleet 이 죽어도 충전은 되어야 한다.

import json as _json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _StubDock:
    """도크 에이전트 대역. body/status/delay 를 테스트가 지정한다."""

    def __init__(self, body=None, status=200, delay_s=0.0, raw=None):
        self.body = body
        self.status = status
        self.delay_s = delay_s
        self.raw = raw
        self.requests = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests += 1
                if outer.delay_s:
                    import time as _t
                    _t.sleep(outer.delay_s)
                payload = (outer.raw if outer.raw is not None
                           else _json.dumps(outer.body).encode())
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self):
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


HEALTHY = {
    "dock_id": "dock_1",
    "firmware": "1.0.0",
    "output_enabled": True,
    "load_present": True,
    "charging": True,
    "current_a": 1.42,
    "output_voltage_v": 8.31,
    "faults": [],
}


def an_agent(url, **kwargs):
    from rosy_core.docking.agent import DockAgent
    return DockAgent(url, timeout_s=kwargs.pop("timeout_s", 1.0), **kwargs)


class TestDockAgentHappyPath:
    def test_it_reads_the_documented_fields(self):
        from rosy_core.docking.agent import DockReachability
        with _StubDock(HEALTHY) as dock:
            status = an_agent(dock.url).poll()
        assert status.reachability is DockReachability.OK
        assert status.answered is True
        assert status.charging is True
        assert status.load_present is True
        assert status.current_a == pytest.approx(1.42)
        assert status.output_voltage_v == pytest.approx(8.31)
        assert status.dock_id == "dock_1"
        assert status.faults == ()

    def test_a_fault_list_comes_through(self):
        body = dict(HEALTHY, charging=False, current_a=0.0,
                    faults=["overtemp", "contact_open"])
        with _StubDock(body) as dock:
            status = an_agent(dock.url).poll()
        assert status.answered is True
        assert status.faults == ("overtemp", "contact_open")
        assert status.charging is False

    def test_load_present_and_charging_are_independent(self):
        """접점이 물렸는데 전류가 안 흐르는 상황은 접촉 실패와 다른 고장이다 —
        산화된 접점, 만충, 래치된 보호회로."""
        body = dict(HEALTHY, load_present=True, charging=False, current_a=0.0)
        with _StubDock(body) as dock:
            status = an_agent(dock.url).poll()
        assert status.load_present is True
        assert status.charging is False


class TestDockAgentFailures:
    """어느 경우에도 예외가 콜백으로 새면 안 되고, 각각이 서로 구분되어야 한다.
    상태머신이 "도크가 전류 없다고 답했다"와 "도크가 답을 안 했다"를 가르지
    못하면 재시도 전략을 세울 수 없다."""

    def test_a_dead_dock_is_not_an_exception(self):
        """거부냐 지연이냐는 OS 마다 다르고 상태머신도 구분할 필요가 없다.
        중요한 것은 답을 못 받았고, 그때 충전 중이 아니라는 것이다."""
        from rosy_core.docking.agent import DockReachability
        with _StubDock(HEALTHY) as dock:
            url = dock.url                      # 서버를 닫고 그 포트를 쓴다
        status = an_agent(url, timeout_s=0.3).poll()
        assert status.reachability in (DockReachability.UNREACHABLE,
                                       DockReachability.TIMEOUT)
        assert status.answered is False
        assert status.charging is False         # 모를 때는 충전 중이 아니다
        assert status.error is not None         # 왜 실패했는지는 남아야 한다

    def test_a_slow_dock_times_out_rather_than_hanging(self):
        from rosy_core.docking.agent import DockReachability
        with _StubDock(HEALTHY, delay_s=2.0) as dock:
            status = an_agent(dock.url, timeout_s=0.3).poll()
        assert status.reachability is DockReachability.TIMEOUT
        assert status.answered is False

    def test_the_client_never_blocks_longer_than_its_timeout(self):
        """이 폴링은 틱 안에서 돈다. 멎은 도크가 틱을 멈춰 세우면 안 된다."""
        import time as _t
        with _StubDock(HEALTHY, delay_s=3.0) as dock:
            started = _t.monotonic()
            an_agent(dock.url, timeout_s=0.3).poll()
            elapsed = _t.monotonic() - started
        assert elapsed < 1.5

    def test_a_non_200_is_a_bad_response(self):
        from rosy_core.docking.agent import DockReachability
        with _StubDock(HEALTHY, status=503) as dock:
            status = an_agent(dock.url).poll()
        assert status.reachability is DockReachability.BAD_RESPONSE
        assert status.answered is False

    def test_malformed_json_is_a_bad_response(self):
        from rosy_core.docking.agent import DockReachability
        with _StubDock(None, raw=b"{not json at all") as dock:
            status = an_agent(dock.url).poll()
        assert status.reachability is DockReachability.BAD_RESPONSE

    def test_a_non_object_body_is_a_bad_response(self):
        from rosy_core.docking.agent import DockReachability
        with _StubDock([1, 2, 3]) as dock:
            status = an_agent(dock.url).poll()
        assert status.reachability is DockReachability.BAD_RESPONSE

    def test_missing_charging_field_is_a_bad_response(self):
        """없는 필드를 False 로 채우면 "충전 안 됨"과 "말을 안 함"이 섞인다."""
        from rosy_core.docking.agent import DockReachability
        body = {k: v for k, v in HEALTHY.items() if k != "charging"}
        with _StubDock(body) as dock:
            status = an_agent(dock.url).poll()
        assert status.reachability is DockReachability.BAD_RESPONSE

    def test_optional_fields_may_be_absent(self):
        from rosy_core.docking.agent import DockReachability
        body = {"load_present": True, "charging": True}
        with _StubDock(body) as dock:
            status = an_agent(dock.url).poll()
        assert status.reachability is DockReachability.OK
        assert status.current_a is None
        assert status.faults == ()

    def test_no_url_means_no_dock_agent(self):
        from rosy_core.docking.agent import DockReachability
        status = an_agent(None).poll()
        assert status.reachability is DockReachability.UNREACHABLE
        assert status.answered is False


# --- 충전 확인: 독립된 두 소스 -------------------------------------------------
#
# LAN 의 어떤 장치가 charging:true 라고 우겨도 그것만으로 안전 경로를 끄지
# 못하게 한다. 이 판정이 D-27 deep 셧다운 억제의 입력이기 때문이다.

def a_status(**kwargs):
    from rosy_core.docking.agent import DockReachability, DockStatus
    options = dict(reachability=DockReachability.OK, load_present=True,
                   charging=True, current_a=1.4)
    options.update(kwargs)
    return DockStatus(**options)


def unreachable_status():
    from rosy_core.docking.agent import DockReachability, DockStatus
    return DockStatus(reachability=DockReachability.UNREACHABLE)


def a_confirmation(clock, **kwargs):
    from rosy_core.docking.charging import ChargingConfirmation
    options = dict(window_s=10.0, fall_tolerance_v=0.02)
    options.update(kwargs)
    return ChargingConfirmation(clock=clock, **options)


class TestChargingConfirmation:
    def test_nothing_is_confirmed_before_any_sample(self, clock):
        assert a_confirmation(clock).confirmed is False

    def test_a_dock_reporting_current_with_steady_voltage_confirms(self, clock):
        confirmation = a_confirmation(clock, window_s=10.0)
        for _ in range(12):
            clock.advance(1.0)
            confirmation.update(a_status(), voltage=7.60)
        assert confirmation.confirmed is True

    def test_a_dock_reporting_current_with_rising_voltage_confirms(self, clock):
        confirmation = a_confirmation(clock, window_s=10.0)
        voltage = 7.40
        for _ in range(12):
            clock.advance(1.0)
            voltage += 0.01
            confirmation.update(a_status(), voltage=voltage)
        assert confirmation.confirmed is True

    def test_a_dock_claiming_current_while_voltage_falls_is_rejected(self, clock):
        """도크가 거짓말을 하거나, 전류가 팩까지 도달하지 못하고 있다.
        어느 쪽이든 충전으로 인정하면 안 된다."""
        confirmation = a_confirmation(clock, window_s=10.0)
        voltage = 7.60
        for _ in range(12):
            clock.advance(1.0)
            voltage -= 0.02
            confirmation.update(a_status(), voltage=voltage)
        assert confirmation.confirmed is False

    def test_a_spoofed_dock_cannot_disable_a_safety_path_alone(self, clock):
        """설계의 핵심 방어 — 이 판정이 D-27 셧다운 억제의 입력이다."""
        confirmation = a_confirmation(clock, window_s=10.0)
        voltage = 6.60
        for _ in range(20):
            clock.advance(1.0)
            voltage -= 0.01                      # 팩은 계속 죽어간다
            confirmation.update(a_status(charging=True, current_a=99.0),
                                voltage=voltage)
        assert confirmation.confirmed is False

    def test_a_dock_reporting_no_current_is_not_confirmed(self, clock):
        confirmation = a_confirmation(clock, window_s=10.0)
        for _ in range(12):
            clock.advance(1.0)
            confirmation.update(a_status(charging=False, current_a=0.0),
                                voltage=7.60)
        assert confirmation.confirmed is False

    def test_an_unreachable_dock_is_not_confirmed_and_not_an_error(self, clock):
        confirmation = a_confirmation(clock, window_s=10.0)
        for _ in range(12):
            clock.advance(1.0)
            confirmation.update(unreachable_status(), voltage=7.60)
        assert confirmation.confirmed is False

    def test_confirmation_needs_the_whole_window(self, clock):
        """한두 표본으로 확정하면 접점이 스치기만 해도 충전으로 읽힌다."""
        confirmation = a_confirmation(clock, window_s=10.0)
        for _ in range(5):
            clock.advance(1.0)
            confirmation.update(a_status(), voltage=7.60)
        assert confirmation.confirmed is False
        for _ in range(6):
            clock.advance(1.0)
            confirmation.update(a_status(), voltage=7.60)
        assert confirmation.confirmed is True

    def test_it_survives_a_single_noisy_voltage_sample(self, clock):
        """전압 표본 한 발이 튀었다고 충전 판정이 무너지면 안 된다."""
        confirmation = a_confirmation(clock, window_s=10.0, fall_tolerance_v=0.05)
        for index in range(14):
            clock.advance(1.0)
            voltage = 7.60 - (0.03 if index == 6 else 0.0)
            confirmation.update(a_status(), voltage=voltage)
        assert confirmation.confirmed is True

    def test_losing_the_dock_drops_confirmation_at_once(self, clock):
        """확정은 창을 요구하지만 해제는 즉시다 — 안전한 방향으로 비대칭."""
        confirmation = a_confirmation(clock, window_s=10.0)
        for _ in range(12):
            clock.advance(1.0)
            confirmation.update(a_status(), voltage=7.60)
        assert confirmation.confirmed is True
        clock.advance(1.0)
        confirmation.update(a_status(charging=False, current_a=0.0), voltage=7.60)
        assert confirmation.confirmed is False

    def test_a_missing_voltage_does_not_confirm(self, clock):
        confirmation = a_confirmation(clock, window_s=10.0)
        for _ in range(12):
            clock.advance(1.0)
            confirmation.update(a_status(), voltage=None)
        assert confirmation.confirmed is False

    def test_reset_clears_the_window(self, clock):
        confirmation = a_confirmation(clock, window_s=10.0)
        for _ in range(12):
            clock.advance(1.0)
            confirmation.update(a_status(), voltage=7.60)
        assert confirmation.confirmed is True
        confirmation.reset()
        assert confirmation.confirmed is False
