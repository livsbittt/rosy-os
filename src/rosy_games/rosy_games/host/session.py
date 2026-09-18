"""Run a finite or live match: arm, tick, always estop."""

from __future__ import annotations

import time

from rosy_games.game.state import MatchState
from rosy_games.host.loop import MatchHost


def run_match(
    host: MatchHost,
    ticks: int | None = 1,
    *,
    period_s: float = 0.0,
) -> list[MatchState]:
    states: list[MatchState] = []
    try:
        host.arm()
        count = 0
        while ticks is None or count < ticks:
            states.append(host.tick())
            count += 1
            if period_s > 0:
                time.sleep(period_s)
        return states
    except KeyboardInterrupt:
        return states
    finally:
        host._estop_all()
