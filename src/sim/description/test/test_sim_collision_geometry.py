"""Rendered collision geometry contracts for the Gazebo model."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ROBOT_XACRO = ROOT / "urdf" / "robot.urdf.xacro"


def _render_robot(*, is_sim: bool) -> ET.Element:
    if shutil.which("xacro") is None:
        pytest.skip("xacro is not installed")
    result = subprocess.run(
        [
            "xacro",
            str(ROBOT_XACRO),
            f"is_sim:={'true' if is_sim else 'false'}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return ET.fromstring(result.stdout)


def _collision_geometry_tags(robot: ET.Element) -> list[str]:
    return [
        geometry[0].tag
        for collision in robot.findall(".//collision")
        if (geometry := collision.find("geometry")) is not None and len(geometry)
    ]


def test_simulation_collisions_use_dart_supported_primitives():
    tags = _collision_geometry_tags(_render_robot(is_sim=True))

    assert tags
    assert "mesh" not in tags
    assert set(tags) <= {"box", "cylinder", "sphere"}


def test_physical_description_keeps_detailed_collision_meshes():
    tags = _collision_geometry_tags(_render_robot(is_sim=False))

    assert tags.count("mesh") == 7
