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
from launch_ros.actions import Node, PushRosNamespace, SetRemap
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


def _slam_config(ns: str, rosy_nav_share: str) -> dict:
    """로봇별 slam_toolbox 파라미터.

    저장소의 mapper_params.yaml 은 단일 로봇용이다(`scan_topic: /scan`, 접두 없는
    프레임). 네임스페이스로 N대를 띄우면 스캔은 `/rosy_XX/scan` 으로 오고 TF 는
    robot_state_publisher 의 frame_prefix 때문에 `rosy_XX/` 가 붙으므로, 그대로 쓰면
    slam_toolbox 는 스캔도 TF 도 찾지 못한다. 기본값을 읽어 로봇별로만 덮어쓴다.

    `/**` 로 감싸는 이유: 노드가 `/rosy_XX/slam_toolbox` 라 파일의 최상위 키가
    `slam_toolbox` 이면 이름이 맞지 않아 파라미터가 하나도 적용되지 않는다.
    """
    defaults_path = os.path.join(rosy_nav_share, "params", "mapper_params.yaml")
    with open(defaults_path, encoding="utf-8") as f:
        defaults = yaml.safe_load(f)
    params = dict(defaults["slam_toolbox"]["ros__parameters"])
    params.update({
        "scan_topic": f"/{ns}/scan",
        "odom_frame": f"{ns}/odom",
        "base_frame": f"{ns}/base_footprint",
        # map 은 공유 루트 프레임으로 둔다(rosy_core 가 `map` 기준으로 목표를 낸다).
        # 로봇별 맵 내용은 SetRemap 으로 나눈 `/rosy_XX/map` 토픽이 구분한다.
        "map_frame": "map",
        "use_sim_time": True,
        # 기본값(0.5 m / 0.5 rad)은 실기 기준이다. 시뮬 월드는 4x3 m 남짓이고 pinky 는
        # 12 cm 라, 0.5 rad 마다 키프레임을 잡으면 제자리 회전 중 스캔 사이 각도차가
        # coarse_search_angle_offset(0.349 rad)를 넘겨 매칭이 어긋나고 맵에 회전 중복상이
        # 남는다. 로봇·월드 크기에 맞춰 키프레임을 촘촘히 잡는다.
        "minimum_travel_distance": 0.2,
        "minimum_travel_heading": 0.2,
        "scan_buffer_size": 20,
        "transform_timeout": 0.5,
    })
    return {"/**": {"ros__parameters": params}}


def _nav_config(ns: str, rosy_nav_share: str,
                inflation_radius: float = 0.0) -> dict:
    """로봇별 nav2 파라미터.

    프레임 접두는 rosy_navigation 의 `apply_nav2_frame_prefix` 를 그대로 쓴다 — `map` 은
    전역으로 남기고 odom/base_* 만 `rosy_XX/` 로 바꾸는 규칙이 거기 한 곳에 있다.

    여기서 두 가지를 더 얹는다:
    - use_sim_time: 저장소 파일은 실기 기준이라 collision_monitor 등이 false 로 못박혀 있다.
    - 네임스페이스 루트 키: 노드의 완전한 이름은 `/rosy_XX/controller_server` 라, 파일
      최상위가 `controller_server` 면 매칭되지 않아 파라미터가 통째로 무시되고 nav2 가
      기본값으로 뜬다("No critics defined for FollowPath" 가 그 증상이다).
      nav2_bringup 의 RewrittenYaml(root_key=namespace) 과 같은 형태다.
    """
    from rosy_navigation.frame_prefix import apply_nav2_frame_prefix

    defaults_path = os.path.join(rosy_nav_share, "params", "nav2_params.yaml")
    with open(defaults_path, encoding="utf-8") as f:
        defaults = yaml.safe_load(f)

    def force_sim_time(value):
        if isinstance(value, dict):
            return {k: (True if k == "use_sim_time" else force_sim_time(v))
                    for k, v in value.items()}
        if isinstance(value, list):
            return [force_sim_time(v) for v in value]
        return value

    params = force_sim_time(apply_nav2_frame_prefix(defaults, ns))
    if inflation_radius:
        # 통로 폭은 월드마다 다르고, 팽창 반경은 그 폭에 맞춰야 한다. 좁은 통로에서는
        # 반폭보다 크게 잡아야 경로가 중앙을 따라가고, 잡동사니가 빽빽한 방에서는
        # 작게 잡아야 출발조차 막히지 않는다. 한 값으로 둘 다 만족시킬 수 없다.
        for costmap in ("local_costmap", "global_costmap"):
            layer = params[costmap][costmap]["ros__parameters"]["inflation_layer"]
            layer["inflation_radius"] = inflation_radius
    return {ns: params}


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

