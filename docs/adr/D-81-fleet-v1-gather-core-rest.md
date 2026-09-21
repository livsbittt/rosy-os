## D-81 Fleet 콘솔 v1 gather는 CORE REST 폴링이다

**Status:** Accepted (2026-09-17). D-5 outbound WS를 뒤집지 않는다. 콘솔 v1
경로만 고정한다.

**Context:** D-5는 로봇이 Fleet에 outbound WS로 붙는다고 했다. D-59는 관제 PC의
한 Fleet 서버가 모은다고 했다. 지금 `rosy_fleet console`은 N대를 한 화면에 모으고
목표·취소를 내리지만, `hub --listen`과 CORE `FleetAgent` outbound는 없다. gather는
CORE REST 폴링이다. "Fleet 서버 미구현"과 "콘솔이 이미 있다"가 같이 적혀 혼선이
난다.

**Decision:** v1 콘솔의 gather는 **CORE REST 폴링**이다.

- `rosy_fleet hub --listen`과 `FleetAgent` outbound는 다음 단계다. 없어도 콘솔
  v1은 유효하다.
- D-5 outbound WS는 목표 경로로 남는다. 에이전트가 붙으면
  `FleetConsole.snapshot()` 출처만 바뀐다.
- Fleet은 최종 `cmd_vel` 소스가 아니다(D-38, D-59).
- 물리 대형 실측과 D-35 후보는 이 결정이 닫지 않는다.

**Alternatives:** 콘솔을 outbound 전까지 금지하는 안은 이미 있는 운용 화면을
지운다. REST 폴링을 D-5 대체로 승격하는 안은 로봇→Fleet 푸시를 포기한다.
채택하지 않는다.

**Consequences:** concept README의 "Fleet unimplemented"은 서버 소켓을 말하고
콘솔 v1을 말하지 않는다. sim bench Task 14와 D-35는 별도다.

**Validation / Transition:** `src/rosy_fleet/test` 콘솔 시험. 패키지 `rclpy`
금지(`test_boundaries.py`). hub listen 시험은 이 ADR이 요구하지 않는다.

**References:** D-5, D-12, D-20, D-38, D-59, D-70,
[site fabric](../plans/2026-09-14-site-middleware-role-fabric-design.md).

---
