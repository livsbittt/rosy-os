"""rosy_core.state.manager — CORE-001 (P1-4). 10 Hz 스냅샷. ROS 무의존."""

from __future__ import annotations

import threading
from typing import Optional

from rosy_core.protocol.schemas import (
    Battery,
    HealthState,
    NavigationState,
    Pose,
    RobotMode,
    SafetySummary,
    StateSnapshot,
    SwarmStatus,
    Velocity,
)


class StateManager:
    def __init__(self, robot_id: str) -> None:
        self._robot_id = robot_id
        self._lock = threading.Lock()
        self._seq = 0
        self._mode: RobotMode = RobotMode.IDLE
        self._navigation: NavigationState = NavigationState.IDLE
        self._pose = Pose()
        self._velocity = Velocity()
        self._battery = Battery()
        self._safety = SafetySummary()
        self._swarm = SwarmStatus()
        self._map_id: Optional[str] = None
        self._diagnostics: dict[str, HealthState] = {}
        self._errors: list[str] = []

    def set_mode(self, mode: RobotMode) -> None:
        with self._lock:
            self._mode = mode

    def set_navigation(self, state: NavigationState) -> None:
        with self._lock:
            self._navigation = state

    def set_pose(self, x: float, y: float, yaw: float) -> None:
        with self._lock:
            self._pose = Pose(x=x, y=y, yaw=yaw)

    def set_velocity(self, linear: float, angular: float) -> None:
        with self._lock:
            self._velocity = Velocity(linear=linear, angular=angular)

    def set_battery(self, percent: Optional[float], voltage: Optional[float] = None) -> None:
        with self._lock:
            self._battery = Battery(percent=percent if percent is not None else self._battery.percent,
                                    voltage=voltage if voltage is not None else self._battery.voltage)

    def set_estop(self, active: bool) -> None:
        with self._lock:
            self._safety = SafetySummary(estop=active)

    def set_swarm(self, status: SwarmStatus) -> None:
        with self._lock:
            self._swarm = status

    def set_map_id(self, map_id: Optional[str]) -> None:
        with self._lock:
            self._map_id = map_id

    @property
    def map_id(self) -> Optional[str]:
        with self._lock:
            return self._map_id

    def set_diagnostic(self, component: str, health: HealthState) -> None:
        with self._lock:
            self._diagnostics[component] = health

    def push_error(self, message: str) -> None:
        with self._lock:
            self._errors.append(message)
            self._errors = self._errors[-20:]

    def snapshot(self) -> StateSnapshot:
        with self._lock:
            self._seq += 1
            return StateSnapshot(
                robot_id=self._robot_id,
                online=True,
                mode=self._mode,
                navigation=self._navigation,
                map_id=self._map_id,
                pose=self._pose.model_copy(),
                velocity=self._velocity.model_copy(),
                battery=self._battery.model_copy(),
                safety=self._safety.model_copy(),
                swarm=self._swarm.model_copy(),
                diagnostics_summary=dict(self._diagnostics),
                errors=list(self._errors),
                seq=self._seq,
            )
