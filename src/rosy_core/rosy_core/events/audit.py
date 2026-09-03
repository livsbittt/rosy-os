"""LOG-001 file audit log. Same EventMessage schema as the in-memory bus."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from rosy_core.protocol.schemas import EventMessage

DEFAULT_RETENTION_DAYS = 30


class FileAuditLog:
    def __init__(
        self,
        path: Path,
        *,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._path = Path(path)
        self._retention_days = retention_days
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def record(self, event: EventMessage) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
            self._prune_locked()

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
        if not self._path.is_file():
            return
        cutoff = self._now() - timedelta(days=self._retention_days)
        kept = [
            event.model_dump_json()
            for event in self._read_locked()
            if self._is_fresh(event.ts, cutoff)
        ]
        self._path.write_text(
            ("\n".join(kept) + "\n") if kept else "",
            encoding="utf-8",
        )

    def _is_fresh(self, ts: str, cutoff: datetime) -> bool:
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= cutoff
