"""ROS-free Gazebo sim package surface (D-73). Launch tests stay skippable."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_and_multi_robot_launch_exist():
    package = (ROOT / "package.xml").read_text(encoding="utf-8")
    assert "<name>gz_sim</name>" in package
    assert "fleet" in package
    launch = (ROOT / "launch" / "gz_multi.launch.py").read_text(encoding="utf-8")
    assert "gz_multi" in launch or "core" in launch
    assert "core" in launch
    assert "spawn_x" in launch
    assert "inflation_radius" in launch
    assert "slam_nav" in launch
    assert launch.count('"use_composition": "False"') >= 2
    assert (ROOT / "config" / "worlds.yaml").is_file()
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "config" in cmake


def test_single_robot_launch_declares_description_runtime_dependency():
    """The installed launch must bring every package it resolves at runtime."""
    package = (ROOT / "package.xml").read_text(encoding="utf-8")
    launch = (ROOT / "launch" / "launch_sim.launch.xml").read_text(
        encoding="utf-8")

    assert "$(find-pkg-share description)" in launch
    assert "<exec_depend>description</exec_depend>" in package


def test_single_robot_gazebo_gui_is_optional():
    """Headless sensor validation must not require a Gazebo GUI process."""
    launch = (ROOT / "launch" / "launch_sim.launch.xml").read_text(
        encoding="utf-8")

    assert '<arg name="gui" default="true"/>' in launch
    assert 'if="$(var gui)"' in launch


def test_single_robot_camera_render_profile_reaches_the_description():
    launch = (ROOT / "launch" / "launch_sim.launch.xml").read_text(
        encoding="utf-8")

    for name, default in (
        ("camera_width", "1280"),
        ("camera_height", "720"),
        ("camera_update_rate", "10"),
    ):
        assert f'<arg name="{name}" default="{default}"/>' in launch
        assert f"<arg name='{name}' value='$(var {name})'/>" in launch


def test_semantic_road_uses_a_bounded_camera_profile_and_gazebo_range():
    launch = (ROOT / "launch" / "semantic_road_dashboard.launch.py").read_text(
        encoding="utf-8")

    assert 'DeclareLaunchArgument("camera_width", default_value="320")' in launch
    assert 'DeclareLaunchArgument("camera_height", default_value="180")' in launch
    assert 'DeclareLaunchArgument("camera_update_rate", default_value="5")' in launch
    assert '"camera_width": LaunchConfiguration("camera_width")' in launch
    assert '"camera_height": LaunchConfiguration("camera_height")' in launch
    assert '"camera_update_rate": LaunchConfiguration(' in launch
    assert '"camera_ground_mode": "gazebo_pinhole"' in launch
    assert '"gazebo_camera_height_m": 0.060194' in launch
    assert '"gazebo_camera_pitch_rad": math.radians(25.0)' in launch
    assert '"gazebo_camera_hfov_rad": 1.1519' in launch


def test_gz_multi_uses_ros_gz_bridge_not_domain_bridge():
    """D-114: 시뮬은 네임스페이스 + ros_gz_bridge. domain_bridge / ROS_DOMAIN_ID 없음."""
    launch = (ROOT / "launch" / "gz_multi.launch.py").read_text(encoding="utf-8")
    assert "ros_gz_bridge" in launch
    assert "parameter_bridge" in launch
    assert "domain_bridge" not in launch
    assert "ROS_DOMAIN_ID" not in launch
    assert "rosy_env.sh" not in launch


def test_gz_multi_seeds_map_initialpose_at_spawn():
    """D-115: nav 모드에서 spawn 좌표를 {ns}/initialpose 로 심는다."""
    launch = (ROOT / "launch" / "gz_multi.launch.py").read_text(encoding="utf-8")
    assert "seed_initialpose" in launch
    assert "spawn_xy" in launch
    script = ROOT / "scripts" / "seed_initialpose.py"
    assert script.is_file()
    raw = script.read_bytes()
    assert raw.startswith(b"#!/usr/bin/env python3\n")
    assert b"\r\n" not in raw
    text = script.read_text(encoding="utf-8")
    assert "initialpose" in text
    assert "get_subscription_count" in text
    assert "while rclpy.ok() and not node.done" in text
    assert "import core" not in text
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "scripts/seed_initialpose.py" in cmake


def test_non_composed_nav2_does_not_apply_namespace_twice():
    """The parent owns the namespace; child launch groups must receive an empty one."""
    bringup = (
        ROOT.parents[1]
        / "navigation"
        / "navigation"
        / "launch"
        / "bringup_launch.xml"
    ).read_text(encoding="utf-8")
    assert bringup.count('<arg name="namespace" value=""/>') == 2


def test_world_to_map_is_installed_and_bench_worlds_exist():
    """HOST에서 도는 정답 맵 생성기가 패키지 표면이다. launch skip이 SOURCE가 아니다."""
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "scripts/world_to_map.py" in cmake
    assert (ROOT / "scripts" / "world_to_map.py").is_file()
    assert (ROOT / "worlds" / "rosy_swarm_bench.world").is_file()
    assert (ROOT / "worlds" / "rosy_maze.world").is_file()
