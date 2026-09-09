#!/usr/bin/env python3
"""gz_multi.launch.py — rosy_gz_sim 멀티 인스턴스 런치 (P0-6, ROSY-PLN-001).

N대의 로봇을 rosy_01 .. rosy_NN namespace로 시뮬레이션한다.

- Gazebo 서버(+옵션 GUI) 1회 기동
- 로봇별: namespaced robot_state_publisher (frame_prefix), spawn(create),
  per-robot ros_gz bridge (gz 토픽이 xacro namespace로 접두되므로
  `rosy_XX/cmd_vel` ↔ `rosy_XX/cmd_vel` 매핑을 런치 시점에 생성)
- 로봇별 Nav2(gz_bringup_launch.xml, A-5 패턴) 또는 SLAM 선택

알려진 제약(런타임 검증 M0 예정):
- SLAM 모드에서 mapper_params.yaml의 scan_topic 절대경로 여부 확인 필요
  (발견 사항 A-1과 동일 계열 — 로봇별 파라미터 오버라이드로 해결)

사용 예:
  ros2 launch rosy_gz_sim gz_multi.launch.py robots:=2
  ros2 launch rosy_gz_sim gz_multi.launch.py robots:=3 mode:=slam headless:=true
  ros2 launch rosy_gz_sim gz_multi.launch.py robots:=3 mode:=nav core:=true   # 로봇별 rosy_core, 8080..8082
"""

import os
import tempfile

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
    SetEnvironmentVariable,
)
from launch_ros.actions import Node, PushRosNamespace
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

import yaml


#: 시뮬 로봇의 API 토큰. rosy_core 기본 설정(`config/rosy_default.yaml`)의 개발 토큰이다.
SIM_OPERATOR_TOKEN = "rosy-dev-operator"


def _core_config(ns: str, api_port: int) -> dict:
    """로봇별 rosy_core 오버라이드(ROSY_CONFIG). 기본 설정 위에 병합된다.

    frame_prefix 는 ROSY_NAMESPACE 환경변수가 넣으므로 여기 두지 않는다. capabilities 는
    기본 파일이 이미 swarm.follow/lead: true 라 그대로 쓴다.

    api_host 는 루프백이다. 이 코어들은 시뮬이고 유일한 클라이언트인 rosy_fleet 은 같은
    기계에서 돈다 — 0.0.0.0 이면 개발 토큰이 붙은 N 대의 API 가 로컬 네트워크에 열린다.
    """
    number = ns.rsplit("_", 1)[-1]
    return {
        "robot": {"id": ns, "name": f"Rosy {number}"},
        "network": {"api_host": "127.0.0.1", "api_port": api_port},
    }


def _robots_manifest(namespaces: list, api_port_base: int) -> list:
    """rosy_fleet CLI 가 읽는 robots.yaml 의 `robots` 목록."""
    return [
        {"robot_id": ns, "base_url": f"http://127.0.0.1:{api_port_base + i}",
         "token": SIM_OPERATOR_TOKEN}
        for i, ns in enumerate(namespaces)
    ]


# per-robot bridge 매핑 템플릿 (rosy_bridge.yaml 기반, prefix 적용)
BRIDGE_TEMPLATE = [
    # (ros_topic, gz_topic, ros_type, gz_type, direction)
    ("tf", "tf", "tf2_msgs/msg/TFMessage", "gz.msgs.Pose_V", "GZ_TO_ROS"),
    ("scan", "scan", "sensor_msgs/msg/LaserScan", "gz.msgs.LaserScan", "GZ_TO_ROS"),
    ("cmd_vel", "cmd_vel", "geometry_msgs/msg/Twist", "gz.msgs.Twist", "ROS_TO_GZ"),
    ("joint_states", "joint_states", "sensor_msgs/msg/JointState", "gz.msgs.Model", "GZ_TO_ROS"),
    ("odom", "odom", "nav_msgs/msg/Odometry", "gz.msgs.Odometry", "GZ_TO_ROS"),
    ("imu_raw", "imu_raw", "sensor_msgs/msg/Imu", "gz.msgs.IMU", "GZ_TO_ROS"),
]

