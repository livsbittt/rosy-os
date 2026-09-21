## D-38 흡수된 모든 이동 명령의 최종 중재와 정지는 CORE가 소유

**Status:** Accepted (2026-09-12). 설계 결정 상태이며 구현·장치 인수 상태와 구분한다.

**Context:** legacy SafetyNode와 CORE RosBridge가 각각 최종 cmd_vel을 발행할 수 있어 무조건 함께 기동할 수 없다.

**Decision:** D-2를 보강한다. CommandManager가 후보를 선택하고 SafetyManager가 최종 제한을 적용하며 RosBridge만 모터 cmd_vel을 발행한다. Control 보정·주행도 이 경로를 통과한다. IO deadman은 D-22대로 유지한다. e-stop·재기동·소유권 교체 때 과거 이동 명령을 폐기하고 새 요청을 요구한다.

**Alternatives:** 기존 SafetyNode를 최종 발행자로 유지하거나 두 발행자를 병렬 활성화하는 안은 CORE 명령 소유권과 충돌한다.

**Consequences:** 센서 기반 제한과 후보별 판단의 정확한 전달 계약은 D-42 Proposed다. Accepted는 물리 안전 인증이나 구현 완료를 의미하지 않는다.

**Validation / Transition:** T3에서 단일 publisher, stale·nonfinite·단절·모순 입력, e-stop 해제 후 자동 재가동 금지를 시험한다. 기록 재생과 무발행 shadow 비교 후 정지 상태에서 전환한다. 정지 지연·거리 한계는 실물 구동 시험 전에 장치별로 고정한다.

**References:** [상세 설계](../plans/2026-09-12-rosy-os-control-integrated-design.md), [실행 계획](../plans/2026-09-12-rosy-control-absorption-plan.md), [현재 증거](../plans/2026-09-12-control-absorption-results.md).

---
