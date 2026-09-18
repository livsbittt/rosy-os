"""ROS-free Gazebo sim package surface (D-73). Launch tests stay skippable."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_and_multi_robot_launch_exist():
    package = (ROOT / "package.xml").read_text(encoding="utf-8")
    assert "<name>rosy_gz_sim</name>" in package
    assert "rosy_fleet" in package
    launch = (ROOT / "launch" / "gz_multi.launch.py").read_text(encoding="utf-8")
    assert "gz_multi" in launch or "core" in launch
    assert "rosy_core" in launch
    assert "spawn_x" in launch
    assert "inflation_radius" in launch
    assert "slam_nav" in launch
    assert (ROOT / "config" / "worlds.yaml").is_file()
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "config" in cmake


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
    text = script.read_text(encoding="utf-8")
    assert "initialpose" in text
    assert "import rosy_core" not in text
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "scripts/seed_initialpose.py" in cmake


def test_world_to_map_is_installed_and_bench_worlds_exist():
    """HOST에서 도는 정답 맵 생성기가 패키지 표면이다. launch skip이 SOURCE가 아니다."""
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "scripts/world_to_map.py" in cmake
    assert (ROOT / "scripts" / "world_to_map.py").is_file()
    assert (ROOT / "worlds" / "rosy_swarm_bench.world").is_file()
    assert (ROOT / "worlds" / "rosy_maze.world").is_file()
