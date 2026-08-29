"""rosy_core.main — 진입점: ROS 노드 기동 + API 서버 (P1-1, ADR-D-1).

프로세스 구조:
- Main Thread: rclpy 노드 "rosy_core" (MultiThreadedExecutor)
- Worker Thread: uvicorn + FastAPI

P1-1 스캘폴딩 단계 — 각 매니저는 등록만 수행하고, 실제 구현은
P1-3~P1-20 태스크에서 채운다 (ROSY-PLN-001 §7 Phase 1).
"""

from __future__ import annotations


def main() -> None:
    import rclpy

    from rosy_core.config import load_config
    from rosy_core.node import RosyCoreNode

    rclpy.init()
    config = load_config()
    node = RosyCoreNode(config)
    try:
        node.run()
    finally:
        node.shutdown()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
