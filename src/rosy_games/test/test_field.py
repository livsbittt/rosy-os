from rosy_games.field import ZERO, Field, Pose2D, Twist


def test_home_scores_in_the_away_goal_mouth():
    field = Field()
    assert field.in_away_goal(field.length_m / 2, 0.0)
    assert not field.in_away_goal(0.0, 0.0)
    assert field.in_bounds(0.0, 0.0)
    assert not field.in_bounds(field.length_m, 0.0)


def test_zero_twist_is_a_full_stop():
    assert ZERO == Twist(0.0, 0.0)
    pose = Pose2D(0.1, -0.2, 1.5)
    assert (pose.x, pose.y, pose.yaw) == (0.1, -0.2, 1.5)
