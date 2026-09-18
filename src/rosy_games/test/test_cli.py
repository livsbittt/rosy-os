"""CLI dry-run loads match.yaml without opening a network."""

from pathlib import Path

from rosy_games.cli import main, parse_args
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
    assert setup.game == "soccer"
    assert setup.policy == "heuristic"
    assert setup.camera.index == 0
    assert setup.camera.corner_ids == (10, 11, 12, 13)


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


def test_cli_default_observer_is_hold_not_the_camera():
    """D-95: 기본은 hold. overhead는 명시할 때만."""
    args = parse_args(["match", "--config", str(MATCH), "--dry-run"])
    assert args.observer == "hold"


def test_load_match_assigns_home_from_attacks_not_row_order(tmp_path):
    text = MATCH.read_text(encoding="utf-8")
    swapped = text.replace("rosy_01", "TMP").replace("rosy_02", "rosy_01").replace("TMP", "rosy_02")
    path = tmp_path / "match.yaml"
    path.write_text(swapped, encoding="utf-8")
    setup = load_match(path)
    assert setup.field.home_id == "rosy_02"
    assert setup.field.away_id == "rosy_01"
    assert setup.robots[0].attacks == "positive_x"


def test_load_match_overlays_sibling_local_yaml(tmp_path):
    (tmp_path / "match.yaml").write_text(MATCH.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "match.local.yaml").write_text(
        "robots:\n  - id: rosy_01\n    url: http://127.0.0.1:9\n    token: secret\n",
        encoding="utf-8",
    )
    setup = load_match(tmp_path / "match.yaml")
    assert setup.robots[0].url == "http://127.0.0.1:9"
    assert setup.robots[0].token == "secret"
    assert setup.robots[1].url == "http://rosy-02.local:8080"


def test_live_match_arms_manual_and_holds_without_a_camera(monkeypatch):
    created = []

    class FakeHttp:
        def __init__(self, endpoint, **_kwargs):
            self.robot_id = endpoint.id
            self.manual = 0
            self.teleops: list[tuple[float, float]] = []
            self.estops = 0
            created.append(self)

        def set_manual(self) -> None:
            self.manual += 1

        def teleop(self, linear: float, angular: float) -> None:
            self.teleops.append((linear, angular))

        def estop(self) -> None:
            self.estops += 1

        def close(self) -> None:
            pass

    monkeypatch.setattr("rosy_games.cli.HttpPlayerClient", FakeHttp)
    assert main(["match", "--config", str(MATCH), "--ticks", "2"]) == 0
    assert [c.robot_id for c in created] == ["rosy_01", "rosy_02"]
    assert all(c.manual == 1 for c in created)
    assert all(c.teleops == [(0.0, 0.0), (0.0, 0.0)] for c in created)
    assert all(c.estops >= 1 for c in created)

