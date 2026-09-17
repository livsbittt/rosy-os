"""game/field/policy stay free of ROS, OpenCV, CORE, and Fleet."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PURE = (
    ROOT / "rosy_games" / "field",
    ROOT / "rosy_games" / "game",
    ROOT / "rosy_games" / "policy",
    ROOT / "rosy_games" / "host",
)
FORBIDDEN = ("rclpy", "cv2", "rosy_core", "rosy_fleet", "isaac", "torch")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_pure_layers_do_not_import_runtime_or_vision():
    for folder in PURE:
        for path in folder.glob("*.py"):
            names = _imports(path)
            hits = names & set(FORBIDDEN)
            assert not hits, f"{path.name} imports {hits}"
