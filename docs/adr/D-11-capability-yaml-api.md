## D-11 Capability 정적 YAML → API 노출

**Status:** Accepted (2026-08)

**Context:** 이기종 로봇·AI 사전 검증을 위해 기능 선언이 필요하다. 동적 협상은 초기에 과하다.

**Decision:** Capability는 로봇의 정적 설정(YAML)에서 생성되어 `GET /system/capabilities`로 노출된다. Robot Profile(HWA)이 원천 데이터다(HWA-003).

**Consequences:** 구현 단순·예측 가능. 동적 capability(런타임 장착 등)는 capability_version 상향으로 확장.

---
