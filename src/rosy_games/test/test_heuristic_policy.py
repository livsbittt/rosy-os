from rosy_games.field import Pose2D
from rosy_games.game import Observation, Phase
from rosy_games.game.state import MatchState
from rosy_games.policy import HeuristicPolicy


def _obs(r2):
    return Observation(
        t=0.0,
        ball=Pose2D(0.5, 0.0, 0.0),
        robots={
            "rosy_01": Pose2D(0.0, 0.0, 0.0),
            "rosy_02": Pose2D(*r2),
        },
    )


def test_policy_turns_toward_the_ball_and_stops_when_the_other_robot_is_close():
    policy = HeuristicPolicy()
    play = MatchState(phase=Phase.PLAY, score={"rosy_01": 0, "rosy_02": 0})
    chase = policy.act(_obs((0.0, 1.0, 0.0)), play)
    assert chase["rosy_01"].linear > 0
    hold = policy.act(_obs((0.1, 0.0, 0.0)), play)
    assert hold["rosy_01"].linear <= 0
