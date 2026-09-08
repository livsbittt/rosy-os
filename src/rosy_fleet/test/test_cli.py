"""CLI 는 파싱과 배선만 한다. 실제 로봇은 Task 14 의 시뮬 계측이 본다."""

import pytest
from fakes import run

from rosy_fleet import cli
from rosy_fleet.formation.geometry import Formation
from rosy_fleet.swarm.robots import RobotEndpoint, write_robots
from rosy_fleet.swarm.session import FormationSpec, HoldPolicy


def _write(tmp_path):
    p = tmp_path / "robots.yaml"
    write_robots(p, [RobotEndpoint("rosy_01", "http://a:8080", "t1"),
                     RobotEndpoint("rosy_02", "http://b:8080", "t2"),
                     RobotEndpoint("rosy_03", "http://c:8080", "t3")])
    return p


def test_formation_args_build_a_spec_and_split_leader_from_followers(tmp_path):
    p = _write(tmp_path)
    args = cli.parse_args(["formation", "--robots", str(p), "--leader", "rosy_02",
                           "--formation", "V", "--spacing", "0.7", "--max-speed", "0.12",
                           "--policy", "ABORT", "--grid-cols", "3"])
    leader, followers = cli.split_robots(args)
    assert leader.robot_id == "rosy_02"
    assert [f.robot_id for f in followers] == ["rosy_01", "rosy_03"]
    spec = cli.spec_from(args)
    assert spec == FormationSpec(Formation.V, spacing=0.7, grid_cols=3, max_speed=0.12,
                                 stream_timeout_ms=1000)
    assert cli.policy_from(args) is HoldPolicy.ABORT


def test_an_unknown_leader_is_refused(tmp_path):
    p = _write(tmp_path)
    args = cli.parse_args(["formation", "--robots", str(p), "--leader", "rosy_09"])
    with pytest.raises(SystemExit):
        cli.split_robots(args)


def test_relay_defaults(tmp_path):
    p = _write(tmp_path)
    args = cli.parse_args(["relay", "--robots", str(p), "--leader", "rosy_01"])
    assert args.command == "relay"
    leader, followers = cli.split_robots(args)
    assert leader.robot_id == "rosy_01" and len(followers) == 2


def test_console_commands_map_to_session_methods():
    class Recorder:
        def __init__(self):
            self.calls = []
            self.state = type("S", (), {"value": "RUNNING"})()
            self.reason = None

        async def reform(self, spec):
            self.calls.append(("reform", spec))

        async def resume(self):
            self.calls.append(("resume",))

        async def stop(self):
            self.calls.append(("stop",))

    rec = Recorder()
    base = FormationSpec(Formation.COLUMN, spacing=0.6)
    assert run(cli.handle_command("reform LINE 0.8", rec, base)) is True
    assert run(cli.handle_command("resume", rec, base)) is True
    assert run(cli.handle_command("status", rec, base)) is True
    assert run(cli.handle_command("stop", rec, base)) is False
    assert rec.calls[0] == ("reform", FormationSpec(Formation.LINE, spacing=0.8))
    assert rec.calls[1:] == [("resume",), ("stop",)]


def test_a_bad_console_command_does_not_end_the_session():
    class Recorder:
        state = type("S", (), {"value": "RUNNING"})()
        reason = None

    base = FormationSpec(Formation.COLUMN, spacing=0.6)
    assert run(cli.handle_command("reform TRIANGLE", Recorder(), base)) is True
    assert run(cli.handle_command("dance", Recorder(), base)) is True


def test_a_reform_that_ends_in_a_hold_says_so(capsys):
    """reform 이 재개하지 않고 끝났다는 것을 운영자가 다음 통계 줄까지 기다려 알면 늦다."""
    class Held:
        def __init__(self):
            self.state = type("S", (), {"value": "HOLDING"})()
            self.reason = ("safety.estop", "rosy_03")

        async def reform(self, spec):
            self.reformed = spec

    held = Held()
    base = FormationSpec(Formation.COLUMN, spacing=0.6)
    assert run(cli.handle_command("reform LINE", held, base)) is True
    out = capsys.readouterr().out
    assert out.startswith("held:")
    assert "safety.estop" in out
