"""CORE REST only: mode, teleop, stop."""

from __future__ import annotations

import httpx

from rosy_games.field import Twist

_MODE = "/api/v1/mode"
_TELEOP = "/api/v1/teleop"
_STOP = "/api/v1/safety/stop"


class HttpPlayerClient:
    def __init__(
        self,
        robot_id: str,
        base_url: str,
        token: str = "",
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.robot_id = robot_id
        self._base = base_url.rstrip("/")
        self._token = token
        self._http = client or httpx.Client(timeout=1.0)

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def set_manual(self) -> None:
        response = self._http.post(
            f"{self._base}{_MODE}",
            json={"mode": "MANUAL"},
            headers=self._headers(),
        )
        response.raise_for_status()

    def teleop(self, twist: Twist) -> None:
        response = self._http.post(
            f"{self._base}{_TELEOP}",
            json={"linear": twist.linear, "angular": twist.angular},
            headers=self._headers(),
        )
        response.raise_for_status()

    def estop(self) -> None:
        response = self._http.post(
            f"{self._base}{_STOP}",
            headers=self._headers(),
        )
        response.raise_for_status()
