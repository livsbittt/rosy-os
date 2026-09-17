"""Device profile and Nav2 motion-limit contracts."""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "rosy_navigation"))

from rosy_navigation.profile_limits import (
    MotionLimits,
    load_motion_limits,
    validate_nav2_parameters,
    validate_requested_limits,
)


PROFILE = ROOT / "deploy" / "robot" / "config" / "profile.hardware.yaml"
NAV2 = ROOT / "src" / "rosy_navigation" / "params" / "nav2_params.yaml"


def test_global_planner_is_smac_and_rejects_unknown():
    """긴 통로에서 NavFn 역추적이 실패한다. 미지 공간은 지름길이 아니다."""
    data = yaml.safe_load(NAV2.read_text(encoding="utf-8"))
    grid = data["planner_server"]["ros__parameters"]["GridBased"]
    assert grid["plugin"] == "nav2_smac_planner::SmacPlanner2D"
    assert grid["allow_unknown"] is False


def test_hardware_profile_is_the_source_of_motion_ceilings():
    limits = load_motion_limits(PROFILE)

    assert limits == MotionLimits(max_linear_mps=0.20, max_angular_rps=0.80)
    validate_requested_limits(
        limits,
        max_linear_mps="0.20",
        max_angular_rps="0.80",
    )
    validate_nav2_parameters(NAV2, limits)


@pytest.mark.parametrize(
    ("name", "value"),
    [("max_linear_mps", 0.21), ("max_angular_rps", 0.81)],
)
def test_launch_override_above_profile_fails_closed(name, value):
    limits = load_motion_limits(PROFILE)
    requested = {"max_linear_mps": 0.20, "max_angular_rps": 0.80}
    requested[name] = value

    with pytest.raises(ValueError, match="exceeds Device profile ceiling"):
        validate_requested_limits(limits, **requested)


def test_nav2_velocity_override_above_profile_fails_closed(tmp_path):
    data = yaml.safe_load(NAV2.read_text(encoding="utf-8"))
    data["velocity_smoother"]["ros__parameters"]["max_velocity"][2] = 0.81
    path = tmp_path / "nav2.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ValueError, match="velocity_smoother.max_velocity"):
        validate_nav2_parameters(path, load_motion_limits(PROFILE))


def test_profile_with_missing_or_invalid_limits_fails_closed(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("profile:\n  max_linear_velocity: 0.2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="max_angular_velocity"):
        load_motion_limits(path)
