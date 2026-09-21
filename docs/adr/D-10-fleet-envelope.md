## D-10 Fleet 프로토콜 envelope 조기 고정

**Status:** Accepted (2026-08)

**Context:** Fleet 구축은 Phase 4이지만, 프로토콜(envelope·heartbeat·ack·이벤트)을 늦게 정하면 Phase 4에서 로봇 측 재작업이 발생한다.

**Decision:** 프로토콜 envelope v1과 이벤트 모델을 Phase 1에서 스키마로 고정(공유 패키지/스키마 정의)하고, 로봇은 Phase 1부터 이 스키마로 이벤트·상태를 발행한다.

**Consequences:** Phase 4 착수 시 계약만 구현하면 됨. 초기 스키마 설계 오류 위험은 추가 전용 버저닝(PRT-006)으로 완화.

---
