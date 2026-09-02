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
