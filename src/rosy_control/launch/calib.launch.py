import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    robot = os.path.join(
        get_package_share_directory('rosy_control'), 'config', 'robot.yaml'
    )
    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('calibration_path', default_value='',
                              description='One calibration file in the active writable data generation'),
        Node(
            package='rosy_control',
            executable='calib_node',
            output='screen',
            namespace=LaunchConfiguration('namespace'),
            parameters=[robot, {
                'save_path': LaunchConfiguration('calibration_path'),
                'sign_path': LaunchConfiguration('calibration_path'),
            }],
        ),
    ])
