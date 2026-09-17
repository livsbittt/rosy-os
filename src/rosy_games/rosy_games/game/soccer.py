"""1v1 push-ball referee. Pure numbers."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Mapping, Optional

from rosy_games.field import Field


class Phase(str, enum.Enum):
    KICKOFF = "kickoff"
    IN_PLAY = "in_play"


@dataclass(frozen=True)
class Observation:
    ball: Optional[tuple[float, float]]
    robots: Mapping[str, tuple[float, float, float]]


@dataclass(frozen=True)
class Action:
    linear: float
    angular: float


@dataclass(frozen=True)
class StepResult:
    phase: Phase
    observation: Observation
    score: Mapping[str, int]
    scorer: Optional[str] = None
    actions: Mapping[str, Action] = field(default_factory=dict)


class SoccerGame:
    def __init__(self, field: Field | None = None) -> None:
        self.field = field or Field()
        self.phase = Phase.KICKOFF
        self.score = {self.field.home_id: 0, self.field.away_id: 0}

    def reset(self) -> StepResult:
        self.phase = Phase.KICKOFF
        empty = Observation(ball=None, robots={})
        return StepResult(phase=self.phase, observation=empty, score=dict(self.score))

    def step(
        self, observation: Observation, actions: Mapping[str, Action]
    ) -> StepResult:
        if self.phase is Phase.KICKOFF:
            if self._kickoff_ready(observation):
                self.phase = Phase.IN_PLAY
            return StepResult(
                phase=self.phase,
                observation=observation,
                score=dict(self.score),
                actions=_halt(observation.robots),
            )
        scorer = self._goal_scorer(observation)
        if scorer is not None:
            self.score[scorer] += 1
            self.phase = Phase.KICKOFF
            return StepResult(
                phase=self.phase,
                observation=observation,
                score=dict(self.score),
                scorer=scorer,
                actions=_halt(observation.robots),
            )
        return StepResult(
            phase=self.phase,
            observation=observation,
            score=dict(self.score),
            actions=dict(actions),
        )

    def _kickoff_ready(self, observation: Observation) -> bool:
        if observation.ball is None:
            return False
        if set(observation.robots) < {self.field.home_id, self.field.away_id}:
            return False
        x, y = observation.ball
        return (x * x + y * y) ** 0.5 <= self.field.kickoff_radius_m

    def _goal_scorer(self, observation: Observation) -> Optional[str]:
        if observation.ball is None:
            return None
        x, y = observation.ball
        if self.field.in_away_goal(x, y):
            return self.field.home_id
        if self.field.in_home_goal(x, y):
            return self.field.away_id
        return None


def _halt(robots: Mapping[str, tuple[float, float, float]]) -> dict[str, Action]:
    return {robot_id: Action(0.0, 0.0) for robot_id in robots}
