"""CAP-001 is a schema. HWA-003: advertised capability is derived from profile + mode."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rosy_core.capability import (
    CapabilityContractError,
    derive_capability,
    parse_capability,
)
from rosy_core.profile import RobotProfile

CORE_CONFIG = Path(__file__).resolve().parents[1] / "config"
DEVICE_CONFIG = (
    Path(__file__).resolve().parents[3] / "deploy" / "robot" / "config"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_parse_rejects_an_unknown_capability_key():
    data = _yaml(DEVICE_CONFIG / "capabilities.core.yaml")
    data["broker"] = "mqtt"

    with pytest.raises(CapabilityContractError, match="broker"):
        parse_capability(data)


def test_parse_rejects_a_descriptor_missing_swarm():
    data = _yaml(DEVICE_CONFIG / "capabilities.core.yaml")
    del data["swarm"]

    with pytest.raises(CapabilityContractError, match="swarm"):
        parse_capability(data)


@pytest.mark.parametrize("mode", ["core", "motor", "hardware"])
def test_device_overlay_equals_profile_and_mode_derivation(mode):
    profile = RobotProfile.load(DEVICE_CONFIG / f"profile.{mode}.yaml")
    advertised = parse_capability(_yaml(DEVICE_CONFIG / f"capabilities.{mode}.yaml"))

    assert derive_capability(profile, mode).to_dict() == advertised.to_dict()


def test_core_mode_does_not_advertise_sensors_the_profile_lists():
    profile = RobotProfile.load(CORE_CONFIG / "profile.pinky_pro.yaml")
    cap = derive_capability(profile, "core")

    assert cap.sensors == []
    assert cap.teleop is False
    assert cap.slam is False
    assert cap.swarm.follow is False
    assert cap.swarm.lead is False
    assert cap.navigation.goal_navigation is False


def test_packaged_capabilities_match_default_runtime_mode_core():
    """rosy_default.yaml runtime.mode is core. The packaged advertisement must match."""
    profile = RobotProfile.load(CORE_CONFIG / "profile.pinky_pro.yaml")
    packaged = parse_capability(_yaml(CORE_CONFIG / "capabilities.yaml"))

    assert packaged.to_dict() == derive_capability(profile, "core").to_dict()


def test_a_file_that_advertises_more_than_the_mode_is_refused():
    from rosy_core.capability import bind_capability

    profile = RobotProfile.load(CORE_CONFIG / "profile.pinky_pro.yaml")
    lying = _yaml(CORE_CONFIG / "capabilities.yaml")
    lying["slam"] = True
    lying["swarm"] = {"follow": True, "lead": True}

    with pytest.raises(CapabilityContractError, match="does not match"):
        bind_capability(profile, "core", lying)