#: TF 는 로봇마다 나누지 않는다. DiffDrive 플러그인이 `<tf_topic>/tf</tf_topic>` 로 gz 의
#: 전역 `/tf` 에 쓰고, robot_state_publisher 도 (네임스페이스와 무관하게) ROS 의 전역
#: `/tf` 에 쓴다. 프레임 이름은 frame_prefix 로 이미 `rosy_XX/` 가 붙어 충돌하지 않는다.
#: 로봇별로 `rosy_XX/tf` 를 브리지하면 구독자만 생기고 발행자가 없어 odom→base_footprint
#: 가 ROS 로 넘어오지 않는다(맵이 안 생기던 원인).
TF_ENTRY = {
    "ros_topic_name": "/tf",
    "gz_topic_name": "/tf",
    "ros_type_name": "tf2_msgs/msg/TFMessage",
    "gz_type_name": "gz.msgs.Pose_V",
    "direction": "GZ_TO_ROS",
}


def _bridge_config(namespace: str, with_clock: bool = False) -> list:
    entries = []
    if with_clock:
        entries.append(dict(CLOCK_ENTRY))
        entries.append(dict(TF_ENTRY))
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
    map_yaml = LaunchConfiguration("map").perform(context)
    spawn_x = float(LaunchConfiguration("spawn_x").perform(context))
    spawn_y = float(LaunchConfiguration("spawn_y").perform(context))
    inflation_radius = float(LaunchConfiguration("inflation_radius").perform(context))

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

        # 2) spawn — spawn_x/spawn_y 에서 x축으로 spacing 간격 배치
        x = spawn_x + (i - 1) * spacing
        group_actions.append(
            Node(
                package="ros_gz_sim",
                executable="create",
                name=f"create_{ns}",
                output="screen",
                arguments=[
                    "-name", ns,
                    "-topic", f"{ns}/robot_description",
                    "-x", str(x), "-y", str(spawn_y), "-z", "0.1",
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
            nav_cfg = os.path.join(bridge_dir, f"nav2_{ns}.yaml")
            with open(nav_cfg, "w", encoding="utf-8") as f:
                yaml.safe_dump(_nav_config(ns, rosy_nav_share, inflation_radius),
                               f, sort_keys=False)
            nav_args = {"namespace": ns, "params_file": nav_cfg}
            if map_yaml:
                nav_args["map"] = map_yaml
            group_actions.append(
                IncludeLaunchDescription(
                    AnyLaunchDescriptionSource(
                        os.path.join(rosy_nav_share, "launch", "gz_bringup_launch.xml")
                    ),
                    launch_arguments=nav_args.items(),
                )
            )
        elif mode == "slam":
            slam_cfg = os.path.join(bridge_dir, f"mapper_{ns}.yaml")
            with open(slam_cfg, "w", encoding="utf-8") as f:
                yaml.safe_dump(_slam_config(ns, rosy_nav_share), f, sort_keys=False)
            group_actions.append(
                GroupAction([
                    PushRosNamespace(ns),
                    # slam_toolbox 는 맵을 절대 토픽 `/map`·`/map_metadata` 로 발행한다
                    # (네임스페이스를 push 해도 따라오지 않는다). N대를 띄우면 전부 같은
                    # 토픽에 겹쳐 쓴다 — 로봇별로 되돌려 준다.
                    SetRemap("/map", f"/{ns}/map"),
                    SetRemap("/map_metadata", f"/{ns}/map_metadata"),
                    IncludeLaunchDescription(
                        AnyLaunchDescriptionSource(
                            os.path.join(rosy_nav_share, "launch", "gz_map_building.launch.xml")
                        ),
                        launch_arguments={
                            "use_sim_time": "True",
                            "slam_params_file": slam_cfg,
                        }.items(),
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
        DeclareLaunchArgument("inflation_radius", default_value="0.0",
                              description="코스트맵 팽창 반경 덮어쓰기 (0 이면 nav2_params.yaml 값). "
                                          "좁은 통로 월드는 통로 반폭보다 크게"),
        DeclareLaunchArgument("spawn_x", default_value="0.0",
                              description="첫 로봇의 spawn x. 원점에 구조물이 있는 월드(미로 등)에서 쓴다"),
        DeclareLaunchArgument("spawn_y", default_value="0.0",
                              description="모든 로봇의 spawn y"),
        DeclareLaunchArgument("spawn_spacing", default_value="1.5",
                              description="로봇 간 x축 배치 간격 (m)"),
        DeclareLaunchArgument("core", default_value="false",
                              description="로봇별 rosy_core 기동 (포트 api_port_base + i - 1)"),
        DeclareLaunchArgument("map", default_value="",
                              description="mode:=nav 이 쓸 맵 yaml (빈 값이면 rosy_navigation 기본 맵)"),
        DeclareLaunchArgument("api_port_base", default_value="8080",
                              description="첫 로봇의 rosy_core API 포트"),
        OpaqueFunction(function=_launch_setup),
    ])
