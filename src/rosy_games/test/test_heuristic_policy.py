from rosy_games.field import Pose2D
from rosy_games.game import Observation
from rosy_games.policy import HeuristicPolicy


def _obs(ball, robots):
    return Observation(
        t=0.0,
        ball=Pose2D(ball[0], ball[1], 0.0),
        robots={rid: Pose2D(*pose) for rid, pose in robots.items()},
        lost_ball=False,
        lost_robots=frozenset(),
    )


def test_policy_turns_toward_the_ball_and_stops_when_the_other_robot_is_close():
    policy = HeuristicPolicy()
    far = _obs((0.5, 0.0), {"rosy_01": (0.0, 0.0, 0.0), "rosy_02": (0.0, 1.0, 0.0)})
    chase = policy.act("rosy_01", far)
    assert chase.linear > 0
    close = _obs((0.5, 0.0), {"rosy_01": (0.0, 0.0, 0.0), "rosy_02": (0.1, 0.0, 0.0)})
    hold = policy.act("rosy_01", close)
    assert hold.linear <= 0
