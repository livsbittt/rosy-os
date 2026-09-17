"""Match loop: observe → referee → policy → twist sink.

OpenCV belongs in an ObservationSource implementation, not here. The sink is
whatever talks to CORE teleop; this module does not import rosy_core.
"""

from __future__ import annotations

from typing import Protocol

from rosy_games.field import ZERO, Twist
from rosy_games.game import MatchState, Observation, Phase, SoccerGame
from rosy_games.policy.heuristic import HeuristicPolicy


class ObservationSource(Protocol):
    def capture(self) -> Observation: ...


class TwistSink(Protocol):
    def send(self, robot_id: str, action: Twist) -> None: ...


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

    def reset(self) -> MatchState:
        return self.game.reset()

    def tick(self) -> MatchState:
        observation = self.source.capture()
        result = self.game.step(observation)
        for robot_id in observation.robots:
            twist = (
                self.policy.act(robot_id, observation)
                if result.phase is Phase.PLAY
                else ZERO
            )
            self.sink.send(robot_id, twist)
        return result
