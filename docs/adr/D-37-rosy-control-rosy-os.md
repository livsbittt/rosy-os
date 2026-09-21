## D-37 Rosy Control을 Rosy OS 내부 기능으로 흡수

**Status:** Accepted (2026-09-12). 설계 결정 상태이며 구현·장치 인수 상태와 구분한다.

**Context:** Control의 코드·웹·배포를 별도로 유지하면 장치 운영과 정비의 소유권이 나뉜다. 사용자가 Rosy OS 단일 제품 방향을 확정했다.

**Decision:** 제품·저장소·설치 기준은 Rosy OS로 통일한다. src/rosy_control은 호환성을 유지하는 내부 패키지로 편입한다. 외부 API와 웹은 rosy_core, 하드웨어는 IO/bringup, 배포·복구는 기존 deploy가 소유한다. D-1·D-18·D-22·D-23을 유지한다.

**Alternatives:** 별도 Control 제품 유지와 즉시 전면 패키지 분할을 검토했다. 전자는 운영 중복을 남기고 후자는 기능 이전과 import 변경을 결합하므로 채택하지 않는다.

**Consequences:** 원본은 provenance로 보존한다. 역방향 의존성·선택 설치·장애 격리가 필요하면 내부 패키지 경계를 재검토한다.

**Validation / Transition:** T0·T1 소스 편입과 package build는 완료. T2~T8 런타임 통합은 미완료. 원본 checkout 없이 설치·기동·정비·rollback까지 재현해야 흡수를 종료한다.

**References:** [상세 설계](../plans/2026-09-12-rosy-os-control-integrated-design.md), [실행 계획](../plans/2026-09-12-rosy-control-absorption-plan.md), [현재 증거](../plans/2026-09-12-control-absorption-results.md).

---
