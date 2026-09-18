"""Match loop: observe → referee → policy → gate → PlayerClient.

OpenCV belongs in an Observer implementation, not here. PlayerClient is
whatever talks to CORE teleop; this module does not import rosy_core.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from rosy_games.field import ZERO
from rosy_games.game import MatchState, SoccerGame
from rosy_games.game.protocol import Game
from rosy_games.game.gate import CommandSet, gate
from rosy_games.host.observer import Observer
from rosy_games.host.preview import overlay_payload
from rosy_games.policy.heuristic import HeuristicPolicy
from rosy_games.policy.protocol import Policy


class PlayerClient(Protocol):
    robot_id: str

    def set_manual(self) -> None: ...

    def set_limits(self, linear: float, angular: float) -> None: ...

    def teleop(self, linear: float, angular: float) -> None: ...

    def estop(self) -> None: ...


class MatchHost:
    def __init__(
        self,
        observer: Observer,
        clients: Iterable[PlayerClient],
        *,
        game: Game | None = None,
        policy: Policy | None = None,
        preview=None,
        max_linear: float | None = None,
        max_angular: float | None = None,
    ) -> None:
        self.observer = observer
        self.clients = tuple(clients)
        self.game = game or SoccerGame()
        self.policy = policy or HeuristicPolicy(self.game.field)
        self.preview = preview
        self.max_linear = max_linear
        self.max_angular = max_angular

    def reset(self) -> MatchState:
        self.arm()
        return self.game.reset()

    def arm(self) -> None:
        """Put every robot in MANUAL before the first tick. Failure stops both."""
        try:
            for client in self.clients:
                client.set_manual()
                if self.max_linear is not None:
                    angular = 0.40 if self.max_angular is None else self.max_angular
                    client.set_limits(self.max_linear, angular)
        except Exception:
            self.halt()
            raise

    def halt(self) -> None:
        try:
            self._estop_all()
        except Exception:
            pass

    def tick(self) -> MatchState:
        try:
            obs = self.observer.observe()
            state = self.game.step(obs)
            if self.preview is not None:
                markers = getattr(self.observer, "last_markers", ())
                jpeg = getattr(self.observer, "last_jpeg", None)
                self.preview.publish(
                    overlay_payload(
                        self.game.field,
                        obs,
                        state,
                        markers=markers,
                        has_frame=jpeg is not None,
                    ),
                    jpeg=jpeg,
                )
            twists = self.policy.act(obs, state)
            commands = gate(
                twists,
                obs,
                state,
                self.game.field,
                max_linear=self.max_linear,
                max_angular=self.max_angular,
            )
            if not commands.estop:
                try:
                    self._teleop_all(commands)
                except Exception:
                    commands = CommandSet(twists=dict(commands.twists), estop=True)
            if commands.estop:
                self._estop_all()
            return state
        except Exception:
            self.halt()
            raise

    def _teleop_all(self, commands: CommandSet) -> None:
        for client in self.clients:
            twist = commands.twists.get(client.robot_id, ZERO)
            client.teleop(twist.linear, twist.angular)

    def _estop_all(self) -> None:
        errors: list[BaseException] = []
        for client in self.clients:
            try:
                client.estop()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise ExceptionGroup("estop failed", errors)
