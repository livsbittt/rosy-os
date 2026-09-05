"""rosy_core.navigation.swarm — SWM-001~007 follow 상태머신 (D-20). ROS 무의존.

추종 계산은 로봇에 있고 Fleet 은 지정·릴레이만 한다(D-20). 이 모듈은 참조
pose 가 **어디서 왔는지 묻지 않는다**(SWM-007): `on_reference_pose` 를 부르는
쪽이 Fleet 릴레이든 peer 유니캐스트든 추종 로직은 같다. 그래서 여기에는
websocket 도 fleet 도 등장하지 않는다.

목표는 Nav2 moving goal 로 투입한다(SWM-001). 별도 cmd_vel 소스를 만들지
않으므로 장애물 회피와 SAF-004 클리핑이 그대로 적용된다.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Optional

from rosy_core.navigation.manager import NavGoalSpec
from rosy_core.protocol.schemas import (
    SwarmFollowParams,
    SwarmReferenceSource,
    SwarmRole,
    SwarmStatus,
)

#: SWM-002 v1: moving goal 갱신 상한. 군집 속도(<=0.2 m/s)에서 충분하고,
#: 그 이상은 Nav2 플래너를 재시작시키기만 한다.
MAX_GOAL_RATE_HZ = 2.0
_MIN_GOAL_INTERVAL_S = 1.0 / MAX_GOAL_RATE_HZ


class SwarmError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ReferencePose:
    """리더가 보고한 pose 한 표본 (API Ref 7.8)."""

    robot_id: str
    x: float
    y: float
    yaw: float
    seq: int = 0


def follow_goal(reference: ReferencePose, distance: float, lateral: float) -> NavGoalSpec:
    """리더 뒤 `distance`, 왼쪽으로 `lateral` 떨어진 지점.

    리더의 heading 을 기준으로 잡는다 — 맵 좌표축이 아니다. 그래야 리더가
    회전해도 대형이 유지된다.
    """
    heading = (math.cos(reference.yaw), math.sin(reference.yaw))
    left = (-math.sin(reference.yaw), math.cos(reference.yaw))
    return NavGoalSpec(
        x=reference.x - distance * heading[0] + lateral * left[0],
        y=reference.y - distance * heading[1] + lateral * left[1],
        yaw=reference.yaw,
    )


class SwarmManager:
    """SWM-002 follow 프리미티브와 SWM-004 단절 정책."""

    def __init__(self, events, state_manager, nav, safety, capability,
                 clock=time.monotonic) -> None:
        self._events = events
        self._state = state_manager
        self._nav = nav
        self._safety = safety
        self._capability = capability
        self._clock = clock
        self._lock = threading.RLock()

        self._params: Optional[SwarmFollowParams] = None
        self._last_sample_at: Optional[float] = None
        self._last_goal_at: Optional[float] = None
        self._pending: Optional[ReferencePose] = None
        self._holding = False

    # --- 조회 -----------------------------------------------------------------

    @property
    def active(self) -> bool:
        with self._lock:
            return self._params is not None

    @property
    def holding(self) -> bool:
        with self._lock:
            return self._holding

    @property
    def params(self) -> Optional[SwarmFollowParams]:
        with self._lock:
            return self._params.model_copy() if self._params is not None else None

    def status(self) -> SwarmStatus:
        with self._lock:
            if self._params is None:
                return SwarmStatus()
            return SwarmStatus(
                role=SwarmRole.FOLLOWER,
                formation=self._formation_label(self._params),
                active=True,
            )

    def state_payload(self) -> dict:
        """GET /api/v1/swarm/state (SWM-002). 스냅샷의 swarm 필드보다 자세하다."""
        with self._lock:
            status = self.status()
            return {
                "role": status.role.value,
                "formation": status.formation,
                "active": status.active,
                "holding": self._holding,
                "target_robot_id": self._params.target_robot_id if self._params else None,
                "source": self._params.source.value if self._params else None,
                "stream_age_s": (
                    None if self._last_sample_at is None
                    else round(self._clock() - self._last_sample_at, 3)
                ),
            }

    @staticmethod
    def _formation_label(params: SwarmFollowParams) -> str:
        return f"follow:{params.target_robot_id}@{params.distance:.2f}/{params.lateral:.2f}"

    # --- SWM-002 follow / cancel ---------------------------------------------

    def follow(self, params: SwarmFollowParams, source: str = "api") -> SwarmStatus:
        if not self._capability.supports("swarm.follow"):
            raise SwarmError("CAPABILITY_NOT_SUPPORTED",
                             "this robot does not support swarm follow")
        if params.source is not SwarmReferenceSource.FLEET:
            # D-21 훅은 계약에만 있고 릴레이가 없다. 받아들이는 척하지 않는다.
            raise SwarmError(
                "CAPABILITY_NOT_SUPPORTED",
                f"reference source {params.source.value} is reserved, not implemented")
        if self._safety.estop:
            raise SwarmError("EMERGENCY_ACTIVE", "e-stop is active")
        if not math.isfinite(params.distance) or params.distance <= 0:
            raise SwarmError("VALIDATION_ERROR", "distance must be a positive number")
        if not math.isfinite(params.lateral):
            raise SwarmError("VALIDATION_ERROR", "lateral must be a finite number")
        if params.stream_timeout_ms <= 0:
            raise SwarmError("VALIDATION_ERROR", "stream_timeout_ms must be positive")
        if not math.isfinite(params.max_speed) or params.max_speed <= 0:
            raise SwarmError("VALIDATION_ERROR", "max_speed must be a positive number")
        ceiling = self._safety.limits.max_linear
        if params.max_speed > ceiling:
            raise SwarmError(
                "VALIDATION_ERROR",
                f"max_speed {params.max_speed} exceeds the SAF-004 ceiling {ceiling}")

        with self._lock:
            self._params = params.model_copy()
            self._last_sample_at = None
            self._last_goal_at = None
            self._pending = None
            self._holding = False
            status = self.status()

        self._state.set_swarm(status)
        self._events.publish(
            "swarm.role_assigned", source="swarm_manager",
            data={"role": SwarmRole.FOLLOWER.value,
                  "target_robot_id": params.target_robot_id,
                  "reference_source": params.source.value, "by": source},
        )
        return status

    def cancel(self, source: str = "api") -> SwarmStatus:
        with self._lock:
            was_active = self._params is not None
            self._params = None
            self._last_sample_at = None
            self._last_goal_at = None
            self._pending = None
            self._holding = False

        if was_active:
            self._nav.cancel(source="swarm")
            self._state.set_swarm(SwarmStatus())
            self._events.publish("swarm.aborted", source="swarm_manager",
                                 data={"reason": "canceled", "by": source})
        return SwarmStatus()

    # --- 참조 스트림 (SWM-007: 소스를 묻지 않는다) ----------------------------

    def on_reference_pose(self, reference: ReferencePose) -> bool:
        """참조 pose 한 표본. 목표를 실제로 보냈으면 True."""
        with self._lock:
            params = self._params
            if params is None or reference.robot_id != params.target_robot_id:
                return False
            now = self._clock()
            self._last_sample_at = now
            resumed = self._holding
            self._holding = False
            if self._last_goal_at is not None and now - self._last_goal_at < _MIN_GOAL_INTERVAL_S:
                # SWM-002: <=2 Hz. 버리지 않고 들고 있다가 tick 에서 낸다.
                self._pending = reference
                return False
            self._last_goal_at = now
            self._pending = None
            spec = follow_goal(reference, params.distance, params.lateral)

        if resumed:
            self._state.set_swarm(self.status())
        self._nav.moving_goal(spec, source="swarm")
        return True

    def tick(self, now: Optional[float] = None) -> None:
        """SWM-004: 스트림이 끊기면 HOLD. 밀린 목표가 있으면 여기서 낸다."""
        current = self._clock() if now is None else now
        spec: Optional[NavGoalSpec] = None
        hold = False
        with self._lock:
            params = self._params
            if params is None:
                return
            timeout_ms = params.stream_timeout_ms
            if self._last_sample_at is not None:
                age_ms = (current - self._last_sample_at) * 1000.0
                if age_ms >= timeout_ms and not self._holding:
                    self._holding = True
                    self._pending = None
                    hold = True
                elif not self._holding and self._pending is not None and (
                    self._last_goal_at is None
                    or current - self._last_goal_at >= _MIN_GOAL_INTERVAL_S
                ):
                    spec = follow_goal(self._pending, params.distance, params.lateral)
                    self._pending = None
                    self._last_goal_at = current

        if hold:
            # 자리를 지킨다: 목표만 거두고 follow 는 살려 둔다. 스트림이 돌아오면
            # 새 follow 명령 없이 이어서 따라간다.
            self._nav.cancel(source="swarm")
            self._state.set_swarm(self.status())
            self._events.publish("swarm.hold", severity="warning", source="swarm_manager",
                                 data={"reason": "reference stream lost",
                                       "stream_timeout_ms": timeout_ms})
        elif spec is not None:
            self._nav.moving_goal(spec, source="swarm")
