from rosy_games.field import Field
from rosy_games.game import Observation, Phase, SoccerGame
from rosy_games.game.soccer import Action


def test_reset_is_kickoff_and_does_not_start_until_the_ball_is_centred():
    game = SoccerGame()
    assert game.reset().phase is Phase.KICKOFF
    mid = Observation(ball=(0.5, 0.0), robots={"rosy_01": (0.4, 0.0, 0.0), "rosy_02": (-0.4, 0.0, 3.1)})
    still = game.step(mid, {})
    assert still.phase is Phase.KICKOFF
    assert still.actions["rosy_01"].linear == 0.0
    ready = Observation(ball=(0.0, 0.0), robots=mid.robots)
    assert game.step(ready, {}).phase is Phase.IN_PLAY


def test_a_ball_in_the_away_goal_scores_for_home_and_halts():
    game = SoccerGame()
    field = Field()
    game.phase = Phase.IN_PLAY
    obs = Observation(
        ball=(field.length_m / 2, 0.0),
        robots={"rosy_01": (0.2, 0.0, 0.0), "rosy_02": (0.6, 0.0, 0.0)},
    )
    result = game.step(obs, {"rosy_01": Action(0.08, 0.0)})
    assert result.scorer == "rosy_01"
    assert result.score["rosy_01"] == 1
    assert result.phase is Phase.KICKOFF
    assert result.actions["rosy_01"].linear == 0.0
