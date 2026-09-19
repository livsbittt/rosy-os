"""ROS-free ADC driver package surface (D-73)."""

from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def test_package_declares_rclcpp_and_sensor_msgs():
    package = ET.parse(ROOT / "package.xml").getroot()
    name = package.find("name")
    assert name is not None and name.text == "sensor_adc"
    dependencies = {
        element.text
        for element in package.findall("depend")
        if element.text
    }
    assert {"rclcpp", "sensor_msgs", "std_msgs"} <= dependencies


def test_node_source_exists():
    source = ROOT / "src" / "main_node.cpp"
    assert source.is_file()
    text = source.read_text(encoding="utf-8")
    assert "rclcpp" in text
