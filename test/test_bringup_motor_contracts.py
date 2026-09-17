"""Static integration contracts for the ROS motor command path."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
BRINGUP = ROOT / "src" / "rosy_bringup"


def test_launch_exposes_all_motor_limits_to_the_node():
    launch = (BRINGUP / "launch" / "bringup_robot.launch.py").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(launch.split())

    for name, default in (
        ("max_linear_mps", "0.20"),
        ("max_angular_rps", "0.80"),
        ("max_wheel_rpm", "100.0"),
        ("motor_profile_acceleration", "200"),
    ):
        assert f"DeclareLaunchArgument('{name}', default_value='{default}')" in normalized
        assert re.search(
            rf"'{name}'\s*:\s*LaunchConfiguration\(\s*'{name}'\s*\)",
            launch,
        )


def test_launch_loads_the_pinky_profile_before_runtime_overrides():
    launch = (BRINGUP / "launch" / "bringup_robot.launch.py").read_text(
        encoding="utf-8"
    )
    assert "pinky_pro_adapter.yaml" in launch
    assert "rosy_params.yaml" in launch
    assert launch.index("pinky_pro_adapter.yaml") < launch.index("rosy_params.yaml")


def test_bringup_validates_ros_values_through_the_board_adapter_before_sdk():
    source = (BRINGUP / "rosy_bringup" / "bringup.py").read_text(encoding="utf-8")
    assert "from .pinky_pro_adapter import PinkyProAdapter" in source
    assert "self.pinky_pro_adapter = PinkyProAdapter.from_mapping" in source
    assert source.index("PinkyProAdapter.from_mapping") < source.index("DynamixelDriver(")


def test_node_uses_structured_controller_instead_of_inline_kinematics():
    source = (BRINGUP / "rosy_bringup" / "bringup.py").read_text(encoding="utf-8")

    assert "MotorController(" in source
    assert "DriveGeometry(" in source
    assert "DriveLimits(" in source
    assert "self.motor_controller.command_twist(" in source
    assert "profile_accel=self.motor_profile_acceleration" in source
    assert "outcome.status is CommandStatus.LIMITED" in source
    assert "v_l = linear_x" not in source
    assert "MAX_RPM =" not in source


def test_node_stops_immediately_on_rejection_and_confirms_deadman_stop():
    source = (BRINGUP / "rosy_bringup" / "bringup.py").read_text(encoding="utf-8")

    assert "stop_outcome = self.motor_controller.stop()" in source
    assert "if stop_outcome.accepted:" in source
    assert "self.command_deadman.mark_stopped()" in source
    assert "self.command_deadman.mark_stop_required()" in source
    assert "lambda: self.motor_controller.stop().accepted" in source


def test_node_uses_rollover_safe_encoder_delta():
    source = (BRINGUP / "rosy_bringup" / "bringup.py").read_text(encoding="utf-8")

    assert "wrapped_encoder_delta(encoder_l, self.last_encoder_l)" in source
    assert "wrapped_encoder_delta(encoder_r, self.last_encoder_r)" in source


def test_node_preserves_parameter_types_for_strict_driver_validation():
    source = (BRINGUP / "rosy_bringup" / "bringup.py").read_text(encoding="utf-8")

    assert "raw_motor_ids = list(self.get_parameter('motor_ids').value)" in source
    assert "self.motor_ids = list(validate_motor_ids(raw_motor_ids))" in source
    assert "self.motor_ids = [int(" not in source
    assert re.search(
        r"raw_profile_acceleration\s*=\s*self\.get_parameter\(\s*"
        r"'motor_profile_acceleration'\s*\)\.value",
        source,
    )
    assert re.search(
        r"self\.motor_profile_acceleration\s*=\s*validate_profile_acceleration\(\s*"
        r"raw_profile_acceleration\s*\)",
        source,
    )


def test_node_constructor_failure_always_terminates_motor_driver():
    source = (BRINGUP / "rosy_bringup" / "bringup.py").read_text(encoding="utf-8")
    normalized = " ".join(source.split())

    assert "try: self.get_logger().info('1. Opening serial port...')" in normalized
    assert "except Exception: self.driver.terminate() raise" in normalized


def test_bringup_publishes_a_latched_motor_readiness_lease():
    source = (BRINGUP / "rosy_bringup" / "bringup.py").read_text(encoding="utf-8")

    assert "MOTOR_READY_TOPIC = \"motor/ready\"" in source
    assert "TRANSIENT_LOCAL" in source
    assert "self.motor_ready_pub.publish(Bool(data=False))" in source
    assert "self.motor_ready_pub.publish(Bool(data=True))" in source
