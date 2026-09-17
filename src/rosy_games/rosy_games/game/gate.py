"""Non-play and ramming twists become zero. Policy is not trusted here."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from rosy_games.field import ZERO, Field, Twist
from rosy_games.game.protocol import Observation, Phase
from rosy_games.game.state import MatchState


@dataclass(frozen=True)
class CommandSet:
    twists: Mapping[str, Twist]
    estop: bool = False


def gate(
    twists: Mapping[str, Twist],
    observation: Observation,
    state: MatchState,
    field: Field,
) -> CommandSet:
    ids = set(observation.robots) | set(twists)
    cleaned = {robot_id: _finite(twists.get(robot_id, ZERO)) for robot_id in ids}
    if state.phase is not Phase.PLAY:
        return CommandSet(twists={robot_id: ZERO for robot_id in cleaned}, estop=False)
    poses = observation.robots
    if len(poses) >= 2:
        (id_a, a), (id_b, b) = tuple(poses.items())[:2]
        if math.hypot(a.x - b.x, a.y - b.y) < field.avoid_m:
            cleaned[id_a] = Twist(min(cleaned.get(id_a, ZERO).linear, 0.0), cleaned.get(id_a, ZERO).angular)
            cleaned[id_b] = Twist(min(cleaned.get(id_b, ZERO).linear, 0.0), cleaned.get(id_b, ZERO).angular)
    return CommandSet(twists=cleaned, estop=False)


def _finite(twist: Twist) -> Twist:
    if not math.isfinite(twist.linear) or not math.isfinite(twist.angular):
        return ZERO
    return twist
