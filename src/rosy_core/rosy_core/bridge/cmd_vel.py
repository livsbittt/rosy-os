"""바퀴로 나가는 한 주기 (ROS 없이 검사할 수 있게 떼어낸 것).

`_publish_cmd_vel` 은 세 가지를 순서대로 한다: 값을 고르고, 바퀴로 내보내고,
그 **뒤에** 알린다. 순서가 기능의 절반인데 브리지 안에 있으면 rclpy 없는
호스트에서 아무도 검사하지 못한다 — 알림 한 줄을 지워도 모든 테스트가
초록이었다. 그래서 순서만 여기로 나온다.

SAF-002 정지가 늦어지지 않게 하는 규칙 두 가지:

* 이벤트 발행(`announce_pending`)은 구독자를 동기로 부르고 그중 하나가 감사
  로그를 쓴다. 내보내기 앞에 두면 그 비용만큼 정지가 늦게 바퀴에 닿는다.
* 절전 정책(`on_activity`)도 마찬가지다. 모터 경로에 개입하지 않는 관측일
  뿐이니, 관측이 바퀴 앞에 설 이유가 없다.
"""

from __future__ import annotations

from typing import Callable, Protocol


class _Command(Protocol):
    def select_output(self): ...
    def announce_pending(self) -> None: ...


class _Power(Protocol):
    def on_activity(self, reason: str) -> None: ...


def cmd_vel_cycle(command: _Command, power: _Power,
                  send: Callable[[float, float], None]) -> None:
    """값을 고르고, 바퀴로 내보내고, 그 뒤에 알린다."""
    out = command.select_output()
    send(out.linear, out.angular)
    if out.linear != 0.0 or out.angular != 0.0:
        power.on_activity("cmd_vel")
    command.announce_pending()
