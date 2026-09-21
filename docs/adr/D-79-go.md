## D-79 게이트 GO는 현재 트리 재실행만 인정한다

**Status:** Accepted (2026-09-17). D-61의 증거 규칙이다.

**Context:** device-validation 계획 §1 표는 ROS-SIM을 `GO(기존 증거)`로 적는다.
같은 날 모듈 `progress.md`는 rosy_core ROS-SIM을 HOLD로 두고 "2026-09-13 이후
현재 트리로 재실행하지 않음"을 blocker로 적는다. 옛 GO 행을 그대로 쓰면 호스트
pytest나 지난 컨테이너 한 번이 Device 앞 계층을 닫은 것처럼 보인다.

**Decision:** 모듈 게이트 GO는 **그 모듈 `progress.md`가 가리키는 명령의 현재
트리 재실행**만 인정한다.

- 계획 문서의 옛 GO 행은 대체 증거가 아니다. 충돌하면 progress가 이긴다.
- 재실행하지 않은 과거 결과는 HOLD(blocker: 재실행 필요)다.
- 상위 계층 결과로 하위 계층을 GO로 쓰지 않는다(호스트 pytest ≠ Device).

**Alternatives:** 계획 표만 믿는 안은 지금 모순이다. 모든 옛 증거를 삭제하는 안은
역사를 지운다. 채택하지 않는다.

**Consequences:** rosy_core/control/nav ROS-SIM은 현재 트리 재실행 전까지 HOLD다.
device-validation §1 ROS-SIM 칸은 이 결정을 따른다. ARTIFACT/DEVICE는 변하지
않는다.

**Validation / Transition:** `STATUS.md` HOLD blockers. `tools/harness` lint가
`GO`에 evidence·cmd를 요구한다. 계획 §1 표의 ROS-SIM 행을 HOLD로 정정한다.

**References:** D-39, D-61,
[device-validation](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md),
[module harness](../plans/2026-09-15-module-harness-design.md).

---
