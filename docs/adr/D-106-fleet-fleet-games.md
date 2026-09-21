## D-106 Fleet 매치 시작은 나중에 Fleet→games 한 방향이며 지금은 버튼을 만들지 않는다

**Status:** Accepted (2026-09-18). D-90 남은 통로 결정이다. 콘솔 버튼을 지금
구현하지 않는다.

**Context:** D-90 수정은 "심판을 Fleet 서버로 옮긴다"는 말이 매치 시작 버튼의
자리이지 규칙 엔진의 이사가 아니라고 적었다. 남은 표는 그 버튼을 "지금
구현하지 않음"으로만 남겨 다음 세션이 Fleet 콘솔에 축구를 넣거나
`rosy_games` 보드에 관제 시작을 붙이기 쉽다. Fleet 서버 v1은 REST gather와
목표·전체 정지가 있다 (D-81). `hub --listen`은 D-88 뒤다.

**Decision:**

- 매치 **시작 버튼**이 생기면 **Fleet 콘솔**에만 산다. `rosy_games` 보드·CLI에
  Fleet 시작 UI를 넣지 않는다
- 그 버튼이 하는 일은 `rosy_games` `MatchHost.reset()` / `run_match`를 **한 방향**
  으로 부르는 것이다. 규칙을 Fleet에 복제하지 않는다
- **지금은 버튼을 만들지 않는다.** D-88 소켓과 현장 계단 4(D-96) 앞에 관제
  매치 UI를 열지 않는다
- `rosy_fleet`은 `rosy_games`를 import하지 않는다. `rosy_games`는 `rosy_fleet`을
  import하지 않는다 (이미 경계 시험)
- `reset()`의 주인은 계속 `rosy_games`다 (D-12, D-90)
- games를 D-62 슬라이스에 올리지 않는다 (이미 `test_rosy_games_surface.py`)

**Alternatives:** 지금 Fleet 콘솔에 축구 시작을 넣는 안은 규칙과 관제를 한
화면에 섞는다. games 보드에 "Fleet 시작"을 넣는 안은 노트북 게임 표면이
관제가 된다 (D-101).

**Consequences:** 노트북 경기는 계속 `rosy_games match`다. Fleet 콘솔은 로봇
목표·일괄 stop만 유지한다.

**Validation / Transition:** `test/test_rosy_games_surface.py` —
Fleet 소스가 `rosy_games`를 모르고, 게임 보드/CLI에 fleet 시작이 없다.
`RobotMode.SOCCER` 없음. DEVICE/FIELD PARKED.

**References:** D-12, D-62, D-81, D-88, D-90, D-101.

---
