"""D-62: CORE is required; other slices are opt-in presets."""

import ast
from pathlib import Path

from robot_contracts import DEPLOY, ROOT, board_caps
import yaml

CORE = ROOT / "src" / "rosy_core" / "rosy_core"
FORBIDDEN = ("rosy_omx_adapter", "rosy_control.camera", "moveit")


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


def test_core_capabilities_do_not_advertise_optional_slices():
    caps = board_caps("core")
    assert caps["navigation"]["goal_navigation"] is False
    assert caps["swarm"]["follow"] is False
    vision = caps.get("vision") or {}
    omx = caps.get("omx") or {}
    ai = caps.get("ai") or {}
    assert vision.get("enabled", False) is False
    assert omx.get("enabled", False) is False
    assert ai.get("enabled", False) is False


def test_core_package_does_not_import_optional_slice_code():
    for path in CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        for name in names:
            for banned in FORBIDDEN:
                assert name != banned and not name.startswith(banned + "."), f"{path.name} imports {name}"
