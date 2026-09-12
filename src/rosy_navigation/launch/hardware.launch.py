"""hardware.launch.py — Pinky hardware slice: motors + LiDAR + Nav2.

Composes rosy_bringup and Nav2 bringup. D-4 param rewrite lives in
rosy_navigation.params_rewrite. Does not start SLAM; Rosy OS FastAPI is owned
by the separate ``rosy_core`` service.
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.launch_description_sources import (
    AnyLaunchDescriptionSource,
    PythonLaunchDescriptionSource,
)
from launch.substitutions import LaunchConfiguration

from rosy_navigation.params_rewrite import write_prefixed_nav2_params
from rosy_navigation.site_map import resolve_occupancy_map


def _include_nav2(context, *args, **kwargs):
    nav_share = get_package_share_directory("rosy_navigation")
    namespace = LaunchConfiguration("namespace").perform(context)
    source = LaunchConfiguration("params_file").perform(context)
    fallback_map = os.path.join(nav_share, "map", "my_map.yaml")
    map_yaml = resolve_occupancy_map(
        LaunchConfiguration("map").perform(context),
        fallback_map,
    )
    return [
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                os.path.join(nav_share, "launch", "bringup_launch.xml")
            ),
            launch_arguments={
                "namespace": namespace,
                "use_sim_time": LaunchConfiguration("use_sim_time").perform(context),
                "map": map_yaml,
                "params_file": write_prefixed_nav2_params(source, namespace),
                "use_composition": "True",
            }.items(),
        )
    ]


def generate_launch_description():
    bringup_share = get_package_share_directory("rosy_bringup")
    nav_share = get_package_share_directory("rosy_navigation")
    default_params = os.path.join(nav_share, "params", "nav2_params.yaml")

    namespace = LaunchConfiguration("namespace")
    use_sim_time = LaunchConfiguration("use_sim_time")

    robot_args = {
        "namespace": namespace,
        "use_sim_time": use_sim_time,
        "enable_battery": LaunchConfiguration("enable_battery"),
        "enable_lidar": LaunchConfiguration("enable_lidar"),
        "cmd_vel_timeout_s": LaunchConfiguration("cmd_vel_timeout_s"),
        "motor_device": LaunchConfiguration("motor_device"),
        "motor_baudrate": LaunchConfiguration("motor_baudrate"),
        "motor_ids": LaunchConfiguration("motor_ids"),
        "max_linear_mps": LaunchConfiguration("max_linear_mps"),
        "max_angular_rps": LaunchConfiguration("max_angular_rps"),
        "max_wheel_rpm": LaunchConfiguration("max_wheel_rpm"),
        "motor_profile_acceleration": LaunchConfiguration(
            "motor_profile_acceleration"
        ),
    }

    return LaunchDescription([
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("enable_battery", default_value="false"),
        DeclareLaunchArgument("enable_lidar", default_value="true"),
        DeclareLaunchArgument("cmd_vel_timeout_s", default_value="0.5"),
        DeclareLaunchArgument("motor_device", default_value="/dev/ttyAMA4"),
        DeclareLaunchArgument("motor_baudrate", default_value="1000000"),
        DeclareLaunchArgument("motor_ids", default_value="[1,2]"),
        DeclareLaunchArgument("max_linear_mps", default_value="0.25"),
        DeclareLaunchArgument("max_angular_rps", default_value="2.5"),
        DeclareLaunchArgument("max_wheel_rpm", default_value="100.0"),
        DeclareLaunchArgument("motor_profile_acceleration", default_value="200"),
        DeclareLaunchArgument(
            "map",
            default_value=os.environ.get("ROSY_MAP", "/var/lib/rosy/maps/site.yaml"),
        ),
        DeclareLaunchArgument("params_file", default_value=default_params),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(bringup_share, "launch", "bringup_robot.launch.py")
            ),
            launch_arguments=robot_args.items(),
        ),
        OpaqueFunction(function=_include_nav2),
    ])
