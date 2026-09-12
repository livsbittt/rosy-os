"""rosy_core.safety — SAF-001~005 (P1-6, P1-20). ROS 무의존."""

from __future__ import annotations

import time
import math
from dataclasses import dataclass
from typing import Optional


def finite_velocity(linear: float, angular: float) -> bool:
    return all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
               for value in (linear, angular))


class TeleopWatchdog:
    """SAF-002: 마지막 teleop 명령 시각 추적, timeout 경과 시 만료."""

    def __init__(self, timeout_ms: int = 500) -> None:
        self.timeout_ms = timeout_ms
        self._last_refresh: float = 0.0

    def refresh(self, now: Optional[float] = None) -> None:
        self._last_refresh = now if now is not None else time.monotonic()

    def expired(self, now: Optional[float] = None) -> bool:
        current = now if now is not None else time.monotonic()
        return (current - self._last_refresh) * 1000.0 > self.timeout_ms


@dataclass
class SpeedLimits:
    max_linear: float = 0.20
    max_angular: float = 0.80
    manual_linear: float = 0.15
    manual_angular: float = 0.60
    fleet_linear: float = 0.20
    fleet_angular: float = 0.80


@dataclass
class BatteryPolicy:
    warning_percent: float = 20.0
    critical_percent: float = 10.0
    critical_action: str = "RETURN_HOME"


@dataclass(frozen=True)
class SafetyRequest:
    command_id: int
    source: str
    calibration_revision: str
    now: float
    linear: float
    angular: float


@dataclass(frozen=True)
class SafetyDecision:
    command_id: int
    source: str
    calibration_revision: str
    observed_at: float
    expires_at: float
    linear_limit: float
    angular_limit: float
    disposition: str = 'allow'
    reason: str = ''


