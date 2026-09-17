"""Run a finite match: arm, tick, always estop."""

from __future__ import annotations

from rosy_games.game.state import MatchState
from rosy_games.host.loop import MatchHost


def run_match(host: MatchHost, ticks: int = 1) -> list[MatchState]:
    states: list[MatchState] = []
    try:
        host.arm()
        for _ in range(ticks):
            states.append(host.tick())
        return states
    finally:
        host._estop_all()
