## D-67 RobotMode가 운용 계약이고 DeviceState는 inventory 파생이다

**Status:** Accepted (2026-09-17). concept 06.

**Context:** concept 06은 BOOTING…UPDATING 장치 수명 주기를 적는다. 살아 있는
계약은 `RobotMode`(`IDLE|MANUAL|NAVIGATION|DOCKING|EMERGENCY`)와 안전 정지다.
두 상태 기계를 명령 경로에 나란히 두면 클라이언트가 어느 쪽이 권위인지
모른다.

**Decision:** 명령·안전·deadman의 권위 상태는 `RobotMode`다. concept
`DeviceState`는 `GET /api/v1/system/inventory`의 파생 값이다. EMERGENCY/e-stop
→ `SAFE_STOP`, diagnostics ERROR → `FAULT`, 바쁜 모드 → `BUSY`, 스냅샷 전
→ `BOOTING`, 그 외 IDLE+정상 → `READY`. `RobotMode` enum을 concept 이름로
바꾸지 않는다.

**Alternatives:** `RobotMode`를 concept 06 enum으로 교체하는 안은 API와 안전
시험을 깨뜨린다. DeviceState를 명령 거절의 유일한 근거로 쓰는 안은 기존
estop/모드 경로와 이중화된다. 채택하지 않는다.

**Consequences:** inventory는 개념 수명 주기를 보여 준다. 텔레옵·내비 거절은
계속 모드·safety·CAP-003이다. 진단이 오기 전 `GET /inventory`는 BOOTING이고
`RobotMode`는 IDLE이다.

**Validation / Transition:** `test_domain_model.py` READY/SAFE_STOP/BOOTING.
`test_api.py::test_inventory_is_booting_before_diagnostics_arrive` 와
`test_inventory_leaves_booting_after_a_diagnostic`. `RobotMode` 스키마 시험은
그대로 통과해야 한다. HOST 2026-09-17: 해당 묶음 19 passed.

**References:** [concept 06](../concept/06_ROSY_Device_State_and_Lifecycle.md), D-65.

---
