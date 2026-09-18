"""D-121: Cyclone is applied before rclpy.init. Web does not set RMW."""

from pathlib import Path

import pytest

from rosy_core.system.rmw import REQUIRED_RMW, RmwError, apply_cyclone_rmw

ROOT = Path(__file__).resolve().parents[1]


def test_empty_rmw_is_filled_with_cyclone():
    env = {}
    assert apply_cyclone_rmw(env) == REQUIRED_RMW
    assert env["RMW_IMPLEMENTATION"] == "rmw_cyclonedds_cpp"


def test_cyclone_rmw_is_left_alone():
    env = {"RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp"}
    assert apply_cyclone_rmw(env) == "rmw_cyclonedds_cpp"
    assert env["RMW_IMPLEMENTATION"] == "rmw_cyclonedds_cpp"


def test_foreign_rmw_is_refused_not_overwritten():
    env = {"RMW_IMPLEMENTATION": "rmw_fastrtps_cpp"}
    with pytest.raises(RmwError, match="rmw_cyclonedds_cpp"):
        apply_cyclone_rmw(env)
    assert env["RMW_IMPLEMENTATION"] == "rmw_fastrtps_cpp"


def test_core_main_applies_cyclone_before_rclpy_init():
    text = (ROOT / "rosy_core" / "main.py").read_text(encoding="utf-8")
    apply_at = text.find("apply_cyclone_rmw")
    init_at = text.find("rclpy.init")
    assert apply_at != -1
    assert init_at != -1
    assert apply_at < init_at


def test_no_api_changes_rmw():
    api = ROOT / "rosy_core" / "api"
    for path in api.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "apply_cyclone_rmw" not in text, path
        assert "/rmw" not in text, path
