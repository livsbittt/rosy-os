"""Sensing-only D-143 line observer; CORE retains all command authority."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('control')
    config = os.path.join(share, 'config')
    namespace = LaunchConfiguration('namespace')
    start_camera = LaunchConfiguration('start_camera')
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('start_camera', default_value='true', choices=['true', 'false']),
        Node(
            package='control', executable='camera_detect_node', namespace=namespace,
            output='screen', respawn=True, respawn_delay=1.0,
            condition=IfCondition(start_camera),
            parameters=[os.path.join(config, 'camera.yaml')],
        ),
        Node(
            package='control', executable='line_observer_node', namespace=namespace,
            output='screen', respawn=True, respawn_delay=1.0,
            parameters=[os.path.join(config, 'line_follow.yaml')],
        ),
    ])
