## D-70 워크플로 엔진은 로봇이 아니라 Fleet이다

**Status:** Accepted (2026-09-17). concept 08. D-12를 concept Task/Workflow에
명시한다.

**Context:** concept 08은 Task 상태(PENDING…BLOCKED)와 TransportObject 같은
워크플로를 적는다. D-12는 미션 DSL을 Fleet에만 둔다. 로봇에 두 번째 상태기계를
만들면 원자 액션 API와 미션이 섞인다.

**Decision:** 로봇이 노출하는 Task는 `TaskKind`(MOVE, NAVIGATE, RETURN_HOME,
FOLLOW, DOCK)와 기존 매니저다. PENDING→SUCCEEDED 워크플로 객체, 우선순위
스케줄러, 크로스 디바이스 워크플로는 로봇에 두지 않는다. 미션은 Fleet(미구현)
영역이다. `TaskKind.concept_id`가 필요한 개념 capability를 가리킨다.

**Alternatives:** 로봇에 concept 08 상태기계를 심는 안은 D-12와 로컬 안전
경계를 흐린다. 채택하지 않는다.

**Consequences:** CORE 라우트는 원자 액션만 추가한다. Pick/Place/Transport
워크플로는 D-55·D-71 이전에는 API에 없다.

**Validation / Transition:** `TaskKind` 목록과 inventory `task_kinds`. 새
미션 리소스가 `rosy_core`에 생기면 이 결정을 어긴다.

**References:** [concept 08](../concept/08_ROSY_Task_and_Workflow.md), D-12.

---
