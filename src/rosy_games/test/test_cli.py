from pathlib import Path

from rosy_games.cli import main
from rosy_games.host.robots import load_match

CONFIG = Path(__file__).resolve().parents[1] / "config" / "match.yaml"


def test_dry_run_reads_two_robots_and_does_not_need_the_network(capsys):
    assert main(["match", "--config", str(CONFIG), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "rosy_01" in out and "rosy_02" in out
    match = load_match(CONFIG)
    assert match.field.length_m == 1.8
    assert match.robots[0].url.startswith("http://")
    assert match.robots[0].token == ""
