"""Match loop: observe → referee → policy → twist sink.

OpenCV belongs in an ObservationSource implementation, not here. The sink is
whatever talks to CORE teleop; this module does not import rosy_core.
"""

from __future__ import annotations

from typing import Protocol

from rosy_games.game.soccer import Action, Observation, SoccerGame, StepResult
from rosy_games.policy.heuristic import HeuristicPolicy


class ObservationSource(Protocol):
    def capture(self) -> Observation: ...


class TwistSink(Protocol):
    def send(self, robot_id: str, action: Action) -> None: ...


class MatchHost:
    def __init__(
        self,
        source: ObservationSource,
        sink: TwistSink,
        *,
        game: SoccerGame | None = None,
        policy: HeuristicPolicy | None = None,
    ) -> None:
        self.source = source
        self.sink = sink
        self.game = game or SoccerGame()
        self.policy = policy or HeuristicPolicy(self.game.field)

    def reset(self) -> StepResult:
        result = self.game.reset()
        self._emit(result)
        return result

    def tick(self) -> StepResult:
        observation = self.source.capture()
        proposed = {
            robot_id: self.policy.act(robot_id, observation)
            for robot_id in observation.robots
        }
        result = self.game.step(observation, proposed)
        self._emit(result)
        return result

    def _emit(self, result: StepResult) -> None:
        for robot_id, action in result.actions.items():
            self.sink.send(robot_id, action)
