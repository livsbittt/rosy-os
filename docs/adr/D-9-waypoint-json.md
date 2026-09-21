## D-9 Waypoint 로컬 저장소 (JSON)

**Status:** Accepted (2026-08)

**Context:** Waypoint는 로봇 독립 동작(Local-First)에 필요하므로 Fleet 의존 없이 보존되어야 한다.

**Decision:** 로봇 로컬 파일(JSON, `~/.rosy/waypoints.json`)을 원천 저장소로 한다. Fleet은 동기화 API로 읽기/내려보기만 한다(WPT-005).

**Consequences:** Fleet 장애에도 주행 가능. 로봇 다중화 시 Fleet이 조정(마지막 쓰기 승자 방지는 Fleet 동기화 순서로 관리).

---
