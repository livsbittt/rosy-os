"""1v1 push-ball referee. Eats observations only."""

from __future__ import annotations

from rosy_games.field import Field, Pose2D
from rosy_games.game.protocol import Observation, Phase
from rosy_games.game.state import MatchState


class SoccerGame:
    def __init__(self, field: Field | None = None) -> None:
        self.field = field or Field()
        self.phase = Phase.KICKOFF
        self.score = {self.field.home_id: 0, self.field.away_id: 0}
        self.reason = ""
        self.scorer = None

    def reset(self) -> MatchState:
        self.phase = Phase.KICKOFF
        self.reason = ""
        self.scorer = None
        return self._state()

    def step(self, observation: Observation) -> MatchState:
        if self.phase is Phase.GOAL:
            self.phase = Phase.KICKOFF
            self.reason = ""
            self.scorer = None
            return self._state()
        if self.phase is Phase.PLAY and self._lost(observation):
            self.phase = Phase.HOLD
            self.reason = "lost"
            self.scorer = None
            return self._state()
        if self.phase is Phase.HOLD:
            if not self._lost(observation):
                self.phase = Phase.PLAY
                self.reason = ""
            return self._state()
        if self.phase is Phase.KICKOFF:
            if self._kickoff_ready(observation):
                self.phase = Phase.PLAY
                self.reason = ""
            return self._state()
        scorer = self._goal_scorer(observation)
        if scorer is not None:
            self.score[scorer] += 1
            self.phase = Phase.GOAL
            self.reason = "goal"
            self.scorer = scorer
            return self._state()
        self.reason = ""
        self.scorer = None
        return self._state()

    def _state(self) -> MatchState:
        return MatchState(
            phase=self.phase,
            score=dict(self.score),
            reason=self.reason,
            scorer=self.scorer,
        )

    def _lost(self, observation: Observation) -> bool:
        if observation.lost_ball or observation.ball is None:
            return True
        if observation.lost_robots:
            return True
        needed = {self.field.home_id, self.field.away_id}
        return not needed <= set(observation.robots)

    def _kickoff_ready(self, observation: Observation) -> bool:
        if self._lost(observation) or observation.ball is None:
            return False
        x, y = observation.ball.x, observation.ball.y
        return (x * x + y * y) ** 0.5 <= self.field.kickoff_radius_m

    def _goal_scorer(self, observation: Observation) -> str | None:
        if observation.ball is None:
            return None
        x, y = observation.ball.x, observation.ball.y
        if self.field.in_away_goal(x, y):
            return self.field.home_id
        if self.field.in_home_goal(x, y):
            return self.field.away_id
        return None


def pose(*xyz: float) -> Pose2D:
    if len(xyz) == 2:
        return Pose2D(xyz[0], xyz[1], 0.0)
    return Pose2D(xyz[0], xyz[1], xyz[2])