class SafetyManager:
    """E-Stop(SAF-001)·속도 제한(SAF-004)·배터리 정책(SAF-005)·Fleet 단절 정책(SAF-003)."""

    def __init__(self, limits: SpeedLimits, battery: BatteryPolicy,
                 fleet_loss_policy: str = "STOP", events=None, policy_required: bool = False) -> None:
        if type(policy_required) is not bool:
            raise ValueError('control_policy_required must be a boolean')
        self.policy_required = policy_required
        self._policy = None
        self._policy_revision = ''
        self._policy_clock = time.monotonic
        self.policy_reason = ''
        self.limits = limits
        self.battery_policy = battery
        self.fleet_loss_policy = fleet_loss_policy
        self._events = events
        self.estop: bool = False
        self.estop_source: str = ""
        self._battery_state: str = "ok"
        #: 한 활동이 자기 구간 동안만 더 낮춰 쓰는 상한 (SWM-002 max_speed).
        #: 프로필 상한을 넘겨 올릴 수는 없다 — clip 이 둘 중 작은 값을 쓴다.
        self._session_linear: Optional[float] = None
        #: E-Stop 이 실제로 걸릴 때 한 번 불린다. API·배터리·어느 경로로
        #: 들어오든 같은 자리를 지나므로, 중단해야 할 활동은 여기에 붙는다.
        self.estop_listeners: list = []

    def bind_policy(self, evaluator, calibration_revision: str) -> None:
        """Bind a bounded, synchronous in-process evaluator; no ROS transport."""
        if not callable(evaluator) or not isinstance(calibration_revision, str) or not calibration_revision:
            raise ValueError('A policy evaluator and calibration revision are required')
        self._policy = evaluator
        self._policy_revision = calibration_revision
        self.policy_required = True

    def evaluate_candidate(self, command_id: int, source: str, linear: float,
                           angular: float, now: float) -> Optional[tuple[float, float]]:
        if not self.policy_required:
            return linear, angular
        self.policy_reason = 'policy_unavailable'
        evaluator, revision = self._policy, self._policy_revision
        if evaluator is None:
            return None
        request = SafetyRequest(command_id, source, revision, now, linear, angular)
        started = self._policy_clock()
        try:
            decision = evaluator(request)
            elapsed = self._policy_clock() - started
        except Exception:
            self.policy_reason = 'policy_failed'
            return None
        self.policy_reason = 'policy_invalid'
        if (not isinstance(decision, SafetyDecision) or evaluator is not self._policy
                or revision != self._policy_revision or not math.isfinite(elapsed) or not 0 <= elapsed <= .01):
            return None
        if (type(decision.command_id) is not int or decision.command_id != command_id
                or not isinstance(decision.source, str) or decision.source != source
                or not isinstance(decision.calibration_revision, str) or decision.calibration_revision != revision
                or not finite_velocity(decision.observed_at, decision.expires_at)
                or not decision.observed_at <= now <= now + elapsed <= decision.expires_at
                or not 0 < decision.expires_at - decision.observed_at <= .5
                or not finite_velocity(decision.linear_limit, decision.angular_limit)
                or min(decision.linear_limit, decision.angular_limit) < 0
                or not isinstance(decision.disposition, str) or decision.disposition not in ('allow', 'limit', 'stop')
                or not isinstance(decision.reason, str) or len(decision.reason) > 128):
            return None
        if decision.disposition == 'stop':
            self.policy_reason = decision.reason or 'policy_stop'
            return None
        self.policy_reason = ''
        return (max(-decision.linear_limit, min(decision.linear_limit, linear)),
                max(-decision.angular_limit, min(decision.angular_limit, angular)))

    def _emit(self, type_: str, severity: str, source: str, data: dict | None = None) -> None:
        if self._events is not None:
            self._events.publish(type_, severity=severity, source=source, data=data or {})

    def trigger_estop(self, source: str) -> bool:
        if self.estop:
            return False
        self.estop = True
        self.estop_source = source
        self._emit("safety.estop", "critical", source, {"source": source})
        for listener in list(self.estop_listeners):
            try:
                listener()
            except Exception:
                # 한 구독자의 실패가 E-Stop 경로를 막으면 안 된다.
                pass
        return True

    def release(self, by: str) -> bool:
        if not self.estop:
            return False
        self.estop = False
        self.estop_source = ""
        self._emit("safety.estop_released", "warning", "safety_manager", {"by": by})
        return True

    def set_session_speed(self, max_linear: Optional[float]) -> None:
        """활동 구간용 추가 상한. `None` 이면 해제하고 프로필 상한으로 돌아간다.

        SWM-002 의 `max_speed` 가 여기로 들어온다. 검증만 하고 흘려보내면
        계약이 거짓이 되고, Nav2 파라미터로 내려보내려면 CORE 에 없는 파라미터
        클라이언트가 필요하다. cmd_vel 이 어차피 전부 `clip` 을 지나므로
        (D-2), 실제로 바퀴에 닿는 값을 여기서 줄인다.
        """
        value = None if max_linear is None else float(max_linear)
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError('Session speed limit must be finite and nonnegative')
        self._session_linear = value

    @property
    def session_linear(self) -> Optional[float]:
        return self._session_linear

    def clip(self, linear: float, angular: float, scope: str = "nav") -> tuple[float, float]:
        if not finite_velocity(linear, angular):
            return 0.0, 0.0
        if scope == "manual":
            max_l, max_a = self.limits.manual_linear, self.limits.manual_angular
        elif scope == "fleet":
            max_l, max_a = self.limits.fleet_linear, self.limits.fleet_angular
        else:
            max_l, max_a = self.limits.max_linear, self.limits.max_angular
        if (not finite_velocity(max_l, max_a)
                or not finite_velocity(self.limits.max_linear, self.limits.max_angular)
                or min(max_l, max_a, self.limits.max_linear, self.limits.max_angular) < 0):
            return 0.0, 0.0
        max_l = min(max_l, self.limits.max_linear)
        max_a = min(max_a, self.limits.max_angular)
        if self._session_linear is not None:
            # 낮추기만 한다. 활동이 프로필 상한을 넘겨 달릴 수는 없다.
            max_l = min(max_l, self._session_linear)
        l = max(-max_l, min(max_l, linear))
        a = max(-max_a, min(max_a, angular))
        return l, a

    def on_battery_percent(self, percent: float) -> Optional[str]:
        """SAF-005: 임계 통과 시 정책 반환. None|'warn'|'critical'."""
        policy = self.battery_policy
        if percent <= policy.critical_percent:
            state = "critical"
            action = policy.critical_action
        elif percent <= policy.warning_percent:
            state = "warn"
            action = "warn"
        else:
            state, action = "ok", None
        crossed = state != self._battery_state and state != "ok"
        self._battery_state = state
        if crossed:
            if state == "critical":
                self._emit("battery.critical", "critical", "safety_manager",
                           {"percent": percent, "policy": action})
            else:
                self._emit("battery.low", "warning", "safety_manager", {"percent": percent})
        return action if crossed else None
