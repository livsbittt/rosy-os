"""rosy_core.safety — SAF-001~005 (P1-6, P1-20). ROS 무의존."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


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


class SafetyManager:
    """E-Stop(SAF-001)·속도 제한(SAF-004)·배터리 정책(SAF-005)·Fleet 단절 정책(SAF-003)."""

    def __init__(self, limits: SpeedLimits, battery: BatteryPolicy,
                 fleet_loss_policy: str = "STOP", events=None) -> None:
        self.limits = limits
        self.battery_policy = battery
        self.fleet_loss_policy = fleet_loss_policy
        self._events = events
        self.estop: bool = False
        self.estop_source: str = ""
        self._battery_state: str = "ok"

    def _emit(self, type_: str, severity: str, source: str, data: dict | None = None) -> None:
        if self._events is not None:
            self._events.publish(type_, severity=severity, source=source, data=data or {})

    def trigger_estop(self, source: str) -> bool:
        if self.estop:
            return False
        self.estop = True
        self.estop_source = source
        self._emit("safety.estop", "critical", source, {"source": source})
        return True

    def release(self, by: str) -> bool:
        if not self.estop:
            return False
        self.estop = False
        self.estop_source = ""
        self._emit("safety.estop_released", "warning", "safety_manager", {"by": by})
        return True

    def clip(self, linear: float, angular: float, scope: str = "nav") -> tuple[float, float]:
        if scope == "manual":
            max_l, max_a = self.limits.manual_linear, self.limits.manual_angular
        elif scope == "fleet":
            max_l, max_a = self.limits.fleet_linear, self.limits.fleet_angular
        else:
            max_l, max_a = self.limits.max_linear, self.limits.max_angular
        max_l = min(max_l, self.limits.max_linear)
        max_a = min(max_a, self.limits.max_angular)
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
