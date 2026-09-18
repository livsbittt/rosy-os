"""rosy_games match --config ... [--dry-run] [--ticks N]"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from rosy_games.catalog import make_game, make_policy
from rosy_games.host.hold import HoldObserver
from rosy_games.host.loop import MatchHost
from rosy_games.host.robots import load_match
from rosy_games.host.session import run_match
from rosy_games.host.transport import HttpPlayerClient


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="rosy_games")
    sub = parser.add_subparsers(dest="command", required=True)
    match = sub.add_parser("match", help="run or inspect a 1v1 match config")
    match.add_argument("--config", required=True, type=Path)
    match.add_argument("--dry-run", action="store_true")
    match.add_argument("--ticks", type=int, default=None)
    match.add_argument("--observer", choices=("hold", "overhead"), default="hold")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    setup = load_match(args.config)
    if args.dry_run:
        print(f"field {setup.field.length_m}x{setup.field.width_m} m")
        print(f"game {setup.game} policy {setup.policy}")
        for robot in setup.robots:
            print(f"{robot.id} {robot.url} aruco={robot.aruco_id} attacks={robot.attacks}")
        return 0
    clients = [HttpPlayerClient(endpoint) for endpoint in setup.robots]
    observer = _observer(args.observer, setup)
    host = MatchHost(
        observer,
        clients,
        game=make_game(setup.game, setup.field),
        policy=make_policy(setup.policy, setup.field, speed=setup.linear),
    )
    try:
        run_match(host, ticks=args.ticks or 1)
    finally:
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
