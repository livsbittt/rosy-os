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
from rosy_core.safety.manager import SafetyManager, TeleopWatchdog


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
        #: teleop 세션 번호. 만료 알림은 세션당 한 번이다.
        #:
        #: 불리언이면 경합에서 사라진다: 타이머가 "아직 안 알림"을 읽고 멈춘
        #: 사이 새 명령이 들어와 초기화하면, 타이머가 깨어나 그 새 세션을
        #: "이미 알림"으로 덮어써 그 세션의 끊김은 영영 조용해진다. 번호를
        #: 비교하면 뒤늦은 쓰기가 옛 값을 실어 무해하다.
        self._session = 0
        self._announced_session = -1
        #: 알릴 것이 밀려 있는가. 알림은 정지가 바퀴에 닿은 뒤에 낸다.
        self._pending_watchdog: Optional[int] = None
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
        linear, angular = self._safety.clip(linear, angular, scope="manual")
        self._manual_twist = Twist(linear, angular)
        self.watchdog.refresh()
        # 새 명령이 왔으니 다음 끊김은 다시 알릴 일이다.
        self._session += 1
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
        self._nav_twist = twist
        self._nav_updated_at = (
            (now if now is not None else time.monotonic()) if twist is not None else None
        )

    def clear_navigation(self) -> None:
        self.set_nav_twist(None)

    def clear_manual(self) -> None:
        self._manual_twist = None
        self.watchdog.refresh(0.0)

    def _note_watchdog_lapse(self) -> None:
        """SAF-002 만료를 기록해 둔다. 내보내는 것은 `announce_pending` 이다.

        `select_output` 은 조회다 — 50 Hz cmd_vel 경로의 첫 줄이고, 그 반환값이
        바퀴로 나간다. 여기서 바로 발행하면 정지를 **알리는 일이 정지를 내보내는
        일보다 먼저** 온다: EventBus 는 구독자를 동기로 부르고, 운용 구성에서
        그중 하나가 30 일치 감사 로그를 통째로 다시 쓰는 파일 싱크다. 그동안
        드라이버는 끊기기 직전의 0 아닌 명령을 그대로 쥐고 있다.

        그래서 여기서는 기록만 하고, 정지가 나간 뒤 호출자가 알린다.
        """
        if self._manual_twist is None or self._announced_session == self._session:
            return
        self._pending_watchdog = self._session

    def announce_pending(self) -> None:
        """밀린 알림을 낸다. 브리지가 cmd_vel 을 내보낸 **뒤** 부른다."""
        session = self._pending_watchdog
        if session is None:
            return
        self._pending_watchdog = None
        if session == self._announced_session:
            return
        self._announced_session = session
        if self._events is not None:
            self._events.publish(
                "safety.watchdog", severity="warning", source="command_manager",
                data={"timeout_ms": self.watchdog.timeout_ms})

    def clear_manual_session(self) -> None:
        """조종을 쥐고 있던 상태를 버린다 (E-Stop 등 이미 알려진 정지 사유).

        `_manual_twist` 가 남아 있으면 E-Stop 해제 뒤 첫 틱이 만료를 발견하고
        `safety.watchdog` 를 낸다 — 링크는 멀쩡했는데 끊겼다고 적는 셈이다.
        """
        self._manual_twist = None
        self._pending_watchdog = None
        self._announced_session = self._session

    def select_output(self, now: Optional[float] = None) -> Twist:
        current = now if now is not None else time.monotonic()
        if self._safety.estop or self._modes.is_emergency:
            return ZERO
        if self._modes.mode is Mode.MANUAL:
            if self._manual_twist is not None and not self.watchdog.expired(current):
                l, a = self._safety.clip(self._manual_twist.linear, self._manual_twist.angular, "manual")
                return Twist(l, a)
            self._note_watchdog_lapse()
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
