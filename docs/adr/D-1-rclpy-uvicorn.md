## D-1 단일 프로세스 (rclpy + uvicorn 스레드)

**Status:** Accepted (2026-08)

**Context:** rosy_core는 ROS 2 노드와 Web API 서버를 모두 구동해야 한다. 별도 프로세스 + ROS 통신 구조도 가능했다.

**Decision:** 단일 프로세스로 Main Thread는 rclpy(MultiThreadedExecutor), Worker Thread는 uvicorn+FastAPI로 구동한다. 스레드 간 데이터는 State Manager의 불변 스냅샷 + 짧은 락으로 보호한다.

**Consequences:** 배포·상태 공유가 단순하다. 기존 Flask 서버도 동일 구조로 검증됨. 대신 장애 격리는 약하므로 systemd 재시작(D-1 보완)과 지연 모니터링에 의존한다.

---
