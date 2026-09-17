"""Load a match without touching robots unless asked."""

from __future__ import annotations

import argparse
from pathlib import Path

from rosy_games.host.robots import load_match


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rosy_games")
    sub = parser.add_subparsers(dest="cmd", required=True)
    match = sub.add_parser("match")
    match.add_argument("--config", type=Path, required=True)
    match.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "match":
        config = load_match(args.config)
        if args.dry_run:
            ids = " ".join(robot.robot_id for robot in config.robots)
            print(f"dry-run {len(config.robots)} robots: {ids}")
            print(f"field {config.field.length_m}x{config.field.width_m}")
            return 0
        raise SystemExit("live match needs an observation source (not in this build)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
