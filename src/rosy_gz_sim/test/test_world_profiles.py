"""월드 카탈로그 — 미로/공장 숫자는 YAML에만 있다."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "launch" / "world_profiles.py"


def _mod():
    spec = importlib.util.spec_from_file_location("world_profiles", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_worlds():
    return _mod().load_worlds()


def profile_for(name):
    return _mod().profile_for(name)


def resolve_world(*args, **kwargs):
    return _mod().resolve_world(*args, **kwargs)


def test_catalog_names_every_shipped_world():
    worlds = load_worlds()
    on_disk = {path.name for path in (ROOT / "worlds").glob("*.world")}
    # empty/default sdf worlds are not nav benches
    benches = on_disk - {"empty.world"}
    missing = benches - set(worlds)
    assert not missing, f"catalog missing worlds: {missing}"


def test_factory_and_maze_do_not_share_inflation():
    factory = profile_for("rosy_factory.world")
    maze = profile_for("rosy_maze")
    assert factory.inflation_radius == 0.25
    assert maze.inflation_radius == 0.55
    assert factory.map == "rosy_factory.yaml"
    assert maze.map == "rosy_maze.yaml"
    assert (factory.spawn_x, factory.spawn_y) != (0.0, 0.0)
    assert (maze.spawn_x, maze.spawn_y) != (factory.spawn_x, factory.spawn_y)


def test_launch_args_override_the_catalog_not_the_other_way_around():
    maze = resolve_world("rosy_maze.world", inflation_radius=0.2, spawn_x=1.0)
    assert maze.inflation_radius == 0.2
    assert maze.spawn_x == 1.0
    assert maze.map == "rosy_maze.yaml"
    untouched = resolve_world("rosy_maze.world")
    assert untouched.inflation_radius == 0.55
