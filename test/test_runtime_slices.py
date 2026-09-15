"""D-62: CORE is required; other slices are opt-in presets."""

from robot_contracts import DEPLOY
import yaml


def board():
    return yaml.safe_load((DEPLOY / "config" / "board.yaml").read_text(encoding="utf-8"))


def test_core_is_the_only_required_slice():
    data = board()
    assert data["slices"]["required"] == ["core"]
    available = set(data["slices"]["available"])
    assert available >= {"motor", "io", "nav", "vision", "omx", "ai"}
    assert "core" not in available


def test_presets_match_current_runtime_modes():
    presets = board()["presets"]
    assert presets["core"] == ["core"]
    assert presets["motor"] == ["core", "motor"]
    assert presets["hardware"] == ["core", "motor", "io", "nav"]
    for extra in ("vision", "omx", "ai"):
        assert extra not in presets["core"]
        assert extra not in presets["motor"]
        assert extra not in presets["hardware"]
