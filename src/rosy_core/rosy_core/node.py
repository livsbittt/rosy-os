"""rosy_core.node — 중심 노드: 매니저 등록 + 실행 (P1-1 스캘폴딩).

각 매니저는 Phase 1 태스크에서 구현·연결된다:
- StateManager (P1-4, CORE-001)
- CommandManager (P1-5, CORE-002/CMD-001)
- SafetyManager (P1-6/P1-20, SAF-001~005)
- NavigationManager (P1-7, NAV-001~006)
- WaypointManager (P1-16, WPT)
- EventBus (P1-17, EVT, ADR-D-8)
- RosBridge (P1-3, ROS-101)
- FleetAgent (P4-2, PRT)
- API Server (P1-9/P1-10, API-101/102)
"""

from __future__ import annotations

from typing import Any

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node


class RosyCoreNode(Node):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__("rosy_core")
        self._config = config
        self.get_logger().info(
            "rosy_core starting: robot_id=%s", config.get("robot", {}).get("id", "unknown")
        )
        # TODO(P1-3~P1-20): 매니저 인스턴스화·연결

    def run(self) -> None:
        executor = MultiThreadedExecutor()
        executor.add_node(self)
        try:
            executor.spin()
        finally:
            executor.remove_node(self)

    def shutdown(self) -> None:
        self.get_logger().info("rosy_core shutting down")
