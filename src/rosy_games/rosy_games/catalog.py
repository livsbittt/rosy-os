"""Named game and policy plugins. Soccer lives here as the first kind."""

from __future__ import annotations

from rosy_games.field import Field
from rosy_games.game.protocol import Game
from rosy_games.game.soccer import SoccerGame
from rosy_games.policy.heuristic import HeuristicPolicy
from rosy_games.policy.protocol import Policy

GAMES = {"soccer": SoccerGame}
POLICIES = {"heuristic": HeuristicPolicy}


def make_game(kind: str, field: Field) -> Game:
    try:
        cls = GAMES[kind]
    except KeyError as exc:
        raise ValueError(f"unknown game {kind!r}") from exc
    return cls(field)


def make_policy(kind: str, field: Field, *, speed: float = 0.08) -> Policy:
    try:
        cls = POLICIES[kind]
    except KeyError as exc:
        raise ValueError(f"unknown policy {kind!r}") from exc
    return cls(field, speed=speed)
