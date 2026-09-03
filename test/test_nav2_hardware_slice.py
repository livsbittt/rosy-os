"""Nav2 hardware-slice contracts (D-2, D-4, composition, packaging)."""

import sys
from pathlib import Path

import yaml

from robot_contracts import DEPLOY, NAV_LAUNCH, NAV_PARAMS, ROOT, board_caps, board_profile, compose

_PKG = str(ROOT / "src" / "rosy_navigation")
if _PKG not in sys.path:
    sys.path.append(_PKG)


def test_hardware_mode_advertises_lidar_and_goal_navigation():
    caps = board_caps("hardware")
    profile = board_profile("hardware")
    io = compose()["services"]["rosy-io"]
    command = io["command"]

    assert caps["teleop"] is True
    assert caps["sensors"] == ["lidar", "encoder"]
    assert caps["navigation"]["goal_navigation"] is True
    assert caps["navigation"]["return_home"] is True
    assert caps["slam"] is False
    assert profile["profile"]["sensors"] == [
        {"lidar": "rplidar_c1"},
        {"encoder": "dynamixel"},
    ]
    assert "rosy_navigation" in command
    assert "hardware.launch.py" in command
    assert "enable_lidar:=true" in command
    assert "enable_battery:=false" in command
    assert any("ttyAMA0" in device for device in io["devices"])
    assert io["healthcheck"]["start_period"] == "60s"
    assert io["healthcheck"]["timeout"] == "10s"
    health = " ".join(io["healthcheck"]["test"])
    assert "rosy_bringup" in health
    assert "lifecycle_manager_navigation" in health
    assert health.count("ros2 node list") == 1


def test_motor_profile_does_not_launch_nav2():
    command = compose()["services"]["rosy-motor"]["command"]

    assert "rosy_bringup" in command
    assert "bringup_robot.launch.py" in command
    assert "rosy_navigation" not in command
    assert "hardware.launch.py" not in command


def test_io_image_packages_nav2_without_slam_or_aux_drivers():
    dockerfile = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "COPY src/rosy_navigation" in dockerfile
    assert "rosy_navigation" in dockerfile
    assert "ros-jazzy-navigation2" in dockerfile
    assert "ros-jazzy-nav2-bringup" in dockerfile
    assert "python3-yaml" in dockerfile
    assert "ros-jazzy-slam-toolbox" not in dockerfile
    assert "rosy_imu_bno055" not in dockerfile
    assert "rosy_sensor_adc" not in dockerfile
    assert "rosy_led" not in dockerfile
    assert "rosy_lamp_control" not in dockerfile
    assert "rosy_emotion" not in dockerfile
    assert "!src/rosy_navigation/" in dockerignore


def test_hardware_launch_composes_bringup_and_imports_nav_policy():
    launch = (NAV_LAUNCH / "hardware.launch.py").read_text(encoding="utf-8")

    assert "bringup_robot.launch.py" in launch
    assert "bringup_launch.xml" in launch
    assert "my_map.yaml" in launch
    assert "from rosy_navigation.params_rewrite import write_prefixed_nav2_params" in launch
    assert "from rosy_navigation.site_map import resolve_occupancy_map" in launch
    assert "sys.path.insert" not in launch
    assert "map_building" not in launch
    assert "slam_toolbox" not in launch
    assert "nav2_web_server" not in launch


def test_hardware_io_mounts_a_host_site_map_directory():
    io = compose()["services"]["rosy-io"]
    motor = compose()["services"]["rosy-motor"]

    assert io["environment"]["ROSY_MAP"] == "${ROSY_MAP:-/var/lib/rosy/maps/site.yaml}"
    assert "${ROSY_DATA_PATH:-/var/lib/rosy}/maps:/var/lib/rosy/maps:ro" in io["volumes"]
    assert "volumes" not in motor
    installer = (DEPLOY / "install-pi.sh").read_text(encoding="utf-8")
    assert '"$ROSY_DATA/maps"' in installer


def test_resolve_occupancy_map_uses_site_yaml_only_when_the_image_exists(tmp_path):
    from rosy_navigation.site_map import resolve_occupancy_map

    fallback = tmp_path / "demo.yaml"
    fallback.write_text("image: demo.pgm\n", encoding="utf-8")
    (tmp_path / "demo.pgm").write_bytes(b"P5\n")

    missing = tmp_path / "maps" / "site.yaml"
    assert resolve_occupancy_map(missing, fallback) == str(fallback)

    site = tmp_path / "maps" / "site.yaml"
    site.parent.mkdir()
    site.write_text("image: site.pgm\n", encoding="utf-8")
    assert resolve_occupancy_map(site, fallback) == str(fallback)

    (tmp_path / "maps" / "site.pgm").write_bytes(b"P5\n")
    assert resolve_occupancy_map(site, fallback) == str(site)


