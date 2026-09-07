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
    # 정리는 쓰기 경로가 한다. 새 인스턴스의 첫 기록이 그 시각이다.
    fresh = FileAuditLog(path, retention_days=30, now=lambda: now)
    fresh.record(_event(3, now.isoformat()))

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == kept_line
    assert len(lines) == 2, "the stale line is gone and the two fresh ones are byte-identical"


def test_a_failed_prune_leaves_the_log_intact(tmp_path, monkeypatch):
    """자르는 도중에 죽으면 감사 기록이 사라진다. 바꿔 끼우기로 쓴다."""
    import os as _os

    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    log = FileAuditLog(path, retention_days=30, now=lambda: now)
    log.record(_event(1, now.isoformat()))
    log.record(_event(2, (now - timedelta(days=31)).isoformat()))
    before = path.read_text(encoding="utf-8")

    monkeypatch.setattr(_os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    fresh = FileAuditLog(path, retention_days=30, now=lambda: now)
    fresh.record(_event(3, now.isoformat()))       # 덧붙이기는 되고 정리만 실패한다

    assert path.read_text(encoding="utf-8").startswith(before)
    assert not list(tmp_path.glob("*.tmp")), "the temporary file must not be left behind"


def test_a_failed_prune_is_not_reported_as_an_unwritable_log(tmp_path, monkeypatch):
    """덧붙이기가 성공했으면 그 이벤트는 기록됐다.

    정리 실패를 쓰기 실패로 세면 `/logs/audit` 은 감사 기록이 멀쩡한 로봇을
    두고 "LOG-001 이 꺼졌다"고 답한다 — 운영자가 좇을 곳이 틀린다.
    """
    import os as _os

    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    # 지난 실행이 남긴 오래된 줄. `record()` 로 넣으면 그 자리에서 정리돼 버린다.
    stale = _event(1, (now - timedelta(days=31)).isoformat()).model_dump_json()
    path.write_text(stale + "\n", encoding="utf-8")

    monkeypatch.setattr(_os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    log = FileAuditLog(path, retention_days=30, now=lambda: now)
    log.record(_event(2, now.isoformat()))         # 예외가 밖으로 나오지 않는다

    health = log.health()
    assert health["writable"] is True
    assert health["write_failures"] == 0 and health["write_failures_total"] == 0
    assert health["prune_failures"] == 1
    assert "OSError" in health["last_prune_error"]
    assert health["last_write_error"] is None, "쓰기 채널은 깨끗하다"
    assert [event.seq for event in log.history()] == [2], "the new event is on disk"


def test_a_read_does_not_rewrite_the_file(tmp_path):
    """조회는 파일을 건드리지 않는다.

    예전에는 읽을 때마다 정리를 돌렸다 — 대시보드가 5 초마다 폴링하면 5 초마다
    30 일치 감사 로그를 통째로 재작성하는 것이고, 그 비용은 `record()` 와 같은
    락 안에 있어 50 Hz cmd_vel 스레드가 문다.
    """
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    log = FileAuditLog(path, retention_days=30, now=lambda: now)
    log.record(_event(1, (now - timedelta(days=31)).isoformat()))
    log.record(_event(2, now.isoformat()))
    before = path.read_bytes()
    inode = path.stat().st_ino

    assert [event.seq for event in log.history()] == [2], "the stale one is filtered out"

    assert path.read_bytes() == before
    # `st_mtime_ns` 는 같은 내용으로 갈아 끼울 때 그대로일 때가 많다(이 파일
    # 시스템에서 200 번 중 76 번). inode 는 `os.replace` 가 반드시 바꾼다.
    assert path.stat().st_ino == inode


def test_a_prune_with_nothing_to_drop_does_not_rewrite(tmp_path):
    """버릴 것이 없으면 쓰지 않는다. 같은 내용으로 갈아 끼우는 동안 원본이
    잠깐 사라지는 창이 생기고, 그것을 매 시각 여는 이유가 없다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    FileAuditLog(path, retention_days=30, now=lambda: now).record(_event(1, now.isoformat()))

    seen = []
    import os as _os
    real = _os.replace
    log = FileAuditLog(path, retention_days=30, now=lambda: now)
    try:
        _os.replace = lambda *a, **k: (seen.append(a), real(*a, **k))[1]
        log.record(_event(2, now.isoformat()))     # 첫 기록 = 정리 시각
    finally:
        _os.replace = real

    assert seen == []


# --- LOG-001 이 꺼졌다는 사실은 어딘가에 남아야 한다 ---------------------------


def test_a_write_failure_is_counted_rather_than_lost(tmp_path, monkeypatch):
    """EventBus 는 구독자 예외를 삼킨다.

    그래서 디스크가 찬 로봇은 감사 기록을 남기지 않으면서 아무 말도 하지
    않는다 — 나중에 사고를 조사할 때 비어 있는 로그와 구분되지 않는다.
    """
    log = FileAuditLog(tmp_path / "audit.jsonl")
    assert log.health() == {"writable": True, "write_failures": 0,
                            "write_failures_total": 0, "prune_failures": 0,
                            "last_write_error": None, "last_prune_error": None}

    def refuse(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "open", refuse)
    for _ in range(3):
        with pytest.raises(OSError):
            log.record(_event(1, "2026-09-03T12:00:00+00:00"))

    health = log.health()
    assert health["writable"] is False
    assert health["write_failures"] == 3
    assert health["write_failures_total"] == 3
    assert "No space left" in health["last_write_error"]


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

    health = log.health()
    assert health["writable"] is True and health["write_failures"] == 0
    # 누적 카운터와 마지막 사유는 남는다. 성공 한 번에 지워 버리면 간헐적으로
    # 실패하는 디스크는 운영자가 볼 때마다 늘 깨끗하고, Prometheus 는 카운터가
    # 0 으로 돌아간 것을 재시작으로 읽어 그 실패를 통째로 잃는다.
    assert health["write_failures_total"] == 1
    assert "nope" in health["last_write_error"]



# --- 잘린 꼬리: fsync 하지 않기로 한 것의 대가 --------------------------------

#: 정전이 UTF-8 한 글자 가운데를 자른 줄. `data` 에는 웨이포인트·맵 이름이
#: 실리므로 한글이 들어가고, 그 바이트열이 잘리면 strict 디코드는 예외다.
TORN = b'{"seq":2,"data":{"name":"\xed\x95\n'


def _with_a_torn_line(path: Path, now: datetime) -> str:
    good = _event(1, now.isoformat()).model_dump_json()
    path.write_bytes(good.encode("utf-8") + b"\n" + TORN)
    return good


def test_a_torn_tail_does_not_take_the_audit_log_down(tmp_path):
    """이 상태가 조용하면 `/logs/audit` 은 그 뒤로 영원히 500 이다.

    바이트 몇 개 때문에 30 일치를 통째로 못 읽게 되는 것이고, 그 사실은
    EventBus 가 구독자 예외를 삼키므로 어디에도 남지 않는다. `record()` 안의
    정리도 같은 디코드에서 죽어, 파일은 다시는 정리되지 않는다.
    """
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    _with_a_torn_line(path, now)
    log = FileAuditLog(path, retention_days=30, now=lambda: now)

    assert [event.seq for event in log.history()] == [1]

    log.record(_event(3, now.isoformat()))         # 예외가 밖으로 나오지 않는다

    assert [event.seq for event in log.history()] == [1, 3]
    health = log.health()
    assert health["writable"] is True
    assert health["prune_failures"] == 0, "정리는 실패한 것이 아니라 그 줄을 버린 것이다"


def test_a_torn_tail_is_compacted_away_rather_than_kept_forever(tmp_path):
    """스스로 낫는 것이 요점이다. 세어만 두면 파일은 영원히 그 상태다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    good = _with_a_torn_line(path, now)

    FileAuditLog(path, retention_days=30, now=lambda: now).record(_event(3, now.isoformat()))

    raw = path.read_bytes()
    assert b"\xed\x95" not in raw
    assert raw.decode("utf-8").splitlines()[0] == good


def test_blank_lines_are_compacted_rather_than_kept_forever(tmp_path):
    """빈 줄을 세지 않으면 `len(kept) == seen` 이 되어 조기 반환에 걸린다 —
    파일이 사는 내내 남는다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    good = _event(1, now.isoformat()).model_dump_json()
    path.write_text("\n\n   \n" + good + "\n", encoding="utf-8")

    FileAuditLog(path, retention_days=30, now=lambda: now).record(_event(2, now.isoformat()))

    assert path.read_text(encoding="utf-8").splitlines()[0] == good
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


# --- 정리는 락을 쥔 채 디코드·파싱하지 않는다 ---------------------------------


def _prune_with(log: FileAuditLog, path: Path, during) -> None:
    """정리의 디코드 자리에 `during` 을 끼워 넣고 한 번 기록한다.

    디코드와 파싱은 락 밖에서 도는 유일한 구간이다. 그 자리에서 무슨 일이
    벌어질 수 있는지가 이 설계의 대가이므로, 거기에 직접 손을 넣어 본다.
    """
    real = FileAuditLog._decode
    try:
        FileAuditLog._decode = staticmethod(lambda raw: (during(), real(raw))[1])
        log.record(_event(2, datetime(2026, 9, 3, tzinfo=timezone.utc).isoformat()))
    finally:
        FileAuditLog._decode = staticmethod(real)


def test_an_event_written_during_a_prune_is_not_lost(tmp_path):
    """스냅샷 길이 뒤를 잘라 새 내용에 붙이지 않으면 그 줄은 `os.replace` 에
    지워진다 — 감사 로그가 조용히 이벤트를 잃는 것이다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    stale = _event(1, (now - timedelta(days=31)).isoformat()).model_dump_json()
    path.write_text(stale + "\n", encoding="utf-8")
    log = FileAuditLog(path, retention_days=30, now=lambda: now)

    def another_thread_records():
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_event(99, now.isoformat()).model_dump_json() + "\n")

    _prune_with(log, path, another_thread_records)

    assert sorted(event.seq for event in log.history()) == [2, 99]


def test_the_prune_does_not_hold_the_lock_across_the_parse(tmp_path):
    """10 만 줄이면 디코드·파싱만 350 ms 다. 락을 쥔 채로 하면 그 한 시간에
    처음 기록되는 이벤트가 그것을 문다 — 하필 SAF-002 정지일 수 있다."""
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    path.write_text(_event(1, (now - timedelta(days=31)).isoformat()).model_dump_json() + "\n",
                    encoding="utf-8")
    log = FileAuditLog(path, retention_days=30, now=lambda: now)
    held: list[bool] = []

    def note_whether_the_lock_is_held():
        free = log._lock.acquire(blocking=False)
        held.append(not free)
        if free:
            log._lock.release()

    _prune_with(log, path, note_whether_the_lock_is_held)

    assert held == [False], "the lock was held across the decode and parse"


def test_whatever_the_prune_throws_is_counted_rather_than_swallowed(tmp_path):
    """`except OSError` 로는 부족하다.

    `_compact` 가 가장 먼저 하는 일은 I/O 가 아니라 디코드이고, 디코드 실패는
    `ValueError` 다. 그것이 여기를 빠져나가면 EventBus 의 `except Exception:
    pass` 가 삼켜 아무 데도 남지 않는다 — 정리는 영영 멈춘 채, 건강 상태는
    깨끗하다고 답한다.
    """
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    path.write_text(_event(1, (now - timedelta(days=31)).isoformat()).model_dump_json() + "\n",
                    encoding="utf-8")
    log = FileAuditLog(path, retention_days=30, now=lambda: now)

    def explode():
        raise ValueError("not an OSError")

    _prune_with(log, path, explode)                # 예외가 밖으로 나오지 않는다

    health = log.health()
    assert health["prune_failures"] == 1
    assert "ValueError" in health["last_prune_error"]
    assert health["writable"] is True and health["write_failures_total"] == 0
    assert [event.seq for event in log.history()] == [2], "the append still happened"


def test_a_file_that_shrank_under_the_prune_is_left_alone(tmp_path):
    """락 밖에서 파싱하는 대가로 생긴 창이다.

    그 사이 파일이 지워지거나 줄어들면 우리가 든 스냅샷은 더 이상 이 파일의
    앞부분이 아니다. 그대로 이어 붙이면 남의 파일을 우리 옛 내용으로
    덮어쓰게 된다 — 이어 붙이지 않고 이번 시각을 거른다.
    """
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    stale = _event(1, (now - timedelta(days=31)).isoformat()).model_dump_json()
    survivor = _event(7, now.isoformat()).model_dump_json()
    path.write_text(stale + "\n", encoding="utf-8")
    log = FileAuditLog(path, retention_days=30, now=lambda: now)

    def someone_replaces_the_file():
        path.write_text(survivor + "\n", encoding="utf-8")   # 더 짧다

    _prune_with(log, path, someone_replaces_the_file)

    assert path.read_text(encoding="utf-8") == survivor + "\n"


def test_a_deleted_file_is_not_recreated_from_a_stale_snapshot(tmp_path):
    now = datetime(2026, 9, 3, tzinfo=timezone.utc)
    path = tmp_path / "audit.jsonl"
    path.write_text(_event(1, (now - timedelta(days=31)).isoformat()).model_dump_json() + "\n",
                    encoding="utf-8")
    log = FileAuditLog(path, retention_days=30, now=lambda: now)

    _prune_with(log, path, lambda: path.unlink())

    assert not path.exists()
