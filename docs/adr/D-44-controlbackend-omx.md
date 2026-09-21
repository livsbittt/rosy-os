## D-44 ControlBackend 채택과 OMX 작업 액션 경계

**Status:** Proposed (2026-09-12). 설계 결정 상태이며 구현·장치 인수 상태와 구분한다.

**Context:** Control의 자율 로직 재사용과 향후 Pinky Pro+OMX 박스 이동·적층이 필요하지만 backend 채택, arm 모델과 적재 조건은 미결정이다.

**Decision:** Control 로직은 Nav2 보조·격리 검증·선택 backend 후보로 비교한다. OMX는 로봇 측 원자 액션과 안전 interlock 확장으로 설계하며 Fleet의 상위 임무 소유권(D-12)을 변경하지 않는다. 로컬 연속 작업 오케스트레이션을 제품 기능으로 채택하려면 D-12 확장 여부를 별도 ADR로 결정한다.

**Alternatives:** ControlBackend 전면 채택, Nav2 보조만 사용, 시험 전용 보존을 동일 시나리오로 비교한다. 베이스·팔 동시 동작과 로컬 임무 엔진은 이번 문서로 승인하지 않는다.

**Consequences:** OMX-F/OMX-AI 등 모델 결정과 하중·중심·도달거리·전원·hand-eye 검증 전에는 arm capability를 활성화하지 않는다. 박스 적층 알고리즘은 T2~T8 흡수 완료 조건에 넣지 않는다.

**Validation / Transition:** T4에서 지도·localization·우회·취소·재기동·namespace·자원 비용으로 backend를 판정한다. OMX 액션은 베이스 정지·고정 확인, 보정 revision, arm 실행·결과 확인을 실물 검증한 후 별도 구현 결정으로 승격한다.

**References:** [상세 설계](../plans/2026-09-12-rosy-os-control-integrated-design.md), [실행 계획](../plans/2026-09-12-rosy-control-absorption-plan.md), [현재 증거](../plans/2026-09-12-control-absorption-results.md).

---
