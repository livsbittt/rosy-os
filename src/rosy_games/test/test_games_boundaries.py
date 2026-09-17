"""field/game/policy stay free of vision and transport. host except overhead.py has no cv2."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "rosy_games"
PURE = (
    PKG / "field",
    PKG / "game",
    PKG / "policy",
)
PURE_FORBIDDEN = ("cv2", "httpx", "rclpy", "rosy_core", "rosy_fleet")
HOST_FORBIDDEN = ("cv2", "rclpy", "rosy_core", "rosy_fleet")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_pure_layers_do_not_import_runtime_or_vision():
    banned = set(PURE_FORBIDDEN) | {"rosy_games.host", "websockets"}
    for folder in PURE:
        for path in folder.rglob("*.py"):
            hits = {name for name in _imports(path) if name in banned or name.split(".")[0] in banned}
            assert not hits, f"{path.name} imports {hits}"


def test_host_except_overhead_has_no_cv2():
    banned = set(HOST_FORBIDDEN)
    for path in (PKG / "host").rglob("*.py"):
        if path.name == "overhead.py":
            continue
        hits = {name.split(".")[0] for name in _imports(path)} & banned
        assert not hits, f"{path.name} imports {hits}"


def test_host_loop_and_transport_do_not_import_cv2():
    for name in ("loop.py", "transport.py"):
        path = PKG / "host" / name
        assert path.is_file()
        hits = _imports(path) & {"cv2"}
        assert not hits, f"{name} imports {hits}"
