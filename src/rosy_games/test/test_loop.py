from rosy_games.field import Pose2D
from rosy_games.game import Observation, Phase
from rosy_games.host import MatchHost

from fakes import FakeObserver, FakePlayerClient


def _obs(
    *,
    ball=(0.0, 0.0),
    r1=(-0.4, 0.0, 0.0),
    r2=(0.4, 0.0, 3.14),
    lost_ball=False,
    robots=None,
):
    if robots is None:
        robots = {"rosy_01": Pose2D(*r1), "rosy_02": Pose2D(*r2)}
    return Observation(
        t=0.0,
        ball=None if ball is None else Pose2D(ball[0], ball[1], 0.0),
        robots=robots,
        lost_ball=lost_ball,
        lost_robots=frozenset(),
    )


def _clients(*, fail=None):
    home = FakePlayerClient("rosy_01", fail_teleop=fail == "rosy_01")
    away = FakePlayerClient("rosy_02", fail_teleop=fail == "rosy_02")
    return home, away


def test_kickoff_not_ready_teleops_zero_to_both_robots():
    home, away = _clients()
    observer = FakeObserver(_obs(ball=None, lost_ball=True))
    host = MatchHost(observer, (home, away))
    host.reset()
    state = host.tick()
    assert state.phase is Phase.KICKOFF
    assert home.teleops == [(0.0, 0.0)]
    assert away.teleops == [(0.0, 0.0)]
    assert home.estops == 0 and away.estops == 0


def test_in_play_chase_sends_positive_linear():
    home, away = _clients()
    observer = FakeObserver(
        [
            _obs(ball=(0.0, 0.0)),
            _obs(ball=(0.2, 0.0), r1=(-0.3, 0.0, 0.0)),
        ]
    )
    host = MatchHost(observer, (home, away))
    host.reset()
    first = host.tick()
    assert first.phase is Phase.PLAY
    home.teleops.clear()
    away.teleops.clear()
    second = host.tick()
    assert second.phase is Phase.PLAY
    sent = home.teleops + away.teleops
    assert sent
    assert any(linear > 0.0 for linear, _ in sent)


def test_observe_omitting_one_robot_holds_and_teleops_zero():
    home, away = _clients()
    missing = Observation(
        t=0.0,
        ball=Pose2D(0.0, 0.0, 0.0),
        robots={"rosy_01": Pose2D(-0.4, 0.0, 0.0)},
        lost_ball=False,
        lost_robots=frozenset(),
    )
    observer = FakeObserver([_obs(), missing])
    host = MatchHost(observer, (home, away))
    host.reset()
    host.tick()
    home.teleops.clear()
    away.teleops.clear()
    state = host.tick()
    assert state.phase is Phase.HOLD
    assert home.teleops == [(0.0, 0.0)]
    assert away.teleops == [(0.0, 0.0)]


def test_teleop_failure_estops_both_clients():
    home, away = _clients(fail="rosy_01")
    observer = FakeObserver(_obs())
    host = MatchHost(observer, (home, away))
    host.reset()
    host.tick()
    assert home.estops >= 1
    assert away.estops >= 1


def test_estop_all_still_stops_the_second_client_when_the_first_raises():
    home = FakePlayerClient("rosy_01", fail_estop=True)
    away = FakePlayerClient("rosy_02")
    host = MatchHost(FakeObserver(_obs()), (home, away))
    try:
        host._estop_all()
    except Exception:
        pass
    assert home.estops == 1
    assert away.estops == 1
