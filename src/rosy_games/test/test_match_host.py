from rosy_games.field import Pose2D, Twist
from rosy_games.game import Observation, Phase
from rosy_games.host import MatchHost


class _Source:
    def __init__(self) -> None:
        self.frames = [
            Observation(
                t=0.0,
                ball=None,
                robots={
                    "rosy_01": Pose2D(-0.4, 0.0, 0.0),
                    "rosy_02": Pose2D(0.4, 0.0, 3.14),
                },
            ),
            Observation(
                t=0.1,
                ball=Pose2D(0.0, 0.0, 0.0),
                robots={
                    "rosy_01": Pose2D(-0.4, 0.0, 0.0),
                    "rosy_02": Pose2D(0.4, 0.0, 3.14),
                },
            ),
            Observation(
                t=0.2,
                ball=Pose2D(0.2, 0.0, 0.0),
                robots={
                    "rosy_01": Pose2D(-0.3, 0.0, 0.0),
                    "rosy_02": Pose2D(0.4, 0.0, 3.14),
                },
            ),
        ]
        self.i = 0

    def capture(self) -> Observation:
        frame = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return frame


class _Client:
    def __init__(self, robot_id: str, *, fail: bool = False) -> None:
        self.robot_id = robot_id
        self.teleops: list[Twist] = []
        self.estops = 0
        self.fail = fail

    def teleop(self, twist: Twist) -> None:
        if self.fail:
            raise ConnectionError("core down")
        self.teleops.append(twist)

    def estop(self) -> None:
        self.estops += 1


def test_host_holds_twists_until_kickoff_then_lets_policy_drive():
    home = _Client("rosy_01")
    away = _Client("rosy_02")
    host = MatchHost(_Source(), {"rosy_01": home, "rosy_02": away})
    host.reset()
    first = host.tick()
    assert first.phase is Phase.KICKOFF
    assert all(t.linear == 0.0 for t in home.teleops)
    home.teleops.clear()
    second = host.tick()
    assert second.phase is Phase.PLAY
    third = host.tick()
    assert third.phase is Phase.PLAY
    assert any(t.linear > 0.0 for t in home.teleops)


def test_a_failed_teleop_stops_both_robots():
    home = _Client("rosy_01", fail=True)
    away = _Client("rosy_02")
    source = _Source()
    source.i = 1
    host = MatchHost(source, {"rosy_01": home, "rosy_02": away})
    host.game.phase = Phase.PLAY
    try:
        host.tick()
    except ConnectionError:
        pass
    assert home.estops >= 1 and away.estops >= 1
