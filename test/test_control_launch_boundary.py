from robot_contracts import DEPLOY, ROOT


def test_operational_compose_does_not_launch_legacy_control_stack():
    text = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
    assert "rosy_control/launch" not in text
    assert "rosy_control/launch/robot.launch.py" not in text


def test_hardware_launch_does_not_start_safety_as_final_publisher():
    nav = ROOT / "src" / "rosy_navigation" / "launch" / "hardware.launch.py"
    text = nav.read_text(encoding="utf-8")
    assert "rosy_control" not in text
    assert "safety_node" not in text
