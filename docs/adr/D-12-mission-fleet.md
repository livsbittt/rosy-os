## D-12 Mission은 Fleet 전용

**Status:** Accepted (2026-08)

**Context:** 미션 상태머신을 로봇에 두면 Fleet 장애 시에도 미션이 돌지만, 로봇별 중복 구현·디버깅 복잡도가 커진다.

**Decision:** Mission DSL 실행기는 Fleet에만 둔다. 로봇은 원자 액션(goto/home/stop/estop)과 이벤트를 제공한다. Local-First는 "기본 조작" 수준에만 적용한다.

**Consequences:** 로봇 단순화, 미션 로직 단일 위치. Fleet 장애 시 진행 중 미션은 중단되나 로봇 안전은 SAF-003이 보장.

---
