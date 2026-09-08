"""rosy_fleet CLI — Fleet 서버가 생기기 전까지 운영자가 대형을 여는 입구.

    rosy_fleet relay     --robots robots.yaml --leader rosy_01
    rosy_fleet formation --robots robots.yaml --leader rosy_01 --formation V --spacing 0.6

`formation` 은 세션을 열고 stdin 명령을 받는다: `reform <FORMATION> [spacing]`,
`resume`, `status`, `stop`. 1 s 마다 릴레이 통계와 세션 상태를 한 줄 찍는다.
SIGINT 는 `stop()` 이다 — 릴레이만 죽이고 팔로워를 무장 상태로 두지 않는다.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import stat
import sys
from pathlib import Path
from typing import Optional, Sequence

from rosy_fleet.formation.geometry import DEFAULT_SPACING, Formation, FormationError
from rosy_fleet.swarm.relay import Relay
from rosy_fleet.swarm.robots import RobotEndpoint, load_robots
from rosy_fleet.swarm.session import FormationSession, FormationSpec, HoldPolicy, SessionError
from rosy_fleet.swarm.transport import HttpRobotClient


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="rosy_fleet")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--robots", required=True, type=Path, help="robots.yaml")
        p.add_argument("--leader", required=True, help="리더 robot_id")

    relay = sub.add_parser("relay", help="리더 pose → 팔로워 reference 릴레이만")
    common(relay)

    formation = sub.add_parser("formation", help="대형 세션 (무장 + 릴레이 + FOR-004)")
    common(formation)
    formation.add_argument("--formation", default="COLUMN", choices=[f.value for f in Formation])
    formation.add_argument("--spacing", type=float, default=DEFAULT_SPACING)
    formation.add_argument("--grid-cols", type=int, default=2)
    formation.add_argument("--max-speed", type=float, default=0.15)
    formation.add_argument("--stream-timeout-ms", type=int, default=1000)
    formation.add_argument("--policy", default="HOLD", choices=[p.value for p in HoldPolicy])
    return parser.parse_args(argv)


def split_robots(args: argparse.Namespace) -> tuple[RobotEndpoint, list[RobotEndpoint]]:
    robots = load_robots(args.robots)
    _warn_if_world_readable(args.robots)
    leaders = [r for r in robots if r.robot_id == args.leader]
    if not leaders:
        sys.exit(f"leader {args.leader!r} is not in {args.robots}")
    return leaders[0], [r for r in robots if r.robot_id != args.leader]


def _warn_if_world_readable(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        if Path(path).stat().st_mode & stat.S_IROTH:
            print(f"warning: {path} is world-readable and holds operator tokens", file=sys.stderr)
    except OSError:
        pass


def spec_from(args: argparse.Namespace) -> FormationSpec:
    return FormationSpec(Formation(args.formation), spacing=args.spacing, grid_cols=args.grid_cols,
                         max_speed=args.max_speed, stream_timeout_ms=args.stream_timeout_ms)


def policy_from(args: argparse.Namespace) -> HoldPolicy:
    return HoldPolicy(args.policy)


def _pending_suffix(session) -> str:
    """`session.pending_triggers` 가 있고 비어있지 않으면 ` pending=<n>`. 없으면 빈 문자열
    — status 테스트의 Recorder 는 이 필드를 갖지 않으므로 getattr 로 넘어간다."""
    pending = getattr(session, "pending_triggers", None)
    return f" pending={len(pending)}" if pending else ""


async def handle_command(line: str, session, base: FormationSpec) -> bool:
    """stdin 한 줄. 세션을 계속 돌리면 True, 끝내면 False."""
    parts = line.strip().split()
    if not parts:
        return True
    cmd, rest = parts[0].lower(), parts[1:]
    try:
        if cmd == "reform" and rest:
            spacing = float(rest[1]) if len(rest) > 1 else base.spacing
            spec = FormationSpec(Formation(rest[0].upper()), spacing=spacing, grid_cols=base.grid_cols,
                                 max_speed=base.max_speed, stream_timeout_ms=base.stream_timeout_ms)
            await session.reform(spec)
            if session.state.value == "HOLDING":
                # 무장 중에 무엇인가 걸렸다. 다음 통계 줄을 기다려 알게 하지 않는다.
                print(f"held: {session.reason} — resume when clear")
        elif cmd == "resume":
            await session.resume()
        elif cmd == "status":
            print(f"state={session.state.value} reason={session.reason}{_pending_suffix(session)}")
        elif cmd == "stop":
            await session.stop()
            return False
        else:
            print("commands: reform <FORMATION> [spacing] | resume | status | stop")
    except (ValueError, FormationError, SessionError) as exc:
        print(f"refused: {exc}")
    return True


async def _read_stdin(queue: asyncio.Queue) -> None:
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            await queue.put("stop")
            return
        await queue.put(line)


def _follower_token(rid: str, hz: float, ok: bool, error: Optional[str]) -> str:
    marker = "" if ok else "!"
    suffix = f"({error})" if not ok and error else ""
    return f"{rid}:{hz:.1f}Hz{marker}{suffix}"


def _stats_line(relay: Relay, session: Optional[FormationSession]) -> str:
    st = relay.stats()
    tx = " ".join(_follower_token(rid, hz, st.follower_connected[rid], st.follower_last_error.get(rid))
                  for rid, hz in st.follower_tx_hz.items())
    state = f" {session.state.value}" + (f" {session.reason}" if session and session.reason else "") \
        + (_pending_suffix(session) if session else "") if session else ""
    err = f" LEADER REFUSED: {st.leader_last_error}" if st.leader_last_error else ""
    return f"leader {st.leader_rx_hz:.1f}Hz drop={st.leader_dropped}{' PAUSED' if st.paused else ''}{err} | {tx}{state}"


async def run_relay(args: argparse.Namespace) -> None:
    leader_ep, follower_eps = split_robots(args)
    leader = HttpRobotClient(leader_ep)
    followers = [HttpRobotClient(ep) for ep in follower_eps]
    relay = Relay(leader, followers)
    await relay.start()
    try:
        while True:
            await asyncio.sleep(1.0)
            print(_stats_line(relay, None), flush=True)
    finally:
        await relay.stop()


async def run_formation(args: argparse.Namespace) -> None:
    leader_ep, follower_eps = split_robots(args)
    leader = HttpRobotClient(leader_ep)
    followers = [HttpRobotClient(ep) for ep in follower_eps]
    base = spec_from(args)
    session = FormationSession(leader, followers, base, policy=policy_from(args))
    try:
        await session.start()
    except SessionError as exc:
        sys.exit(f"could not arm the formation: {exc}")
    print(f"armed: {session.assignment}", flush=True)
    commands: asyncio.Queue = asyncio.Queue()
    reader = asyncio.create_task(_read_stdin(commands))
    try:
        while True:
            try:
                line = await asyncio.wait_for(commands.get(), timeout=1.0)
            except asyncio.TimeoutError:
                print(_stats_line(session.relay, session), flush=True)
                continue
            if not await handle_command(line, session, base):
                return
    finally:
        reader.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reader
        if session.state.value != "STOPPED":
            await session.stop()


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    runner = run_relay if args.command == "relay" else run_formation
    try:
        asyncio.run(runner(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
