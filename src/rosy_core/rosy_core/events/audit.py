"""LOG-001 file audit log. Same EventMessage schema as the in-memory bus.

기록은 이벤트 버스의 구독자로 붙어 있고(`services.py`), 버스는 구독자를 **동기로**
부른다. 그래서 `record()` 가 무거우면 그 비용은 이벤트를 낸 스레드가 문다 — 그중
하나가 50 Hz cmd_vel 타이머다.

예전에는 이벤트 하나마다 파일 전체를 읽어 모든 줄을 파싱하고 다시 직렬화해
덮어썼다. 보존 기간이 30 일이라 파일은 계속 자라고, 비용은 줄 수에 비례한다:
800 줄에서 `record()` 한 번이 16 ms — 50 Hz 주기의 0.8 개 — 이고 파일을 채우는
전체 비용은 O(n²) 이다. 30 일치면 그보다 한참 크다.

보존은 "읽었을 때 30 일 넘은 것이 없다"는 약속이지 "매 쓰기마다 즉시 정리한다"는
약속이 아니다. 그래서 쓰기는 덧붙이기만 하고, 정리는 (1) 읽을 때와 (2) 쓰기
경로에서는 한 시간에 한 번만 한다.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from rosy_core.protocol.schemas import EventMessage

DEFAULT_RETENTION_DAYS = 30

#: 쓰기 경로에서 정리를 다시 시도하기까지의 최소 간격.
#:
#: 30 일 보존에 한 시간의 여유를 두는 것이므로 정책은 그대로다. 대신 쓰기 한 번의
#: 비용이 줄 수와 무관해진다.
PRUNE_INTERVAL_S = 3600.0


class FileAuditLog:
    def __init__(
        self,
        path: Path,
        *,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        now: Optional[Callable[[], datetime]] = None,
        monotonic: Optional[Callable[[], float]] = None,
        prune_interval_s: float = PRUNE_INTERVAL_S,
    ) -> None:
        self._path = Path(path)
        self._retention_days = retention_days
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._prune_interval_s = prune_interval_s
        #: None = 아직 한 번도 정리하지 않았다. 첫 기록은 정리한다 — 지난
        #: 실행이 남긴 오래된 줄이 그대로 있을 수 있다.
        self._last_prune: Optional[float] = None
        #: 기록이 실패한 횟수와 마지막 사유. 버스는 구독자 예외를 삼키므로,
        #: 여기에 남기지 않으면 디스크가 찬 로봇은 감사 기록을 남기지 않으면서
        #: 아무 말도 하지 않는다 — LOG-001 이 조용히 꺼진 상태다.
        self._write_failures = 0
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def health(self) -> dict:
        """기록이 실제로 남고 있는가. 운영자가 감사 로그를 물을 때 함께 답한다."""
        with self._lock:
            return {
                "writable": self._write_failures == 0,
                "write_failures": self._write_failures,
                "last_error": self._last_error,
            }

    def record(self, event: EventMessage) -> None:
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(event.model_dump_json() + "\n")
                if self._prune_due_locked():
                    self._prune_locked()
            except OSError as error:
                # EventBus 는 구독자 예외를 삼킨다. 그대로 두면 감사 기록이
                # 멈춘 사실이 어디에도 남지 않는다 — 디스크가 찬 로봇은 아무
                # 말 없이 LOG-001 을 지키지 않게 된다. 세어 두고, 물으면 답한다.
                self._write_failures += 1
                self._last_error = f"{type(error).__name__}: {error}"
                raise
            self._last_error = None
            self._write_failures = 0

    def _prune_due_locked(self) -> bool:
        if self._last_prune is None:
            return True
        return self._monotonic() - self._last_prune >= self._prune_interval_s

    def history(
        self,
        *,
        since_seq: Optional[int] = None,
        limit: int = 500,
    ) -> list[EventMessage]:
        with self._lock:
            self._prune_locked()
            events = self._read_locked()
        if since_seq is not None:
            events = [item for item in events if item.seq > since_seq]
        if limit < 1:
            return []
        return events[-limit:]

    def _read_locked(self) -> list[EventMessage]:
        if not self._path.is_file():
            return []
        events: list[EventMessage] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(EventMessage.model_validate_json(line))
            except (ValueError, TypeError):
                continue
        return events

    def _prune_locked(self) -> None:
        self._last_prune = self._monotonic()
        if not self._path.is_file():
            return
        cutoff = self._now() - timedelta(days=self._retention_days)
        kept: list[str] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = EventMessage.model_validate_json(stripped)
            except (ValueError, TypeError):
                # 읽을 수 없는 줄은 `history()` 도 건너뛴다. 여기서 버린다.
                continue
            if self._is_fresh(event.ts, cutoff):
                # 원본 줄을 그대로 남긴다. 다시 직렬화하면 감사 기록이 스키마
                # 왕복에 따라 조용히 달라질 수 있다.
                kept.append(stripped)

        # 감사 로그를 자르는 도중에 죽으면 기록이 사라진다. 설정 오버레이와
        # 같은 규칙으로 임시 파일에 쓰고 바꿔 끼운다.
        tmp = self._path.with_name(self._path.name + ".tmp")
        try:
            tmp.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise

    def _is_fresh(self, ts: str, cutoff: datetime) -> bool:
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= cutoff
