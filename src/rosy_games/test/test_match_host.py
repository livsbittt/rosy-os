from rosy_games.game import Observation, Phase
from rosy_games.host import MatchHost


class _Source:
    def __init__(self) -> None:
        self.frames = [
            Observation(ball=None, robots={"rosy_01": (-0.4, 0.0, 0.0), "rosy_02": (0.4, 0.0, 3.14)}),
            Observation(ball=(0.0, 0.0), robots={"rosy_01": (-0.4, 0.0, 0.0), "rosy_02": (0.4, 0.0, 3.14)}),
            Observation(ball=(0.2, 0.0), robots={"rosy_01": (-0.3, 0.0, 0.0), "rosy_02": (0.4, 0.0, 3.14)}),
        ]
        self.i = 0

    def capture(self) -> Observation:
        frame = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return frame


class _Sink:
    def __init__(self) -> None:
        self.sent: list[tuple[str, float, float]] = []

    def send(self, robot_id, action) -> None:
        self.sent.append((robot_id, action.linear, action.angular))


def test_host_holds_twists_until_kickoff_then_lets_policy_drive():
    sink = _Sink()
    host = MatchHost(_Source(), sink)
    host.reset()
    first = host.tick()
    assert first.phase is Phase.KICKOFF
    assert all(linear == 0.0 for _, linear, _ in sink.sent)
    sink.sent.clear()
    second = host.tick()
    assert second.phase is Phase.IN_PLAY
    third = host.tick()
    assert third.phase is Phase.IN_PLAY
    assert any(linear > 0.0 for _, linear, _ in sink.sent)
