from rosy_games.catalog import make_game, make_policy
from rosy_games.field import Field
from rosy_games.game import SoccerGame
from rosy_games.policy import HeuristicPolicy


def test_catalog_builds_soccer_and_heuristic_from_names():
    field = Field()
    game = make_game("soccer", field)
    policy = make_policy("heuristic", field, speed=0.08)
    assert isinstance(game, SoccerGame)
    assert game.field is field
    assert isinstance(policy, HeuristicPolicy)
    assert policy.speed == 0.08


def test_catalog_rejects_unknown_kinds():
    field = Field()
    try:
        make_game("chess", field)
        raise AssertionError("unknown game must fail")
    except ValueError as exc:
        assert "chess" in str(exc)
    try:
        make_policy("neural", field)
        raise AssertionError("unknown policy must fail")
    except ValueError as exc:
        assert "neural" in str(exc)
