## D-80 G4 GO는 Device 표면이다

**Status:** Accepted (2026-09-17). D-72 HOST 조각을 Device GO와 가른다.

**Context:** D-72 S3–S6이 `fresh`/`delayed`/`disconnected`/`unavailable`과 stale
teleop 차단을 HOST 시험으로 올렸다. G4 본문은 다섯 safety 상태, 나열된 Nav2
이름, 보정 상태기계, Device viewport 터치/키보드, 권한 경로의 Device 증거도
요구한다. HOST 조각만으로 G4를 닫으면 벤치 화면이 현장 화면이 된다.

**Decision:** G4 GO는 **Device viewport에서** 다음이 증빙될 때만이다.

- 다섯 상태 `NORMAL`/`LIMITED`/`HOLD`/`ESTOP_LATCHED`/`RECOVERY_PENDING` (G0/D-51)
- G4가 나열한 navigation 이름 또는 그에 대한 사상표
- 보정: check → prepare → confirm → progress → cancel/fail → save → apply
- 권한 경로와 세션 철회
- 지원 Device viewport의 터치·키보드

HOST 증거 4상태와 `/dashboard` 단일 콘솔(D-77)은 G4를 **이행 중이게** 하지
**닫지 않는다.** G4 행의 상태·증거는 device-validation 계획만 쓴다.

**Alternatives:** HOST pytest로 G4를 GO하는 안은 계층을 속인다. G4를 대시보드
색 계약으로 줄이는 안은 D-72가 이미 나눈 법을 다시 섞는다.

**Consequences:** G4는 HOLD. 다섯 상태 매핑은 D-51이 연다. 이 ADR이 보정 UI를
구현하지 않는다.

**Validation / Transition:** device-validation G4 HOST 단락. `test_evidence.py`,
`test_dashboard.py`는 HOST. Device viewport 시험은 아직 없다.

**References:** D-51, D-72, D-77,
[device-validation G4](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
