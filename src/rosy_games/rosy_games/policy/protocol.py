"""Policy contract. Referee state in, twists out."""

from __future__ import annotations

from typing import Protocol

from rosy_games.field import Twist
from rosy_games.game.state import MatchState, Observation


class Policy(Protocol):
    def act(self, obs: Observation, state: MatchState) -> dict[str, Twist]: ...
