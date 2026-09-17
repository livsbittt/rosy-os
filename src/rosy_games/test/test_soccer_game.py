from rosy_games.field import Field, Pose2D
from rosy_games.game import Observation, Phase, SoccerGame


def _obs(*, ball=(0.0, 0.0), r1=(-0.4, 0.0, 0.0), r2=(0.4, 0.0, 3.1), lost_ball=False, lost=()):
    return Observation(
        t=0.0,
        ball=None if ball is None else Pose2D(ball[0], ball[1], 0.0),
        robots={"rosy_01": Pose2D(*r1), "rosy_02": Pose2D(*r2)},
        lost_ball=lost_ball,
        lost_robots=frozenset(lost),
    )


def test_reset_is_kickoff_and_does_not_start_until_the_ball_is_centred():
    game = SoccerGame()
    assert game.reset().phase is Phase.KICKOFF
    mid = _obs(ball=(0.5, 0.0), r1=(0.4, 0.0, 0.0), r2=(-0.4, 0.0, 3.1))
    still = game.step(mid)
    assert still.phase is Phase.KICKOFF
    ready = _obs(ball=(0.0, 0.0), r1=(0.4, 0.0, 0.0), r2=(-0.4, 0.0, 3.1))
    assert game.step(ready).phase is Phase.PLAY


def test_a_ball_in_the_away_goal_scores_for_home_and_halts():
    game = SoccerGame()
    field = Field()
    game.step(_obs())
    obs = _obs(ball=(field.length_m / 2, 0.0), r1=(0.2, 0.0, 0.0), r2=(0.6, 0.0, 0.0))
    result = game.step(obs)
    assert result.scorer == "rosy_01"
    assert result.score["rosy_01"] == 1
    nxt = game.step(obs)
    assert nxt.phase is Phase.KICKOFF


def test_missing_ball_in_play_holds():
    game = SoccerGame()
    game.step(_obs())  # kickoff -> play
    held = game.step(_obs(ball=None, lost_ball=True))
    assert held.phase is Phase.HOLD
    assert held.score["rosy_01"] == 0
