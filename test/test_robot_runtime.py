"""Static contract tests for the Raspberry Pi robot runtime."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "robot"


def _compose() -> dict:
    return yaml.safe_load((DEPLOY / "compose.yaml").read_text(encoding="utf-8"))


def test_runtime_separates_core_from_hardware_devices():
    services = _compose()["services"]

    assert set(services) == {"rosy-core", "rosy-motor", "rosy-io"}
    assert "devices" not in services["rosy-core"]
    assert services["rosy-core"].get("privileged", False) is False
    assert services["rosy-motor"].get("privileged", False) is False
    assert services["rosy-io"].get("privileged", False) is False
    assert services["rosy-motor"]["devices"] == [
        "${ROSY_MOTOR_DEVICE:-/dev/ttyAMA4}:/dev/rosy-motor",
    ]
    assert services["rosy-io"]["devices"] == [
        "${ROSY_MOTOR_DEVICE:-/dev/ttyAMA4}:/dev/rosy-motor",
        "${ROSY_LIDAR_DEVICE:-/dev/ttyAMA0}:/dev/ttyAMA0",
    ]


def test_runtime_uses_local_ros_network_and_bounded_logs():
    services = _compose()["services"]

    for service in services.values():
        assert service["network_mode"] == "host"
        assert service["restart"] == "unless-stopped"
        assert service["logging"]["driver"] == "local"
        assert service["logging"]["options"] == {
            "max-size": "10m",
            "max-file": "3",
        }
        assert service["environment"]["ROS_DOMAIN_ID"] == "${ROS_DOMAIN_ID:-42}"


def test_runtime_uses_one_namespace_and_a_real_core_health_endpoint():
    services = _compose()["services"]
    namespace_arg = "__ns:=/${ROSY_NAMESPACE:-rosy_01}"

    assert namespace_arg in services["rosy-core"]["command"]
    assert "namespace:=${ROSY_NAMESPACE:-rosy_01}" in services["rosy-motor"]["command"]
    assert "namespace:=${ROSY_NAMESPACE:-rosy_01}" in services["rosy-io"]["command"]
    assert "/api/v1" in " ".join(services["rosy-core"]["healthcheck"]["test"])


def test_runtime_builds_distinct_targets_from_shared_dockerfile():
    services = _compose()["services"]
    dockerfile = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")

    assert services["rosy-core"]["build"]["target"] == "core"
    assert services["rosy-motor"]["build"]["target"] == "io"
    assert services["rosy-io"]["build"]["target"] == "io"
    assert "AS core" in dockerfile
    assert "AS io" in dockerfile
    assert "ros:jazzy-ros-base" in dockerfile
    assert "ros-jazzy-rmw-cyclonedds-cpp" in dockerfile
    assert "ros-jazzy-joint-state-publisher" in dockerfile
    assert "SLLIDAR_COMMIT=34300099fadfc772965962dec837bf436706188f" in dockerfile
    assert "git checkout --detach ${SLLIDAR_COMMIT}" in dockerfile
    assert "COPY --from=core-build /opt/rosy_ws/install" in dockerfile
    assert "COPY --from=io-build /opt/rosy_ws/install" in dockerfile
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "src/rosy_description/meshes/**" in dockerignore


def test_initial_io_slice_disables_unavailable_adc_battery_driver():
    compose_command = _compose()["services"]["rosy-io"]["command"]
    launch = (
        ROOT / "src" / "rosy_bringup" / "launch" / "bringup_robot.launch.py"
    ).read_text(encoding="utf-8")

    assert "enable_battery:=false" in compose_command
    assert "DeclareLaunchArgument('enable_battery', default_value='false'" in launch
    assert "condition=IfCondition(enable_battery)" in launch
    assert "on_exit=Shutdown(" in launch


def test_motor_only_profile_excludes_lidar_and_passes_uart_parameters():
    services = _compose()["services"]
    motor = services["rosy-motor"]
    command = motor["command"]

    assert motor["profiles"] == ["motor"]
    assert "enable_lidar:=false" in command
    assert "motor_device:=/dev/rosy-motor" in command
    assert "motor_baudrate:=${ROSY_MOTOR_BAUDRATE:-1000000}" in command
    assert "motor_ids:=${ROSY_MOTOR_IDS:-[1,2]}" in command
    assert "max_linear_mps:=${ROSY_MAX_LINEAR_MPS:-0.25}" in command
    assert "max_angular_rps:=${ROSY_MAX_ANGULAR_RPS:-2.5}" in command
    assert "max_wheel_rpm:=${ROSY_MAX_WHEEL_RPM:-100.0}" in command
    assert (
        "motor_profile_acceleration:=${ROSY_MOTOR_PROFILE_ACCELERATION:-200}"
        in command
    )
    assert all("ttyAMA0" not in device for device in motor["devices"])


def test_hardware_profile_passes_the_same_motor_safety_limits():
    command = _compose()["services"]["rosy-io"]["command"]

    assert "max_linear_mps:=${ROSY_MAX_LINEAR_MPS:-0.25}" in command
    assert "max_angular_rps:=${ROSY_MAX_ANGULAR_RPS:-2.5}" in command
    assert "max_wheel_rpm:=${ROSY_MAX_WHEEL_RPM:-100.0}" in command
    assert (
        "motor_profile_acceleration:=${ROSY_MOTOR_PROFILE_ACCELERATION:-200}"
        in command
    )


def test_example_environment_exposes_motor_limits_as_data_only_values():
    environment = (DEPLOY / ".env.example").read_text(encoding="utf-8")

    assert "ROSY_MAX_LINEAR_MPS=0.25" in environment
    assert "ROSY_MAX_ANGULAR_RPS=2.5" in environment
    assert "ROSY_MAX_WHEEL_RPM=100.0" in environment
    assert "ROSY_MOTOR_PROFILE_ACCELERATION=200" in environment


def test_io_health_requires_the_motor_node_to_be_discoverable():
    io = _compose()["services"]["rosy-io"]

    assert "healthcheck" in io
    assert "/${ROSY_NAMESPACE:-rosy_01}/rosy_bringup" in " ".join(
        io["healthcheck"]["test"]
    )


def test_core_data_is_a_host_owned_bind_and_capabilities_match_the_slice():
    compose = _compose()
    core = compose["services"]["rosy-core"]
    capabilities = yaml.safe_load(
        (DEPLOY / "config" / "capabilities.pi5-lite.yaml").read_text(encoding="utf-8")
    )
    profile = yaml.safe_load(
        (DEPLOY / "config" / "profile.pi5-lite.yaml").read_text(encoding="utf-8")
    )

    assert "${ROSY_DATA_PATH:-/var/lib/rosy}:/var/lib/rosy" in core["volumes"]
    assert "volumes" not in compose
    assert capabilities["sensors"] == ["lidar", "encoder"]
    assert capabilities["navigation"]["goal_navigation"] is False
    assert capabilities["navigation"]["return_home"] is False
    assert capabilities["slam"] is False
    assert profile["profile"]["sensors"] == [
        {"lidar": "rplidar_c1"},
        {"encoder": "dynamixel"},
    ]


def test_core_reads_only_bounded_host_telemetry_paths():
    core = _compose()["services"]["rosy-core"]
    mounts = set(core["volumes"])

    assert core["environment"]["ROSY_HOST_ROOT"] == "${ROSY_HOST_ROOT:-/host}"
    assert {
        "/proc/uptime:/host/proc/uptime:ro",
        "/proc/loadavg:/host/proc/loadavg:ro",
        "/proc/stat:/host/proc/stat:ro",
        "/proc/net/dev:/host/proc/net/dev:ro",
        "/proc/meminfo:/host/proc/meminfo:ro",
        "/sys/class/thermal:/host/sys/class/thermal:ro",
        "/sys/devices/virtual/thermal:/host/sys/devices/virtual/thermal:ro",
        "/etc/os-release:/host/etc/os-release:ro",
        "/etc/hostname:/host/etc/hostname:ro",
    } <= mounts
    assert "/:/host:ro" not in mounts
    assert "/var/run/docker.sock:/var/run/docker.sock" not in mounts


def test_core_image_prepares_dashboard_and_host_mount_directories():
    dockerfile = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    setup = (ROOT / "src" / "rosy_core" / "setup.py").read_text(encoding="utf-8")

    assert (
        "mkdir -p /host/proc/net /host/etc /host/sys/class/thermal "
        "/host/sys/devices/virtual/thermal"
    ) in dockerfile
    assert "web/*.html" in setup
    assert "web/*.css" in setup
    assert "web/*.js" in setup


def test_systemd_unit_delegates_to_runtime_mode_wrapper():
    unit = (DEPLOY / "rosy-runtime.service").read_text(encoding="utf-8")

    assert "Requires=docker.service" in unit
    assert "EnvironmentFile=-/opt/rosy/deploy/robot/.env" in unit
    assert "runtime-mode.sh up" in unit
    assert "runtime-mode.sh down" in unit
    assert "docker compose" not in unit


def test_container_entrypoint_is_forced_to_unix_line_endings():
    entrypoint = (DEPLOY / "entrypoint.sh").read_bytes()
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert b"\r\n" not in entrypoint
    assert "*.sh text eol=lf" in attributes
