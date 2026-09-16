"""ROS-free Gazebo sim package surface (D-73). Launch tests stay skippable."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_and_multi_robot_launch_exist():
    package = (ROOT / "package.xml").read_text(encoding="utf-8")
    assert "<name>rosy_gz_sim</name>" in package
    assert "rosy_fleet" in package
    launch = (ROOT / "launch" / "gz_multi.launch.py").read_text(encoding="utf-8")
    assert "gz_multi" in launch or "core" in launch
    assert "rosy_core" in launch
