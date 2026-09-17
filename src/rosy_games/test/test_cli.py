"""CLI dry-run loads match.yaml without opening a network."""

from pathlib import Path

from rosy_games.cli import main
from rosy_games.host.robots import load_match

PKG = Path(__file__).resolve().parents[1]
MATCH = PKG / "config" / "match.yaml"


def test_load_match_builds_field_and_two_endpoints():
    setup = load_match(MATCH)
    field, robots = setup.field, setup.robots
    assert field.length_m == 2.0
    assert field.width_m == 1.4
    assert field.goal_width_m == 0.35
    assert field.min_spacing_m == 0.35
    assert field.home_id == "rosy_01"
    assert field.away_id == "rosy_02"
    assert [r.id for r in robots] == ["rosy_01", "rosy_02"]
    assert robots[0].url == "http://rosy-01.local:8080"
    assert robots[1].url == "http://rosy-02.local:8080"
    assert robots[0].token == ""
    assert robots[1].token == ""
    assert robots[0].aruco_id == 1
    assert robots[1].aruco_id == 2
    assert robots[0].attacks == "positive_x"
    assert robots[1].attacks == "negative_x"


def test_dry_run_prints_both_robots_without_opening_a_socket(monkeypatch, capsys):
    import socket

    def boom(*_a, **_k):
        raise AssertionError("dry-run must not open a network")

    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)

    assert main(["match", "--config", str(MATCH), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "rosy_01" in out
    assert "rosy_02" in out
