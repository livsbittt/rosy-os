from robot_contracts import DEPLOY, ROOT


def test_operational_compose_does_not_launch_legacy_control_stack():
    text = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
    assert "apps/control/launch" not in text
    assert "apps/control/launch/robot.launch.py" not in text


def test_operational_compose_does_not_serve_the_control_console():
    """D-77: 운용자 콘솔은 CORE /dashboard. web_node는 compose에 없다."""
    text = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
    assert "web_node" not in text
    assert "dashboard.html" not in text
    html = (ROOT / "src" / "apps" / "control" / "web" / "dashboard.html").read_text(encoding="utf-8")
    assert "<title>pinky console</title>" not in html
    assert "<title>Rosy control diagnostic</title>" in html


def test_hardware_launch_does_not_start_safety_as_final_publisher():
    nav = ROOT / "src" / "navigation" / "navigation" / "launch" / "hardware.launch.py"
    text = nav.read_text(encoding="utf-8")
    assert "apps/control" not in text
    assert "safety_node" not in text
