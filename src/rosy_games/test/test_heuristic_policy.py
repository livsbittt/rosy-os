from rosy_games.game import Observation
from rosy_games.policy import HeuristicPolicy


def test_policy_turns_toward_the_ball_and_stops_when_the_other_robot_is_close():
    policy = HeuristicPolicy()
    far = Observation(
        ball=(0.5, 0.0),
        robots={"rosy_01": (0.0, 0.0, 0.0), "rosy_02": (0.0, 1.0, 0.0)},
    )
    chase = policy.act("rosy_01", far)
    assert chase.linear > 0
    close = Observation(
        ball=(0.5, 0.0),
        robots={"rosy_01": (0.0, 0.0, 0.0), "rosy_02": (0.1, 0.0, 0.0)},
    )
    hold = policy.act("rosy_01", close)
    assert hold.linear <= 0
