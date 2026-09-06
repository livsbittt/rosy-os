"""LOG-001: audit events survive a process restart on disk."""

from datetime import datetime, timedelta, timezone

import pytest
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


# --- 쓰기 비용: 기록은 버스 구독자이고, 버스는 구독자를 동기로 부른다 ----------


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_a_write_does_not_rewrite_the_whole_file_every_time():
    """예전에는 이벤트 하나마다 파일 전체를 읽고 파싱하고 다시 썼다.

    보존 기간이 30 일이라 비용은 계속 자라고, 그 비용은 이벤트를 낸 스레드가
    문다 — 그중 하나가 50 Hz cmd_vel 타이머다.
    """
    import tempfile
    import time

    path = Path(tempfile.mkdtemp()) / "audit.jsonl"
    log = FileAuditLog(path)
    for seq in range(2000):
        log.record(_event(seq, "2026-09-03T12:00:00+00:00"))

    started = time.perf_counter()
    log.record(_event(2000, "2026-09-03T12:00:00+00:00"))
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < 5.0, (
        f"a single record cost {elapsed_ms:.1f} ms against a 2000-line log; "
        "one 50 Hz cmd_vel cycle is 20 ms"
    )


def test_the_write_path_prunes_at_most_once_an_hour(tmp_path):
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    clock = Clock()
    path = tmp_path / "audit.jsonl"
    log = FileAuditLog(path, retention_days=30, now=lambda: now,
                       monotonic=clock, prune_interval_s=3600.0)
    log.record(_event(1, (now - timedelta(days=31)).isoformat()))   # 첫 기록은 정리한다

    log.record(_event(2, (now - timedelta(days=31)).isoformat()))
    clock.advance(60.0)
    log.record(_event(3, now.isoformat()))

    # 아직 한 시간이 지나지 않았으니 오래된 줄이 파일에 남아 있다.
    assert "seq\":2" in path.read_text(encoding="utf-8").replace(" ", "")

    clock.advance(3600.0)
    log.record(_event(4, now.isoformat()))

    assert [event.seq for event in log.history()] == [3, 4]


def test_the_first_write_still_prunes_what_the_last_run_left(tmp_path):
    """재시작 직후 파일에 남아 있는 오래된 줄은 첫 기록에서 정리된다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    FileAuditLog(path, now=lambda: now).record(
        _event(1, (now - timedelta(days=31)).isoformat()))

    FileAuditLog(path, retention_days=30, now=lambda: now).record(
        _event(2, now.isoformat()))

    assert [event.seq for event in FileAuditLog(path, now=lambda: now).history()] == [2]


def test_reading_always_honours_retention(tmp_path):
    """정리를 늦춘 것이지 보존 약속을 늦춘 것이 아니다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    clock = Clock()
    log = FileAuditLog(tmp_path / "audit.jsonl", retention_days=30,
                       now=lambda: now, monotonic=clock)
    log.record(_event(1, now.isoformat()))
    log.record(_event(2, (now - timedelta(days=31)).isoformat()))

    assert [event.seq for event in log.history()] == [1]


def test_pruning_keeps_the_original_line_rather_than_re_serialising(tmp_path):
    """감사 기록이 스키마 왕복으로 조용히 달라지면 안 된다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    log = FileAuditLog(path, retention_days=30, now=lambda: now)
    log.record(_event(1, now.isoformat()))
    kept_line = path.read_text(encoding="utf-8").strip()

    log.record(_event(2, (now - timedelta(days=31)).isoformat()))
    FileAuditLog(path, retention_days=30, now=lambda: now).history()

    assert path.read_text(encoding="utf-8").strip() == kept_line


def test_a_failed_prune_leaves_the_log_intact(tmp_path, monkeypatch):
    """자르는 도중에 죽으면 감사 기록이 사라진다. 바꿔 끼우기로 쓴다."""
    import os as _os

    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    log = FileAuditLog(path, retention_days=30, now=lambda: now)
    log.record(_event(1, now.isoformat()))
    before = path.read_text(encoding="utf-8")

    monkeypatch.setattr(_os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        FileAuditLog(path, retention_days=30, now=lambda: now).history()

    assert path.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("*.tmp")), "the temporary file must not be left behind"


# --- LOG-001 이 꺼졌다는 사실은 어딘가에 남아야 한다 ---------------------------


def test_a_write_failure_is_counted_rather_than_lost(tmp_path, monkeypatch):
    """EventBus 는 구독자 예외를 삼킨다.

    그래서 디스크가 찬 로봇은 감사 기록을 남기지 않으면서 아무 말도 하지
    않는다 — 나중에 사고를 조사할 때 비어 있는 로그와 구분되지 않는다.
    """
    log = FileAuditLog(tmp_path / "audit.jsonl")
    assert log.health() == {"writable": True, "write_failures": 0, "last_error": None}

    def refuse(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "open", refuse)
    for _ in range(3):
        with pytest.raises(OSError):
            log.record(_event(1, "2026-09-03T12:00:00+00:00"))

    health = log.health()
    assert health["writable"] is False
    assert health["write_failures"] == 3
    assert "No space left" in health["last_error"]


def test_the_bus_still_swallows_the_failure_so_publishing_keeps_working(tmp_path, monkeypatch):
    """감사 기록이 안 된다고 안전 이벤트 발행이 멈추면 안 된다."""
    bus = EventBus("rosy_01")
    log = FileAuditLog(tmp_path / "audit.jsonl")
    bus.subscribe(log.record)

    def refuse(*args, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(Path, "open", refuse)
    bus.publish("safety.estop", source="api")

    assert log.health()["write_failures"] == 1
    assert bus.last_seq == 1


def test_a_recovered_write_clears_the_alarm(tmp_path, monkeypatch):
    """디스크가 비면 다시 정상이다. 한 번 실패한 채로 굳어 있으면 안 된다."""
    log = FileAuditLog(tmp_path / "audit.jsonl")
    real_open = Path.open

    def refuse(*args, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(Path, "open", refuse)
    with pytest.raises(OSError):
        log.record(_event(1, "2026-09-03T12:00:00+00:00"))
    assert log.health()["writable"] is False

    monkeypatch.setattr(Path, "open", real_open)
    log.record(_event(2, "2026-09-03T12:00:00+00:00"))

    assert log.health() == {"writable": True, "write_failures": 0, "last_error": None}

