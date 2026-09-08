"""rosy_fleet.swarm.robots — 오케스트레이터가 아는 로봇 목록 (robots.yaml).

토큰은 로봇마다 다르다(D-30: 장치 로컬 토큰). 참조 소켓과 swarm/follow 는 operator
이상이어야 한다(D-31) — 파일에 든 토큰은 그 역할이어야 하며 여기서는 형식만 본다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

import yaml


class RobotsFileError(ValueError):
    """robots.yaml 을 읽을 수 없다."""


@dataclass(frozen=True)
class RobotEndpoint:
    robot_id: str
    base_url: str   # 끝 슬래시 없음
    token: str


_REQUIRED = ("robot_id", "base_url", "token")


def load_robots(path: Path) -> list[RobotEndpoint]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rows = data.get("robots") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RobotsFileError(f"{path}: needs a non-empty 'robots' list")
    seen: set[str] = set()
    out: list[RobotEndpoint] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RobotsFileError(f"{path}: robots[{i}] is not a mapping")
        for key in _REQUIRED:
            if not row.get(key):
                raise RobotsFileError(f"{path}: robots[{i}] is missing '{key}'")
        robot_id = str(row["robot_id"])
        if robot_id in seen:
            raise RobotsFileError(f"{path}: duplicate robot_id {robot_id!r}")
        seen.add(robot_id)
        out.append(RobotEndpoint(robot_id, str(row["base_url"]).rstrip("/"), str(row["token"])))
    return out


def write_robots(path: Path, robots: list[RobotEndpoint]) -> None:
    """`gz_multi core:=true` 가 시뮬 로봇 목록을 써 주는 데 쓴다."""
    Path(path).write_text(
        yaml.safe_dump({"robots": [asdict(r) for r in robots]}, sort_keys=False),
        encoding="utf-8",
    )


def ws_url(base_url: str, path: str, token: str, **query: str) -> str:
    """REST base_url → 같은 호스트의 WS URL. 토큰은 쿼리로 간다 (API Ref §6)."""
    scheme, _, host = base_url.partition("://")
    ws_scheme = "wss" if scheme == "https" else "ws"
    params = {"token": token, **query}
    return f"{ws_scheme}://{host}{path}?{urlencode(params)}"
