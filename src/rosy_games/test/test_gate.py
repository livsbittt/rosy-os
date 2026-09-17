from rosy_games.field import ZERO, Field, Pose2D, Twist
from rosy_games.game import Observation, Phase
from rosy_games.game.gate import gate
from rosy_games.game.state import MatchState


def test_gate_zeros_when_not_in_play_and_clips_ramming():
    field = Field()
    obs = Observation(
        t=0.0,
        ball=Pose2D(0.5, 0.0, 0.0),
        robots={
            "rosy_01": Pose2D(0.0, 0.0, 0.0),
            "rosy_02": Pose2D(0.1, 0.0, 0.0),
        },
        lost_ball=False,
        lost_robots=frozenset(),
    )
    hold = MatchState(phase=Phase.HOLD, score={"rosy_01": 0, "rosy_02": 0}, reason="lost")
    out = gate({"rosy_01": Twist(0.08, 0.0)}, obs, hold, field)
    assert out.twists["rosy_01"] == ZERO
    play = MatchState(phase=Phase.PLAY, score=hold.score, reason="")
    ram = gate(
        {"rosy_01": Twist(0.08, 0.0), "rosy_02": Twist(0.08, 0.0)},
        obs,
        play,
        field,
    )
    assert ram.twists["rosy_01"].linear <= 0.0
    assert ram.twists["rosy_02"].linear <= 0.0