def test_nav2_frame_prefix_module_prefixes_odom_not_map():
    from rosy_navigation.frame_prefix import apply_nav2_frame_prefix

    raw = yaml.safe_load(NAV_PARAMS.read_text(encoding="utf-8"))
    prefixed = apply_nav2_frame_prefix(raw, "rosy_01")
    amcl = prefixed["amcl"]["ros__parameters"]
    assert amcl["odom_frame_id"] == "rosy_01/odom"
    assert amcl["base_frame_id"] == "rosy_01/base_footprint"
    assert amcl["global_frame_id"] == "map"
    assert (
        prefixed["bt_navigator"]["ros__parameters"]["robot_base_frame"]
        == "rosy_01/base_link"
    )
    local = prefixed["local_costmap"]["local_costmap"]["ros__parameters"]
    assert local["global_frame"] == "rosy_01/odom"
    assert local["robot_base_frame"] == "rosy_01/base_footprint"
    globmap = prefixed["global_costmap"]["global_costmap"]["ros__parameters"]
    assert globmap["global_frame"] == "map"
    assert globmap["robot_base_frame"] == "rosy_01/base_footprint"
    assert apply_nav2_frame_prefix(raw, "")["amcl"]["ros__parameters"][
        "odom_frame_id"
    ] == "odom"


def test_write_prefixed_nav2_params_writes_a_unique_file(tmp_path):
    from rosy_navigation.params_rewrite import write_prefixed_nav2_params

    out = Path(write_prefixed_nav2_params(NAV_PARAMS, "rosy_01", directory=tmp_path))
    assert out.parent == tmp_path
    assert out.name.startswith("rosy_nav2_params_")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["amcl"]["ros__parameters"]["odom_frame_id"] == "rosy_01/odom"


def test_nav2_composition_loads_into_the_namespaced_container():
    bringup = (NAV_LAUNCH / "bringup_launch.xml").read_text(encoding="utf-8")
    loc = (NAV_LAUNCH / "localization_launch.xml").read_text(encoding="utf-8")
    nav = (NAV_LAUNCH / "navigation_launch.xml").read_text(encoding="utf-8")

    assert "name='$(var container_name)'" in bringup
    assert 'value="$(var namespace)/$(var container_name)"' in bringup
    assert "name='$(var namespace)/$(var container_name)'" not in bringup
    nav_nodes = bringup.split("lifecycle_nodes_nav")[1].split("/>")[0]
    assert "smoother_server" in nav_nodes
    assert 'target="$(var container_name)"' in loc
    assert 'target="$(var container_name)"' in nav


def test_gz_bringup_reuses_robot_nav2_launch():
    gz = (NAV_LAUNCH / "gz_bringup_launch.xml").read_text(encoding="utf-8")

    assert "bringup_launch.xml" in gz
    assert "use_sim_time" in gz
    assert "component_container_isolated" not in gz
    assert "lifecycle_nodes_nav" not in gz


def test_amcl_initial_pose_is_a_pose_dict():
    params = yaml.safe_load(NAV_PARAMS.read_text(encoding="utf-8"))
    pose = params["amcl"]["ros__parameters"]["initial_pose"]
    assert isinstance(pose, dict)
    assert {"x", "y", "yaw"} <= set(pose)


def test_nav2_smoother_output_is_nav_cmd_vel_not_cmd_vel():
    text = (NAV_LAUNCH / "navigation_launch.xml").read_text(encoding="utf-8")

    assert text.count('from="cmd_vel_smoothed" to="nav_cmd_vel"') == 2
    assert 'from="cmd_vel_smoothed" to="cmd_vel"' not in text


def test_hardware_nav2_shares_the_global_tf_bus():
    for name in (
        "bringup_launch.xml",
        "gz_bringup_launch.xml",
        "localization_launch.xml",
        "navigation_launch.xml",
    ):
        text = (NAV_LAUNCH / name).read_text(encoding="utf-8")
        assert '<remap from="/tf" to="tf"/>' not in text, name
        assert '<remap from="/tf_static" to="tf_static"/>' not in text, name
