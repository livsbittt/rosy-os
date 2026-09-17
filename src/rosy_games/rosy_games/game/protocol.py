"""Referee contract. Policy twists stay out of step()."""

from __future__ import annotations

from typing import Protocol

from rosy_games.game.state import MatchState, Observation


class Game(Protocol):
    def reset(self) -> MatchState: ...

    def step(self, obs: Observation) -> MatchState: ...
