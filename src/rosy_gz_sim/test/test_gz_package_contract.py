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


def test_world_to_map_is_installed_and_bench_worlds_exist():
    """HOST에서 도는 정답 맵 생성기가 패키지 표면이다. launch skip이 SOURCE가 아니다."""
    cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "scripts/world_to_map.py" in cmake
    assert (ROOT / "scripts" / "world_to_map.py").is_file()
    assert (ROOT / "worlds" / "rosy_swarm_bench.world").is_file()
    assert (ROOT / "worlds" / "rosy_maze.world").is_file()
