"""rosy_games match --config ... [--dry-run] [--ticks N] [--preview]"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from rosy_games.catalog import make_game, make_policy
from rosy_games.host.hold import HoldObserver
from rosy_games.host.loop import MatchHost
from rosy_games.host.robots import load_match
from rosy_games.host.session import HOST_PERIOD_S, run_match, space_pressed
from rosy_games.host.transport import HttpPlayerClient


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="rosy_games")
    sub = parser.add_subparsers(dest="command", required=True)
    match = sub.add_parser("match", help="run or inspect a 1v1 match config")
    match.add_argument("--config", required=True, type=Path)
    match.add_argument("--dry-run", action="store_true")
    match.add_argument("--ticks", type=int, default=None)
    match.add_argument("--observer", choices=("hold", "overhead"), default="hold")
    match.add_argument("--preview", action="store_true")
    match.add_argument("--preview-port", type=int, default=8765)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    setup = load_match(args.config)
    if args.dry_run:
        print(f"field {setup.field.length_m}x{setup.field.width_m} m")
        print(f"game {setup.game} policy {setup.policy}")
        for robot in setup.robots:
            print(f"{robot.id} {robot.url} aruco={robot.aruco_id} attacks={robot.attacks}")
        print(f"goals {setup.goals.home_id}/{setup.goals.away_id}")
        if args.preview:
            print("preview 127.0.0.1 (not started in dry-run)")
        return 0
    live = args.ticks is None
    period_s = HOST_PERIOD_S if live else 0.0
    if period_s > setup.camera.lost_hold_s:
        raise ValueError(
            f"host period {period_s}s exceeds watchdog lost_hold_s {setup.camera.lost_hold_s}"
        )
    from rosy_games.host.preview import PreviewBoard, PreviewServer

    board = PreviewBoard() if args.preview else None
    server = PreviewServer(board, port=args.preview_port) if board is not None else None
    clients = [HttpPlayerClient(endpoint) for endpoint in setup.robots]
    observer = _observer(args.observer, setup)
    host = MatchHost(
        observer,
        clients,
        game=make_game(setup.game, setup.field),
        policy=make_policy(
            setup.policy,
            setup.field,
            speed=setup.linear,
            angular=setup.angular,
        ),
        preview=board,
        max_linear=setup.linear,
        max_angular=setup.angular,
    )
    try:
        if server is not None:
            print(server.start())
        run_match(
            host,
            ticks=None if live else args.ticks,
            period_s=period_s,
            halt_check=lambda: (board.stop if board is not None else False) or space_pressed(),
        )
    finally:
        if server is not None:
            server.close()
        for client in clients:
            close = getattr(client, "close", None)
            if close is not None:
                close()
        close = getattr(observer, "close", None)
        if close is not None:
            close()
    return 0


def _observer(kind: str, setup):
    if kind == "hold":
        return HoldObserver(setup.field.home_id, setup.field.away_id)
    from rosy_games.host.overhead import OverheadCamera

    return OverheadCamera(setup)


if __name__ == "__main__":
    raise SystemExit(main())