CLOCK_ENTRY = {
    "ros_topic_name": "clock",
    "gz_topic_name": "clock",
    "ros_type_name": "rosgraph_msgs/msg/Clock",
    "gz_type_name": "gz.msgs.Clock",
    "direction": "GZ_TO_ROS",
}


def _bridge_config(namespace: str, with_clock: bool = False) -> list:
    entries = []
    if with_clock:
        entries.append(dict(CLOCK_ENTRY))
    for ros_topic, gz_topic, ros_type, gz_type, direction in BRIDGE_TEMPLATE:
        entries.append({
            "ros_topic_name": f"{namespace}{ros_topic}",
            "gz_topic_name": f"{namespace}{gz_topic}",
            "ros_type_name": ros_type,
            "gz_type_name": gz_type,
            "direction": direction,
        })
    return entries


def _launch_setup(context):
    robots = int(LaunchConfiguration("robots").perform(context))
    prefix = LaunchConfiguration("prefix").perform(context)
    world_name = LaunchConfiguration("world_name").perform(context)
    mode = LaunchConfiguration("mode").perform(context)
    headless = LaunchConfiguration("headless").perform(context).lower() in ("true", "1")
    spacing = float(LaunchConfiguration("spawn_spacing").perform(context))
    core = LaunchConfiguration("core").perform(context).lower() in ("true", "1")
    api_port_base = int(LaunchConfiguration("api_port_base").perform(context))

    gz_sim_share = get_package_share_directory("ros_gz_sim")
    rosy_gz_share = get_package_share_directory("rosy_gz_sim")
    rosy_nav_share = get_package_share_directory("rosy_navigation")
    rosy_desc_share = get_package_share_directory("rosy_description")

    actions = [
        SetEnvironmentVariable(
            "GZ_SIM_RESOURCE_PATH",
            os.path.join(rosy_desc_share, "..")
            + ":" + os.path.join(rosy_gz_share, "models")
            + ":" + os.path.join(os.environ.get("HOME", ""), ".gazebo", "models"),
        )
    ]

    world_path = os.path.join(rosy_gz_share, "worlds", world_name)

    # Gazebo 서버 (1회) — headless 여부로 GUI 분기
    server_args = f"-r -s -v4 {world_path}"
    actions.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(gz_sim_share, "launch", "gz_sim.launch.py")
            ),
            launch_arguments={"gz_args": server_args, "on_exit_shutdown": "true"}.items(),
        )
    )
    if not headless:
        actions.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(gz_sim_share, "launch", "gz_sim.launch.py")
                ),
                launch_arguments={"gz_args": "-g -v4"}.items(),
            )
        )

    # per-robot bridge config를 런치 시점 생성
    bridge_dir = tempfile.mkdtemp(prefix="rosy_gz_multi_")

    for i in range(1, robots + 1):
        ns = f"{prefix}_{i:02d}"
        group_actions = []

        # 1) robot_state_publisher (namespace + frame_prefix)
        group_actions.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(rosy_desc_share, "launch", "upload_robot.launch.py")
                ),
                launch_arguments={
                    "namespace": ns,
                    "is_sim": "True",
                }.items(),
            )
        )

        # 2) spawn — x축으로 spacing 간격 배치
        x = (i - 1) * spacing
        group_actions.append(
            Node(
                package="ros_gz_sim",
                executable="create",
                name=f"create_{ns}",
                output="screen",
                arguments=[
                    "-name", ns,
                    "-topic", f"{ns}/robot_description",
                    "-x", str(x), "-y", "0.0", "-z", "0.1",
                ],
                parameters=[{"use_sim_time": True}],
            )
        )

        # 3) per-robot bridge (1번 로봇이 clock 담당)
        config_path = os.path.join(bridge_dir, f"bridge_{ns}.yaml")
        with open(config_path, "w") as f:
            yaml.safe_dump(_bridge_config(f"{ns}/", with_clock=(i == 1)), f)
        group_actions.append(
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                name=f"bridge_{ns}",
                output="screen",
                arguments=["--ros-args", "-p", f"config_file:={config_path}"],
            )
        )

        # 4) Nav2 / SLAM (mode)
        if mode == "nav":
            group_actions.append(
                IncludeLaunchDescription(
                    AnyLaunchDescriptionSource(
                        os.path.join(rosy_nav_share, "launch", "gz_bringup_launch.xml")
                    ),
                    launch_arguments={"namespace": ns}.items(),
                )
            )
        elif mode == "slam":
            group_actions.append(
                GroupAction([
                    PushRosNamespace(ns),
                    IncludeLaunchDescription(
                        AnyLaunchDescriptionSource(
                            os.path.join(rosy_nav_share, "launch", "gz_map_building.launch.xml")
                        ),
                        launch_arguments={"use_sim_time": "True"}.items(),
                    ),
                ])
            )

        # 5) rosy_core (core:=true) — 로봇마다 포트·HOME·설정을 가른다.
        #    HOME 을 가르는 이유: waypoints.json 과 audit.jsonl 이 Path.home()/.rosy 에
        #    고정돼 있어, 같은 HOME 이면 N대가 한 파일을 쓴다.
        #    HOME 을 가르면 ROS 로그도 따라간다: 각 코어의 ~/.ros/log 는 그 임시 HOME
        #    아래에 생기므로(ROS_LOG_DIR 기본값이 $HOME/.ros/log), 로그는 로봇마다
        #    나뉘고 런치가 끝나도 사용자의 ~/.ros 를 어지럽히지 않는다.
        if core:
            core_home = os.path.join(bridge_dir, f"home_{ns}")
            os.makedirs(core_home, exist_ok=True)
            core_cfg = os.path.join(bridge_dir, f"rosy_{ns}.yaml")
            with open(core_cfg, "w") as f:
                yaml.safe_dump(_core_config(ns, api_port_base + i - 1), f)
            group_actions.append(
                Node(
                    package="rosy_core",
                    executable="rosy_core",
                    name="rosy_core",
                    namespace=ns,
                    output="screen",
                    parameters=[{"use_sim_time": True}],
                    additional_env={
                        "ROSY_NAMESPACE": ns,
                        "ROSY_CONFIG": core_cfg,
                        "HOME": core_home,
                    },
                )
            )

        actions.extend(group_actions)

    if core:
        namespaces = [f"{prefix}_{i:02d}" for i in range(1, robots + 1)]
        manifest_path = os.path.join(bridge_dir, "robots.yaml")
        with open(manifest_path, "w") as f:
            yaml.safe_dump({"robots": _robots_manifest(namespaces, api_port_base)}, f, sort_keys=False)
        try:
            # 이 파일은 운영자 토큰을 담는다. mkdtemp 은 디렉터리를 0700 으로 만들지만
            # 파일 자체는 umask 를 따르므로, rosy_fleet 이 경고하는 것과 같은 조건을
            # 우리가 먼저 만들지 않는다. Windows 는 이 비트를 무시한다.
            os.chmod(manifest_path, 0o600)
        except OSError as exc:
            actions.append(LogInfo(msg=f"could not restrict robots.yaml permissions: {exc}"))
        actions.append(LogInfo(msg=f"rosy_fleet robots.yaml: {manifest_path}"))

    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("robots", default_value="2",
                              description="로봇 대수"),
        DeclareLaunchArgument("prefix", default_value="rosy",
                              description="namespace 접두 (rosy → rosy_01, rosy_02, ...)"),
        DeclareLaunchArgument("world_name", default_value="rosy_factory.world"),
        DeclareLaunchArgument("mode", default_value="none",
                              choices=["none", "nav", "slam"],
                              description="로봇별 상위 스택 (none=spawn만)"),
        DeclareLaunchArgument("headless", default_value="false"),
        DeclareLaunchArgument("spawn_spacing", default_value="1.5",
                              description="로봇 간 x축 배치 간격 (m)"),
        DeclareLaunchArgument("core", default_value="false",
                              description="로봇별 rosy_core 기동 (포트 api_port_base + i - 1)"),
        DeclareLaunchArgument("api_port_base", default_value="8080",
                              description="첫 로봇의 rosy_core API 포트"),
        OpaqueFunction(function=_launch_setup),
    ])
