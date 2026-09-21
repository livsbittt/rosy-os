## D-43 보정 schema와 릴리스 generation 저장 매핑

**Status:** Proposed (2026-09-12). 설계 결정 상태이며 구현·장치 인수 상태와 구분한다.

**Context:** 보정은 장치별 데이터이며 OS 업데이트와 rollback에서 보존되어야 한다. 임의의 전역 저장 경로는 D-36의 generation 복구 규칙을 우회할 수 있다.

**Decision:** 장치 identity, schema·geometry·calibration revision, 단위·범위, 변경 감사, 원자적 쓰기와 적용 acknowledgement를 요구한다. /var/lib/rosy/calibration/<device-id>/는 컨테이너 내부 후보 경로다. 호스트에서는 D-36의 활성 data-working/<generation>에 대응해야 하며 정확한 파일명·schema·migration은 미확정이다.

**Alternatives:** 읽기 전용 package share에 쓰거나 모든 generation이 하나의 mutable 보정 파일을 공유하는 안은 채택하지 않는다. 기존 보정 형식 보존과 versioned schema 변환을 비교한다.

**Consequences:** 일반 설정 로더의 config/rosy_default.yaml → ~/.rosy/rosy.yaml → ROSY_CONFIG 순서를 바꾸지 않는다. 장치 profile과 측정 보정의 필드별 결합·충돌 규칙은 별도 정의한다.

**Validation / Transition:** T2에서 손상·장치 불일치·범위 초과·쓰기 실패·재부팅을 시험하고 T6에서 activation/rollback 데이터 격리와 schema 호환을 확인한다. 구버전 복구가 검증된 migration 정책을 기록한 뒤 승격한다.

**References:** [상세 설계](../plans/2026-09-12-rosy-os-control-integrated-design.md), [실행 계획](../plans/2026-09-12-rosy-control-absorption-plan.md), [현재 증거](../plans/2026-09-12-control-absorption-results.md).

---
