## D-39 OS 운용·진단·유지보수와 완료 증거를 통합

**Status:** Accepted (2026-09-12). 설계 결정 상태이며 구현·장치 인수 상태와 구분한다.

**Context:** 소스 편입만으로 단일 제품 운영이나 기존 기능 동등성을 증명할 수 없다.

**Decision:** CORE 대시보드와 기존 인증 역할로 운전·보정·정비를 제공한다. 새 역할을 임의로 만들지 않는다. capability는 실제 준비 상태를 반영하며 stale 데이터는 현재값과 구분한다. D-36의 서명된 runtime 활성화·복구와 generation별 데이터 규칙을 계승한다. SOURCE/BUILD/LOCAL/SIM/ARTIFACT/DEVICE/FIELD 증거를 따로 기록한다.

**Alternatives:** 별도 Control 서버의 상시 유지, 파일 개수나 단위 테스트만으로 인수하는 안은 운용 동등성을 보장하지 않는다.

**Consequences:** 기능별 설정·시험·진단·복구 대장과 단독 운영 runbook을 T8 산출물로 만든다. 장치별 전환 책임자·복귀 조건을 기록한다.

**Validation / Transition:** T5 실제 브라우저 권한·단절·보정 흐름, T6 artifact·복구, G3/T7 Pinky Pro 실측, T8 원본 runtime 없는 운용을 각각 통과한다.

**References:** [상세 설계](../plans/2026-09-12-rosy-os-control-integrated-design.md), [실행 계획](../plans/2026-09-12-rosy-control-absorption-plan.md), [현재 증거](../plans/2026-09-12-control-absorption-results.md).

---
