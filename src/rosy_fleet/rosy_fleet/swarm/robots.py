"""rosy_fleet.swarm.robots — 오케스트레이터가 아는 로봇 목록 (robots.yaml).

토큰은 로봇마다 다르다(D-30: 장치 로컬 토큰). 참조 소켓과 swarm/follow 는 operator
이상이어야 한다(D-31) — 파일에 든 토큰은 그 역할이어야 하며 여기서는 형식만 본다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
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
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError 는 ValueError 계열이라 OSError 만 잡으면 새어 나간다.
        raise RobotsFileError(f"{path}: cannot read robots file: {exc}") from exc
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise RobotsFileError(f"{path}: not valid YAML: {exc}") from exc
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
        # 토큰은 바이트 그대로 살아야 하는 비밀이다. YAML 1.1 은 `01234567`(8진), `yes`,
        # `1:23:45` 같은 따옴표 없는 값을 다른 타입으로 읽으므로, str() 로 억지로 바꾸면
        # 다른 문자열이 되어 4401 로 조용히 실패한다. base_url 도 같은 이유로 문자열만 받는다.
        for key in ("base_url", "token"):
            if not isinstance(row[key], str):
                raise RobotsFileError(
                    f"{path}: robots[{i}] '{key}' must be a quoted string, not {type(row[key]).__name__}")
        robot_id = str(row["robot_id"])
        if robot_id in seen:
            raise RobotsFileError(f"{path}: duplicate robot_id {robot_id!r}")
        seen.add(robot_id)
        base_url = row["base_url"].rstrip("/")
        if not base_url.lower().startswith(("http://", "https://")):
            # 스킴이 없으면 ws_url 이 호스트를 잃고 `ws:///...` 를 만든다 — 연결 시점이 아니라
            # 여기서 거절한다.
            raise RobotsFileError(f"{path}: robots[{i}] base_url needs an http:// or https:// scheme")
        out.append(RobotEndpoint(robot_id, base_url, row["token"]))
    return out


def write_robots(path: Path, robots: list[RobotEndpoint]) -> None:
    """`gz_multi core:=true` 가 시뮬 로봇 목록을 써 주는 데 쓴다. 로더의 규칙을 먼저 통과시킨다."""
    ids = [r.robot_id for r in robots]
    if not robots or any(not r.robot_id or not r.base_url or not r.token for r in robots):
        raise RobotsFileError("every robot needs robot_id, base_url and token")
    if len(set(ids)) != len(ids):
        raise RobotsFileError(f"duplicate robot_id in {ids}")
    rows = [{"robot_id": r.robot_id, "base_url": r.base_url.rstrip("/"), "token": r.token} for r in robots]
    target = Path(path)
    target.write_text(yaml.safe_dump({"robots": rows}, sort_keys=False), encoding="utf-8")
    try:
        # operator 토큰 N 개가 평문으로 든 파일이다. POSIX 에서는 소유자만 읽게 한다.
        os.chmod(target, 0o600)
    except OSError:
        pass


def ws_url(base_url: str, path: str, token: str, **query: str) -> str:
    """REST base_url → 같은 호스트의 WS URL. 토큰은 쿼리로 간다 (API Ref §6)."""
    scheme, _, host = base_url.partition("://")
    scheme = scheme.lower()
    if scheme not in ("http", "https") or not host:
        # 알 수 없는 스킴을 ws 로 떨어뜨리면 https 오타 하나가 토큰을 평문으로 보낸다.
        raise ValueError(f"base_url must be http(s)://host[:port], got {base_url!r}")
    ws_scheme = "wss" if scheme == "https" else "ws"
    params = {"token": token, **query}
    return f"{ws_scheme}://{host}{path}?{urlencode(params)}"
