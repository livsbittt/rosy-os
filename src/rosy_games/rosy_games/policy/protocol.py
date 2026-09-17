from __future__ import annotations

from typing import Mapping, Protocol

from rosy_games.field import Twist
from rosy_games.game.protocol import Observation
from rosy_games.game.state import MatchState


class Policy(Protocol):
    def act(self, observation: Observation, state: MatchState) -> Mapping[str, Twist]: ...
