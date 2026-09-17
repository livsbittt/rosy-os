"""Match phase, observation, and referee result. No policy twists."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Mapping, Optional

from rosy_games.field import Pose2D


class Phase(str, enum.Enum):
    KICKOFF = "kickoff"
    PLAY = "play"
    HOLD = "hold"
    GOAL = "goal"


@dataclass(frozen=True)
class Observation:
    t: float
    ball: Optional[Pose2D]
    robots: Mapping[str, Pose2D]
    lost_ball: bool
    lost_robots: frozenset[str]


@dataclass(frozen=True)
class MatchState:
    phase: Phase
    score: Mapping[str, int]
    reason: str
    scorer: Optional[str] = None
