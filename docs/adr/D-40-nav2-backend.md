## D-40 Nav2 기본 유지와 단일 주행 backend 소유권

**Status:** Accepted (2026-09-12). 설계 결정 상태이며 구현·장치 인수 상태와 구분한다.

**Context:** CORE는 Nav2 action을 사용하고 Control은 GoalBrain·route·wander를 사용한다. 목표와 취소 결과의 중복 소유를 막아야 한다.

**Decision:** 기존 운영 기본값 Nav2를 유지한다. CORE NavigationManager가 세션·목표·취소·종료 결과를 소유하며 로봇별 활성 backend는 하나다. 취소된 세션의 늦은 결과는 현재 세션에 반영하지 않는다. 안전한 경로가 있으면 우회하고 없으면 정지한다.

**Alternatives:** 즉시 Control로 전환하거나 두 실행기를 동시에 사용하는 안은 현재 API와 취소 수명주기를 보존하지 못한다.

**Consequences:** ControlBackend의 운영 채택은 D-44에서 별도로 검증한다. 이 결정은 Nav2가 모든 시나리오에서 우수하다는 실측 결론이 아니다.

**Validation / Transition:** T4에서 목표·취소·늦은 결과·재시작·우회·막힘을 공통 시나리오로 검증한다. 경로 생성과 실측 도착을 구분한다.

**References:** [상세 설계](../plans/2026-09-12-rosy-os-control-integrated-design.md), [실행 계획](../plans/2026-09-12-rosy-control-absorption-plan.md), [현재 증거](../plans/2026-09-12-control-absorption-results.md).

---
