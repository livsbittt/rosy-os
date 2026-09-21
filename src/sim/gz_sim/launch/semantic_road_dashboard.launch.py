#!/usr/bin/env python3
"""One-robot semantic road camera + CORE dashboard simulation."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    gz_share = get_package_share_directory("gz_sim")
    control_share = get_package_share_directory("control")
    world = os.path.join(
        control_share, "map", "map_260905_update_v2", "worlds",
        "map_260905_traffic.world")
    line_config = os.path.join(control_share, "config", "line_follow.yaml")
    core_overlay = os.path.join(
        gz_share, "config", "semantic_road_core.yaml")

    simulation = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            os.path.join(gz_share, "launch", "launch_sim.launch.xml")),
        launch_arguments={
            "world": world,
            "bridge_image": "true",
            "cam_tilt_deg": "25",
        }.items(),
    )
    simulation_camera = {
        "use_sim_time": True,
        "require_camera_controls_stable": False,
    }

    return LaunchDescription([
        simulation,
        Node(
            package="control",
            executable="line_observer_node",
            name="line_observer_node",
            output="screen",
            parameters=[line_config, simulation_camera],
        ),
        Node(
            package="control",
            executable="road_observer_node",
            name="road_observer_node",
            output="screen",
            parameters=[line_config, {
                **simulation_camera,
                "dashboard_source": "GAZEBO",
            }],
        ),
        Node(
            package="core",
            executable="core",
            name="core",
            output="screen",
            parameters=[{"use_sim_time": True}],
            additional_env={"ROSY_CONFIG": core_overlay},
        ),
        LogInfo(msg=(
            "Semantic road camera dashboard: http://127.0.0.1:8080/dashboard "
            "(viewer token: rosy-dev-viewer)")),
    ])
