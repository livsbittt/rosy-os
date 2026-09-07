"""LOG-001 file audit log. Same EventMessage schema as the in-memory bus.

기록은 이벤트 버스의 구독자로 붙어 있고(`services.py`), 버스는 구독자를 **동기로**
부른다. 그래서 `record()` 가 무거우면 그 비용은 이벤트를 낸 스레드가 문다 — 그중
하나가 50 Hz cmd_vel 타이머다.

예전에는 이벤트 하나마다 파일 전체를 읽어 모든 줄을 파싱하고 다시 직렬화해
덮어썼다. 보존 기간이 30 일이라 파일은 계속 자라고, 비용은 줄 수에 비례한다:
800 줄에서 `record()` 한 번이 16 ms — 50 Hz 주기의 0.8 개 — 이고 파일을 채우는
전체 비용은 O(n²) 이다. 30 일치면 그보다 한참 크다.

보존은 "읽었을 때 30 일 넘은 것이 없다"는 약속이지 "매 쓰기마다 즉시 정리한다"는
약속이 아니다. 그래서 쓰기는 덧붙이기만 하고, 조회는 메모리에서 걸러 답하며,
파일을 실제로 줄이는 것은 쓰기 경로가 한 시간에 한 번 한다.

이 구현이 **하지 않는** 것 두 가지 (알고 두는 것이지 잊은 것이 아니다):

* `fsync` 하지 않는다. 정전이면 OS 버퍼에 있던 마지막 몇 줄이 사라질 수 있다.
  매 이벤트마다 `fsync` 하면 SD 카드에서 한 번에 수 ms 가 들고 그 비용을 50 Hz
  타이머가 문다 — 이 파일이 애초에 고치려던 문제로 되돌아간다. 딥 방전 종료
  (D-27)는 정상 종료 경로라 버퍼가 비워지고, 갑작스러운 정전에서 마지막 몇 줄을
  잃는 것은 LOG-001 이 요구하는 30 일 보존과 다른 이야기다.
* 여러 **프로세스** 가 같은 파일을 쓰는 것을 막지 않는다. `threading.Lock` 은
  프로세스 안에서만 유효하고, 정리의 읽기-쓰기 사이에 다른 프로세스가 덧붙인
  줄은 `os.replace` 에 지워진다. D-1 에 따라 이 파일을 쓰는 것은 `rosy_core`
  한 프로세스뿐이므로 지금은 성립한다 — 두 번째 쓰는 쪽이 생기면 파일 락이
  필요하고, 그것은 이 주석이 아니라 ADR 로 정해야 한다.
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
        #:
        #: 둘로 나눠 센다. `_write_failures` 는 **연속** 실패라 지금 쓸 수 있는지를
        #: 말하고(gauge), `_write_failures_total` 은 누적이라 되돌아가지 않는다
        #: (counter). 성공 한 번이 카운터를 0 으로 되돌리면 Prometheus 는 그것을
        #: "카운터 리셋"으로 읽어 그 사이의 실패를 통째로 못 본 것으로 만든다.
        self._write_failures = 0
        self._write_failures_total = 0
        #: 정리 실패는 쓰기 실패가 아니다. 덧붙이기가 성공했으면 그 이벤트는
        #: 기록됐고, 파일이 30 일보다 길게 남아 있는 것은 다음 시각에 다시
        #: 시도할 일이지 감사 로그가 꺼졌다는 뜻이 아니다.
        self._prune_failures = 0
        #: 마지막 사유는 지우지 않는다. 성공 한 번에 지워 버리면 간헐적으로
        #: 실패하는 디스크는 운영자가 볼 때마다 늘 깨끗해 보인다.
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
                "write_failures_total": self._write_failures_total,
                "prune_failures": self._prune_failures,
                "last_error": self._last_error,
            }

    def record(self, event: EventMessage) -> None:
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(event.model_dump_json() + "\n")
            except OSError as error:
                # EventBus 는 구독자 예외를 삼킨다. 그대로 두면 감사 기록이
                # 멈춘 사실이 어디에도 남지 않는다 — 디스크가 찬 로봇은 아무
                # 말 없이 LOG-001 을 지키지 않게 된다. 세어 두고, 물으면 답한다.
                self._write_failures += 1
                self._write_failures_total += 1
                self._last_error = f"{type(error).__name__}: {error}"
                raise
            self._write_failures = 0

            # 이벤트는 이미 파일에 있다. 여기서부터 실패해도 그것은 되돌아가지
            # 않으므로, 정리 실패를 쓰기 실패로 세거나 밖으로 던지지 않는다 —
            # 그렇게 하면 감사 기록은 멀쩡한데 로그가 꺼졌다고 답하게 된다.
            if self._prune_due_locked():
                try:
                    self._prune_locked()
                except OSError as error:
                    self._prune_failures += 1
                    self._last_error = f"prune {type(error).__name__}: {error}"

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
        """보존 기간 안의 기록. **파일은 건드리지 않는다.**

        예전에는 읽을 때마다 정리를 돌렸다. 조회 한 번이 파일 전체를 다시
        쓰는 것이고, 대시보드가 5 초마다 폴링하면 5 초마다 감사 로그가 통째로
        재작성된다 — 버릴 줄이 하나도 없어도 그렇다. 게다가 그 파싱과 재작성이
        전부 `record()` 와 같은 락 안에 있어서, 조회 한 번이 50 Hz cmd_vel
        타이머를 그만큼 세운다.

        보존은 "읽었을 때 30 일 넘은 것이 보이지 않는다"는 약속이다. 그 약속은
        메모리에서 걸러도 똑같이 지켜진다. 파일을 실제로 줄이는 것은 쓰기
        경로가 한 시간에 한 번 한다.

        락은 원시 텍스트를 읽는 동안만 잡는다. 파싱은 밖에서 한다 — 비싼 쪽이
        그쪽이고, 그 사이 덧붙는 줄은 다음 조회에 보이면 된다.
        """
        with self._lock:
            text = self._read_text_locked()
            cutoff = self._now() - timedelta(days=self._retention_days)
        events = [event for event in self._parse(text) if self._is_fresh(event.ts, cutoff)]
        if since_seq is not None:
            events = [item for item in events if item.seq > since_seq]
        if limit < 1:
            return []
        return events[-limit:]

    def _read_text_locked(self) -> str:
        if not self._path.is_file():
            return ""
        return self._path.read_text(encoding="utf-8")

    @staticmethod
    def _parse(text: str) -> list[EventMessage]:
        events: list[EventMessage] = []
        for line in text.splitlines():
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
        seen = 0
        for line in self._path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            seen += 1
            try:
                event = EventMessage.model_validate_json(stripped)
            except (ValueError, TypeError):
                # 읽을 수 없는 줄은 `history()` 도 건너뛴다. 여기서 버린다.
                continue
            if self._is_fresh(event.ts, cutoff):
                # 원본 줄을 그대로 남긴다. 다시 직렬화하면 감사 기록이 스키마
                # 왕복에 따라 조용히 달라질 수 있다.
                kept.append(stripped)

        if len(kept) == seen:
            # 버릴 것이 없으면 쓰지 않는다. 같은 내용으로 파일을 갈아 끼우는
            # 것은 공짜가 아니다 — 30 일치를 매 시각 재작성하는 것이고, 그때마다
            # 원본이 잠깐 사라지는 창이 생긴다.
            return

        # 감사 로그를 자르는 도중에 죽으면 기록이 사라진다. 설정 오버레이와
        # 같은 규칙으로 임시 파일에 쓰고 바꿔 끼운다.
        tmp = self._path.with_name(self._path.name + ".tmp")
        try:
            tmp.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
            # Windows 에서 이것은 대상에 열린 핸들이 하나라도 있으면
            # `PermissionError` 다 (백신·인덱서·다른 프로세스의 조회). 여기서
            # 자며 다시 시도하지 않는다 — 이 코드는 락을 쥔 채 50 Hz cmd_vel
            # 스레드 위에서 돈다. 재시도는 한 시간 뒤 다음 정리 시각이 한다.
            # 그 사이 원본은 그대로 남아 있으므로 잃는 것은 없다.
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
