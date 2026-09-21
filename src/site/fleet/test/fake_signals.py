"""신호등 가짜 — 네트워크 없이 SignalConsole/엔드포인트를 돌린다.

장치의 최소 규칙만 흉내 낸다: 단조 `seq` 검사(409 stale_seq), 인증(403),
충돌 가드(400 conflict), 그리고 상태 보고. 펌웨어를 대체하지 않는다 — 계약의
응답 모양을 고정하는 것이 목적이다.
"""

from __future__ import annotations

from typing import Optional

from fleet.server.signals import SignalApiError, SignalStatus


class FakeSignal:
    def __init__(self, signal_id: str, *, mode: str = "manual",
                 lamps: Optional[dict] = None, token: str = "t") -> None:
        self.signal_id = signal_id
        self.token = token
        self.mode = mode
        self.lamps = lamps if lamps is not None else {
            "red": True, "yellow": False, "green": False}
        self.faults: list[str] = []
        self.last_seq = 0
        self.status_error: Optional[Exception] = None
        self.commands: list[dict] = []
        self.command_error: Optional[Exception] = None

    # --- SignalClient protocol --------------------------------------------------

    def _status(self) -> SignalStatus:
        return SignalStatus(
            signal_id=self.signal_id,
            mode=self.mode,
            lamps=dict(self.lamps),
            seq=self.last_seq,
            faults=tuple(self.faults),
            secs_since_contact=0,
            firmware="1.0.0",
        )

    async def status(self) -> SignalStatus:
        if self.status_error is not None:
            raise self.status_error
        return self._status()

    async def command(self, body: dict) -> SignalStatus:
        if self.command_error is not None:
            raise self.command_error
        seq = body.get("seq")
        if not isinstance(seq, int) or seq <= self.last_seq:
            raise SignalApiError(self.signal_id, 409, "stale_seq",
                                 "seq is not ahead of the device", self.last_seq)
        if body.get("mode") == "manual":
            lamps = body.get("lamps") or {}
            if lamps.get("red") and lamps.get("green"):
                raise SignalApiError(self.signal_id, 400, "conflict",
                                     "red and green together is refused")
        self.last_seq = seq
        self.mode = body.get("mode", self.mode)
        if "lamps" in body:
            self.lamps = dict(body["lamps"])
        if self.mode == "all_red":
            self.lamps = {"red": True, "yellow": False, "green": False}
        self.commands.append(dict(body))
        return self._status()

    async def aclose(self) -> None:
        return None
