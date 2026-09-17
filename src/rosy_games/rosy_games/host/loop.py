"""Match loop: observe → referee → policy → gate → clients.

OpenCV belongs in an ObservationSource. This file does not import rosy_core.
"""

from __future__ import annotations

from typing import Mapping, Protocol

from rosy_games.field import Twist
from rosy_games.game import SoccerGame, gate
from rosy_games.game.protocol import Observation
from rosy_games.game.state import MatchState
from rosy_games.policy.heuristic import HeuristicPolicy


class ObservationSource(Protocol):
    def capture(self) -> Observation: ...


class PlayerClient(Protocol):
    robot_id: str

    def teleop(self, twist: Twist) -> None: ...

    def estop(self) -> None: ...


class MatchHost:
    def __init__(
        self,
        source: ObservationSource,
        clients: Mapping[str, PlayerClient],
        *,
        game: SoccerGame | None = None,
        policy: HeuristicPolicy | None = None,
    ) -> None:
        self.source = source
        self.clients = dict(clients)
        self.game = game or SoccerGame()
        self.policy = policy or HeuristicPolicy(self.game.field)

    def reset(self) -> MatchState:
        return self.game.reset()

    def tick(self) -> MatchState:
        observation = self.source.capture()
        state = self.game.step(observation)
        twists = self.policy.act(observation, state)
        try:
            commands = gate(twists, observation, state, self.game.field)
            if commands.estop:
                self._estop_all()
                return state
            for robot_id, twist in commands.twists.items():
                client = self.clients.get(robot_id)
                if client is None:
                    continue
                client.teleop(twist)
        except Exception:
            self._estop_all()
            raise
        return state

    def _estop_all(self) -> None:
        for client in self.clients.values():
            client.estop()
