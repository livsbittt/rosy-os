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
    assert setup.linear == 0.08
    assert setup.angular == 0.40
    assert setup.camera.lost_hold_s == 0.5
    assert setup.goals.home_id == 20
    assert setup.goals.away_id == 21
    assert setup.goals.hsv_low is None
    assert setup.goals.hsv_high is None


def test_dry_run_prints_both_robots_without_opening_a_socket(monkeypatch, capsys):
    import socket

    def boom(*_a, **_k):
        raise AssertionError("dry-run must not open a network")

    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)

    assert main(["match", "--config", str(MATCH), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "goals 20/21" in out
    assert "rosy_01" in out
    assert "rosy_02" in out


def test_load_match_defaults_goal_markers_when_yaml_omits_them(tmp_path):
    text = MATCH.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("goals:") and "home_id: 20" not in line and "away_id: 21" not in line]
    path = tmp_path / "match.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    setup = load_match(path)
    assert setup.goals.home_id == 20
    assert setup.goals.away_id == 21


def test_load_match_overlays_goal_hsv(tmp_path):
    (tmp_path / "match.yaml").write_text(MATCH.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "match.local.yaml").write_text(
        "goals:\n  hsv_low: [40, 80, 80]\n  hsv_high: [80, 255, 255]\n",
        encoding="utf-8",
    )
    setup = load_match(tmp_path / "match.yaml")
    assert setup.goals.home_id == 20
    assert setup.goals.hsv_low == (40, 80, 80)
    assert setup.goals.hsv_high == (80, 255, 255)


def test_cli_default_observer_is_hold_not_the_camera():
    """D-95: 기본은 hold. overhead는 명시할 때만."""
    args = parse_args(["match", "--config", str(MATCH), "--dry-run"])
    assert args.observer == "hold"


def test_cli_default_preview_is_off():
    """D-101: 미리보기는 명시할 때만. 기본 CLI가 포트를 열지 않는다."""
    args = parse_args(["match", "--config", str(MATCH), "--dry-run"])
    assert args.preview is False


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
            self.limits: list[tuple[float, float]] = []
            created.append(self)

        def set_manual(self) -> None:
            self.manual += 1

        def set_limits(self, linear: float, angular: float) -> None:
            self.limits.append((linear, angular))

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
    assert all(c.limits == [(0.08, 0.40)] for c in created)
    assert all(c.teleops == [(0.0, 0.0), (0.0, 0.0)] for c in created)
    assert all(c.estops >= 1 for c in created)


def test_preview_without_ticks_runs_until_interrupt(monkeypatch):
    seen: dict[str, object] = {}

    class FakeHttp:
        def __init__(self, endpoint, **_kwargs):
            self.robot_id = endpoint.id

        def set_manual(self) -> None:
            pass

        def teleop(self, linear: float, angular: float) -> None:
            pass

        def estop(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeServer:
        def __init__(self, board, **_kwargs):
            seen["board"] = board

        def start(self) -> str:
            return "http://127.0.0.1:9/"

        def close(self) -> None:
            seen["closed"] = True

    def fake_run(host, ticks=1, period_s=0.0, **_kwargs):
        seen["ticks"] = ticks
        seen["period_s"] = period_s
        return []

    monkeypatch.setattr("rosy_games.cli.HttpPlayerClient", FakeHttp)
    monkeypatch.setattr("rosy_games.host.preview.PreviewServer", FakeServer)
    monkeypatch.setattr("rosy_games.cli.run_match", fake_run)
    assert main(["match", "--config", str(MATCH), "--preview"]) == 0
    assert seen["ticks"] is None
    assert seen["period_s"] == 0.05
    assert seen["closed"] is True


def test_match_without_ticks_is_live_even_without_preview(monkeypatch):
    """D-102: preview가 없어도 --ticks 없으면 20 Hz 루프다."""
    seen: dict[str, object] = {}

    class FakeHttp:
        def __init__(self, endpoint, **_kwargs):
            self.robot_id = endpoint.id

        def set_manual(self) -> None:
            pass

        def teleop(self, linear: float, angular: float) -> None:
            pass

        def estop(self) -> None:
            pass

        def close(self) -> None:
            pass

    def fake_run(host, ticks=1, period_s=0.0, **_kwargs):
        seen["ticks"] = ticks
        seen["period_s"] = period_s
        return []

    monkeypatch.setattr("rosy_games.cli.HttpPlayerClient", FakeHttp)
    monkeypatch.setattr("rosy_games.cli.run_match", fake_run)
    assert main(["match", "--config", str(MATCH)]) == 0
    assert seen["ticks"] is None
    assert seen["period_s"] == 0.05


def test_host_refuses_a_period_slower_than_the_watchdog(tmp_path, monkeypatch):
    text = MATCH.read_text(encoding="utf-8").replace("lost_hold_s: 0.5", "lost_hold_s: 0.01")
    path = tmp_path / "match.yaml"
    path.write_text(text, encoding="utf-8")

    class FakeHttp:
        def __init__(self, endpoint, **_kwargs):
            self.robot_id = endpoint.id

        def set_manual(self) -> None:
            pass

        def teleop(self, linear: float, angular: float) -> None:
            pass

        def estop(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr("rosy_games.cli.HttpPlayerClient", FakeHttp)
    try:
        main(["match", "--config", str(path)])
        raise AssertionError("period must not exceed lost_hold_s")
    except ValueError as exc:
        assert "lost_hold" in str(exc)

