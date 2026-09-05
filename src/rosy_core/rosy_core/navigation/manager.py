"""rosy_core.navigation.manager — NAV-001~004/006 (P1-7, P1-20). ROS 무의존.

실행(Nav2 액션)은 executor 인터페이스 뒤로 격리 — bridge가 구현 (ROS-101/HWA-002 원칙).
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Optional, Protocol

from rosy_core.protocol.schemas import NavigationState


@dataclass
class NavGoalSpec:
    x: float
    y: float
    yaw: float
    frame: str = "map"


class NavExecutor(Protocol):
    def send_goal(self, spec: NavGoalSpec) -> None: ...
    def cancel_goal(self) -> None: ...
    def send_initial_pose(self, x: float, y: float, yaw: float) -> None: ...
    def save_map(self, name: str) -> str: ...   # map_id 반환 (D-13, 브리지가 체크섬/대체 해시 산출)


class NavigationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_IDLE_STATES = {NavigationState.IDLE, NavigationState.ARRIVED,
                NavigationState.CANCELED, NavigationState.FAILED}


class NavigationManager:
    def __init__(self, events, state_manager, waypoints, safety,
                 map_id_provider=None, stuck_timeout_s: float = 30.0,
                 stuck_min_progress: float = 0.05) -> None:
        self._events = events
        self._state = state_manager
        self._waypoints = waypoints
        self._safety = safety
        self._map_id_provider = map_id_provider or (lambda: self._state.map_id)
        self.executor: Optional[NavExecutor] = None
        self._nav_state = NavigationState.IDLE
        self.mapping_active = False
        self._stuck_timeout = stuck_timeout_s
        self._stuck_min_progress = stuck_min_progress
        self._last_progress_pos: Optional[tuple[float, float]] = None
        self._last_progress_ts: float = 0.0
        # 목표는 uvicorn 워커(REST·WS)와 rclpy executor(브리지 타이머) 양쪽에서
        # 건드려진다(D-1). check-send-set 이 쪼개지면 취소가 목표를 놓친다.
        self._lock = threading.RLock()
        #: moving goal 세션이 잡혀 있으면 목표의 임자는 그쪽이다 (SWM-001).
        self._moving_session = False

    @property
    def nav_state(self) -> NavigationState:
        return self._nav_state

    def _set_state(self, new: NavigationState) -> None:
        if new is not self._nav_state:
            self._nav_state = new
            self._state.set_navigation(new)

    def _require_executor(self) -> NavExecutor:
        if self.executor is None:
            raise NavigationError("CAPABILITY_NOT_SUPPORTED", "navigation executor unavailable")
        return self.executor

    def resolve_goal(self, *, x=None, y=None, yaw=None, waypoint=None) -> NavGoalSpec:
        if waypoint is not None:
            wp = self._waypoints.get(waypoint)
            current_map = self._map_id_provider()
            if wp.map_id and current_map and wp.map_id != current_map:
                raise NavigationError("MAP_MISMATCH",
                                      f"waypoint map '{wp.map_id}' != current '{current_map}'")
            return NavGoalSpec(x=wp.x, y=wp.y, yaw=wp.yaw)
        if x is None or y is None:
            raise NavigationError("VALIDATION_ERROR", "x,y or waypoint required")
        return NavGoalSpec(x=float(x), y=float(y), yaw=float(yaw or 0.0))

    def goal(self, spec: NavGoalSpec, source: str = "api") -> None:
        executor = self._require_executor()
        if self._safety.estop:
            raise NavigationError("EMERGENCY_ACTIVE", "e-stop is active")
        if self.mapping_active:
            raise NavigationError("MAPPING_ACTIVE", "mapping session active")
        with self._lock:
            if self._moving_session:
                # 추종 중에 들어온 단발 목표는 0.5 초 뒤 스트림에 덮인다.
                # 조용히 덮이느니 거절하는 편이 낫다.
                raise NavigationError("NAVIGATION_ACTIVE",
                                      "a swarm follow session owns the goal — cancel it first")
            if self._nav_state not in _IDLE_STATES:
                raise NavigationError(
                    "NAVIGATION_ACTIVE",
                    f"navigation in progress ({self._nav_state.value}) — cancel first")
            executor.send_goal(spec)
            self._set_state(NavigationState.PLANNING)
        self._events.publish("nav.started", source="navigation_manager",
                             data={"goal": {"x": spec.x, "y": spec.y, "yaw": spec.yaw}, "by": source})

    def moving_goal(self, spec: NavGoalSpec, source: str = "swarm") -> None:
        """SWM-001: 이미 주행 중이어도 목표를 갈아끼운다.

        `goal()` 은 진행 중인 주행을 NAVIGATION_ACTIVE 로 막는다 — 운영자가
        실수로 목표를 덮어쓰지 않게 하려는 것이다. 군집 추종은 정반대로,
        리더가 움직이는 동안 목표가 계속 갱신되는 것이 정상이다. 그래서
        진행 중 거부만 빼고 안전 게이트는 그대로 지난다: e-stop 과 맵핑
        세션은 여기서도 막는다.

        Nav2 NavigateToPose 는 새 목표를 받으면 이전 목표를 선점하므로
        취소를 먼저 보내지 않는다 — 그 사이에 로봇이 멈춰 서기 때문이다.
        """
        executor = self._require_executor()
        if self._safety.estop:
            raise NavigationError("EMERGENCY_ACTIVE", "e-stop is active")
        if self.mapping_active:
            raise NavigationError("MAPPING_ACTIVE", "mapping session active")
        with self._lock:
            self._moving_session = True
            executor.send_goal(spec)
            started = self._nav_state not in (NavigationState.NAVIGATING,
                                              NavigationState.PLANNING)
            if started:
                self._set_state(NavigationState.PLANNING)
        if started:
            self._events.publish(
                "nav.started", source="navigation_manager",
                data={"goal": {"x": spec.x, "y": spec.y, "yaw": spec.yaw}, "by": source})

    def home(self, source: str = "api") -> None:
        spec = self.resolve_goal(waypoint="__home__")
        self.goal(spec, source=source)

    # --- NAV-005 Mapping 세션 -------------------------------------------------

    def start_mapping(self, source: str = "api") -> None:
        if self._safety.estop:
            raise NavigationError("EMERGENCY_ACTIVE", "e-stop is active")
        if self._nav_state not in _IDLE_STATES:
            raise NavigationError("NAVIGATION_ACTIVE",
                                  f"navigation in progress ({self._nav_state.value})")
        self.mapping_active = True
        self._events.publish("slam.started", source="navigation_manager", data={"by": source})

    def stop_mapping(self, source: str = "api") -> None:
        self.mapping_active = False
        self._events.publish("slam.stopped", source="navigation_manager", data={"by": source})

    def save_map(self, name: str = "rosy_map", source: str = "api") -> str:
        executor = self._require_executor()
        if not self.mapping_active:
            raise NavigationError("VALIDATION_ERROR", "no active mapping session")
        map_id = executor.save_map(name)
        self._state.set_map_id(map_id)
        self._events.publish("map.saved", source="navigation_manager", data={"map_id": map_id})
        return map_id

    def reset_mapping(self, source: str = "api") -> None:
        if not self.mapping_active:
            return
        if self.executor is not None and hasattr(self.executor, "reset_mapping"):
            self.executor.reset_mapping()
        self._events.publish("slam.started", source="navigation_manager",
                             data={"by": source, "reset": True})

    def cancel(self, source: str = "api") -> None:
        """진행 중 목표를 거둔다.

        moving goal 세션에서는 상태가 IDLE 계열이어도 취소를 보낸다. 선점된
        목표의 abort 가 상태를 FAILED 로 떨어뜨려 놓았을 수 있고, 그때 여기서
        돌아서면 살아 있는 Nav2 목표가 그대로 남아 로봇이 계속 달린다.
        """
        with self._lock:
            session = self._moving_session
            self._moving_session = False
            if self._nav_state in _IDLE_STATES and not session:
                return
            if self.executor is not None:
                self.executor.cancel_goal()
            self._set_state(NavigationState.CANCELED)
        self._events.publish("nav.canceled", source="navigation_manager", data={"source": source})

    def on_goal_accepted(self) -> None:
        with self._lock:
            self._set_state(NavigationState.NAVIGATING)
            if self._moving_session and self._last_progress_pos is not None:
                # SWM-002 는 NAV-006 이 그대로 적용된다고 못박았다. 0.5 초마다
                # 기준점을 초기화하면 30 초 무진척 조건은 영원히 성립하지 않고,
                # 문틀에 낀 팔로워가 아무 신호 없이 계속 밀어붙인다.
                return
            self._last_progress_pos = None
            self._last_progress_ts = time.monotonic()

    def on_result(self, succeeded: bool, error: Optional[str] = None) -> None:
        if succeeded:
            self._set_state(NavigationState.ARRIVED)
            self._events.publish("nav.completed", source="navigation_manager")
        else:
            self._set_state(NavigationState.FAILED)
            self._events.publish("nav.failed", severity="error", source="navigation_manager",
                                 data={"error_code": error or "UNKNOWN"})

    def on_pose_progress(self, x: float, y: float) -> None:
        """NAV-006 stuck: NAVIGATING 중 진척 없으면 자동 취소."""
        if self._nav_state is not NavigationState.NAVIGATING:
            return
        now = time.monotonic()
        if self._last_progress_pos is not None:
            dist = math.hypot(x - self._last_progress_pos[0], y - self._last_progress_pos[1])
            if dist >= self._stuck_min_progress:
                self._last_progress_pos = (x, y)
                self._last_progress_ts = now
                return
        else:
            self._last_progress_pos = (x, y)
            self._last_progress_ts = now
            return
        if now - self._last_progress_ts > self._stuck_timeout:
            self.cancel(source="stuck_detector")
            self._events.publish("nav.stuck", severity="error", source="navigation_manager",
                                 data={"timeout_s": self._stuck_timeout})
