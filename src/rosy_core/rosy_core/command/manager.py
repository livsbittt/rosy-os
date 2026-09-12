"""rosy_core.command.manager — CORE-002 + §8.1 cmd_vel 멀렉서 (P1-5, D-2). ROS 무의존.

유일한 cmd_vel 원천: select_output()을 50 Hz로 호출해 발행한다 (bridge 담당).
- EMERGENCY: 모든 소스 차단, zero-twist (SAF-001)
- MANUAL: teleop만, watchdog 만료 시 zero (SAF-002)
- NAVIGATION: nav_cmd_vel(Nav2) 통과, 속도 클리핑 (SAF-004)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from rosy_core.command.arbitration import Mode, ModeMachine, SourceRegistry
from rosy_core.safety.manager import SafetyManager, TeleopWatchdog, finite_velocity


@dataclass
class Twist:
    linear: float = 0.0
    angular: float = 0.0


ZERO = Twist()


class CommandManager:
    def __init__(self, registry: SourceRegistry, modes: ModeMachine,
                 safety: SafetyManager, events=None) -> None:
        self._registry = registry
        self._modes = modes
        self._safety = safety
        self._events = events
        self.watchdog = TeleopWatchdog(timeout_ms=500)
        self._manual_twist: Optional[Twist] = None
        self._nav_twist: Optional[Twist] = None
        self._nav_updated_at: Optional[float] = None
        self._nav_timeout_s = 0.5

    def _reject(self, source: str, reason: str) -> None:
        if self._events is not None:
            self._events.publish("command.rejected", severity="warning",
                                 source="command_manager", data={"source": source, "reason": reason})

    def teleop(self, linear: float, angular: float, source: str = "manual") -> tuple[bool, str]:
        if not self._registry.is_active_source(source):
            self._reject(source, "unregistered source")
            return False, "VALIDATION_ERROR"
        if self._safety.estop or self._modes.is_emergency:
            self._reject(source, "e-stop active")
            return False, "EMERGENCY_ACTIVE"
        if self._modes.mode is not Mode.MANUAL:
            self._reject(source, f"mode is {self._modes.mode.value}, not MANUAL")
            return False, "MODE_CONFLICT"
        if not finite_velocity(linear, angular):
            self.clear_manual()
            self._reject(source, "invalid velocity")
            return False, "VALIDATION_ERROR"
        linear, angular = self._safety.clip(linear, angular, scope="manual")
        self._manual_twist = Twist(linear, angular)
        self.watchdog.refresh()
        return True, ""

    @property
    def manual_active(self) -> bool:
        """살아 있는 teleop 세션이 있는가.

        도킹 복귀 정책이 쓴다 — MANUAL(3)이 DOCKING(4)보다 위라, 운영자가 쥐고
        있는 로봇을 배터리 정책이 빼앗지 않는다. 워치독이 만료된 명령은 이미
        조종이 아니므로 세션으로 치지 않는다.
        """
        return self._manual_twist is not None and not self.watchdog.expired()

    def set_nav_twist(self, twist: Optional[Twist], now: Optional[float] = None) -> None:
        if twist is not None and not finite_velocity(twist.linear, twist.angular):
            self._reject('navigation', 'invalid velocity')
            twist = None
        self._nav_twist = twist
        self._nav_updated_at = (
            (now if now is not None else time.monotonic()) if twist is not None else None
        )

    def clear_navigation(self) -> None:
        self.set_nav_twist(None)

    def clear_manual(self) -> None:
        self._manual_twist = None
        self.watchdog.refresh(0.0)

    def select_output(self, now: Optional[float] = None) -> Twist:
        current = now if now is not None else time.monotonic()
        if self._safety.estop or self._modes.is_emergency:
            return ZERO
        if self._modes.mode is Mode.MANUAL:
            if self._manual_twist is not None and not self.watchdog.expired(current):
                l, a = self._safety.clip(self._manual_twist.linear, self._manual_twist.angular, "manual")
                return Twist(l, a)
            return ZERO
        nav_age = current - self._nav_updated_at if self._nav_updated_at is not None else None
        if (
            self._modes.mode is Mode.NAVIGATION
            and self._nav_twist is not None
            and nav_age is not None
            and 0.0 <= nav_age <= self._nav_timeout_s
        ):
            l, a = self._safety.clip(self._nav_twist.linear, self._nav_twist.angular, "nav")
            return Twist(l, a)
        return ZERO
