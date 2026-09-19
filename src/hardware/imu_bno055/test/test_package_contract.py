"""ROS-free checks for the optional BNO055 package boundary."""

from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_optional_profile_defaults_to_no_reset_and_known_units():
    data = yaml.safe_load((ROOT / "config" / "bno055.yaml").read_text(encoding="utf-8"))
    params = data["imu_bno055"]["ros__parameters"]

    assert params == {
        "interface": "/dev/i2c-0",
        "frame_id": "imu_link",
        "rate": 100.0,
        "reset_on_start": False,
    }


def test_launch_requires_explicit_reset_argument_and_uses_driver_node():
    text = (ROOT / "launch" / "bno055.launch.py").read_text(encoding="utf-8")

    assert 'DeclareLaunchArgument("reset_on_start", default_value="false")' in text
    assert '"config", "bno055.yaml"' in text
    assert 'package="imu_bno055"' in text
    assert 'executable="main_node"' in text


def test_package_declares_runtime_dependencies_and_cmake_sample_test():
    package = ET.parse(ROOT / "package.xml").getroot()
    dependencies = {
        element.text
        for element in package.findall("depend")
        if element.text
    }
    assert {"rclcpp", "sensor_msgs", "std_msgs", "realtime_tools"} <= dependencies

    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "src/bno055_device.cpp" in cmake
    assert "test_imu_sample" in cmake
    assert "CMAKE_SYSTEM_PROCESSOR STREQUAL \"aarch64\"" in cmake
