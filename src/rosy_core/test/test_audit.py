"""LOG-001: audit events survive a process restart on disk."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from rosy_core.events.audit import FileAuditLog
from rosy_core.events.bus import EventBus
from rosy_core.protocol.schemas import EventMessage, Severity


def _event(seq: int, ts: str, type_: str = "mode.changed") -> EventMessage:
    return EventMessage(
        seq=seq,
        ts=ts,
        robot_id="rosy_01",
        type=type_,
        severity=Severity.INFO,
        source="test",
        data={},
    )


def test_audit_log_survives_a_new_process(tmp_path):
    path = tmp_path / "audit.jsonl"
    FileAuditLog(path).record(_event(1, "2026-09-03T12:00:00+00:00"))
    events = FileAuditLog(path).history()
    assert len(events) == 1
    assert events[0].type == "mode.changed"
    assert events[0].seq == 1


def test_audit_log_drops_records_older_than_retention(tmp_path):
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    log = FileAuditLog(tmp_path / "audit.jsonl", retention_days=30, now=lambda: now)
    log.record(_event(1, (now - timedelta(days=31)).isoformat()))
    log.record(_event(2, (now - timedelta(days=1)).isoformat()))
    types = [e.type for e in log.history()]
    assert [e.seq for e in log.history()] == [2]
    assert types == ["mode.changed"]


def test_audit_log_skips_a_corrupt_line(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    FileAuditLog(path).record(_event(3, "2026-09-03T12:00:00+00:00"))
    events = FileAuditLog(path).history()
    assert [e.seq for e in events] == [3]


def test_event_bus_can_feed_the_audit_log(tmp_path):
    bus = EventBus("rosy_01")
    log = FileAuditLog(tmp_path / "audit.jsonl")
    bus.subscribe(log.record)
    bus.publish("safety.estop", source="api")
    assert FileAuditLog(tmp_path / "audit.jsonl").history()[0].type == "safety.estop"
