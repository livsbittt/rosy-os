"""Referee contract. Policy twists stay out of step()."""

from __future__ import annotations

from typing import Protocol

from rosy_games.field import Field
from rosy_games.game.state import MatchState, Observation


class Game(Protocol):
    field: Field

    def reset(self) -> MatchState: ...

    def step(self, obs: Observation) -> MatchState: ...
