"""In-process doubles for the match loop. No HTTP."""

from __future__ import annotations

from rosy_games.game import Observation


class FakeObserver:
    def __init__(self, frames: Observation | list[Observation]) -> None:
        self.frames = frames if isinstance(frames, list) else [frames]
        self.i = 0

    def observe(self) -> Observation:
        frame = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return frame


class FakePlayerClient:
    def __init__(self, robot_id: str, *, fail_teleop: bool = False) -> None:
        self.robot_id = robot_id
        self.fail_teleop = fail_teleop
        self.teleops: list[tuple[float, float]] = []
        self.estops = 0
        self.manual = 0

    def set_manual(self) -> None:
        self.manual += 1

    def teleop(self, linear: float, angular: float) -> None:
        if self.fail_teleop:
            raise RuntimeError("teleop failed")
        self.teleops.append((linear, angular))

    def estop(self) -> None:
        self.estops += 1
