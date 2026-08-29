#!/usr/bin/env bash
# env.sh — ROSY 개발 환경 공통 진입점
# 사용: source env.sh
#   - /opt/ros/$ROS_DISTRO/setup.bash source (기본 jazzy)
#   - 워크스페이스 install/setup.bash가 있으면 추가 source (colcon build 후)
# 빌드: source env.sh && colcon build --base-paths src

ROS_DISTRO="${ROS_DISTRO:-jazzy}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    echo "rosy env: ROS 2 $ROS_DISTRO sourced"
else
    echo "rosy env: WARNING - /opt/ros/$ROS_DISTRO not found" >&2
fi

if [ -f "$REPO_DIR/install/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "$REPO_DIR/install/setup.bash"
    echo "rosy env: workspace install sourced"
fi

# 로봇(실기기)에서는 대신 rosy_bringup의 로봇별 격리 스크립트 사용:
#   source $(ros2 pkg prefix rosy_bringup)/share/rosy_bringup/scripts/rosy_env.sh 1
