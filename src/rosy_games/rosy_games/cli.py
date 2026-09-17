"""rosy_games match --config ... [--dry-run]"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from rosy_games.host.robots import load_match


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="rosy_games")
    sub = parser.add_subparsers(dest="command", required=True)
    match = sub.add_parser("match", help="load a 1v1 match config")
    match.add_argument("--config", required=True, type=Path)
    match.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    field, robots = load_match(args.config)
    if not args.dry_run:
        raise SystemExit("run with --dry-run")
    print(f"field {field.length_m}x{field.width_m} m")
    for robot in robots:
        print(f"{robot.id} {robot.url} aruco={robot.aruco_id} attacks={robot.attacks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
