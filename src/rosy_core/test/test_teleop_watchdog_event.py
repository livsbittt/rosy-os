"""SAF-002 만료를 알리는 것 (계약은 v1.0 부터 약속했고 코드는 낸 적이 없다).

만료되면 출력이 조용히 0 이 된다. 조종하던 사람에게는 로봇이 그냥 멈춘 것이고,
링크가 끊겼는지 명령이 거부됐는지 자기가 손을 뗀 것인지 구분되지 않는다.
"""

from __future__ import annotations

import pytest
from rosy_core.command.arbitration import Mode, ModeMachine, SourceRegistry
from rosy_core.command.manager import CommandManager, Twist
from rosy_core.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits


class FakeEvents:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict]] = []

    def publish(self, type_, severity="info", source="", data=None):
        self.published.append((type_, str(severity), data or {}))

    def types(self) -> list[str]:
        return [t for t, _s, _d in self.published]


def build(mode=Mode.MANUAL):
    events = FakeEvents()
    modes = ModeMachine()
    modes.transition(mode)
    safety = SafetyManager(SpeedLimits(), BatteryPolicy(), events=events)
    return CommandManager(SourceRegistry(), modes, safety, events=events), events, safety


def drive(command, at):
    assert command.teleop(0.1, 0.0)[0] is True
    command.watchdog.refresh(at)


def test_an_expiry_says_so_with_the_timeout():
    command, events, _safety = build()
    drive(command, 100.0)

    command.select_output(now=100.0 + command.watchdog.timeout_ms / 1000.0 + 0.01)

    watchdog = [d for t, _s, d in events.published if t == "safety.watchdog"]
    assert watchdog == [{"timeout_ms": command.watchdog.timeout_ms}]


def test_it_is_a_warning_because_the_robot_stopped_on_its_own():
    command, events, _safety = build()
    drive(command, 100.0)

    command.select_output(now=101.0)

    severity = next(s for t, s, _d in events.published if t == "safety.watchdog")
    assert "warning" in severity.lower()


def test_it_is_announced_once_not_once_per_cycle():
    """select_output 은 50 Hz 로 불린다. 상태가 아니라 전이에서 말해야 한다."""
    command, events, _safety = build()
    drive(command, 100.0)

    for step in range(50):
        command.select_output(now=101.0 + step * 0.02)

    assert events.types().count("safety.watchdog") == 1


def test_a_new_command_re_arms_it():
    command, events, _safety = build()
    drive(command, 100.0)
    command.select_output(now=101.0)

    drive(command, 102.0)
    command.select_output(now=103.0)

    assert events.types().count("safety.watchdog") == 2


def test_an_expiry_with_nothing_in_hand_announces_nothing():
    """쥐고 있던 조종이 없으면 끊긴 조종도 없다."""
    command, events, _safety = build()

    for step in range(10):
        command.select_output(now=1000.0 + step)

    assert "safety.watchdog" not in events.types()


def test_the_announcement_does_not_change_what_reaches_the_wheels():
    command, _events, _safety = build()
    drive(command, 100.0)

    assert command.select_output(now=100.1) == Twist(0.1, 0.0)
    assert command.select_output(now=101.0) == Twist(0.0, 0.0)
    assert command.select_output(now=102.0) == Twist(0.0, 0.0)


def test_an_estop_stops_the_robot_without_blaming_the_watchdog():
    """E-Stop 은 그 자체로 알려진 원인이다. 워치독 탓으로 적으면 안 된다."""
    command, events, safety = build()
    drive(command, 100.0)
    safety.trigger_estop("operator")

    command.select_output(now=101.0)

    assert "safety.watchdog" not in events.types()
    assert "safety.estop" in events.types()


def test_a_navigation_run_is_not_a_lapsed_teleop():
    command, events, _safety = build(mode=Mode.NAVIGATION)
    command.set_nav_twist(Twist(0.1, 0.0), now=100.0)

    command.select_output(now=200.0)

    assert "safety.watchdog" not in events.types()


def test_the_expiry_reaches_the_audit_log(tmp_path):
    """운영자가 나중에 왜 멈췄는지 볼 수 있어야 한다 (LOG-001)."""
    from rosy_core.events.audit import FileAuditLog
    from rosy_core.events.bus import EventBus

    bus = EventBus("rosy_01")
    audit = FileAuditLog(tmp_path / "audit.jsonl")
    bus.subscribe(audit.record)

    modes = ModeMachine()
    modes.transition(Mode.MANUAL)
    safety = SafetyManager(SpeedLimits(), BatteryPolicy(), events=bus)
    command = CommandManager(SourceRegistry(), modes, safety, events=bus)
    command.teleop(0.1, 0.0)
    command.watchdog.refresh(100.0)

    command.select_output(now=101.0)

    recorded = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "safety.watchdog" in recorded
