## D-116 관제 양보는 출발 로봇과 겹친 pose를 길로 보지 않는다

**Status:** Accepted (2026-09-18). 관제 기하 가드다. DEVICE/FIELD GO가 아니다.

**Context:** 양보는 경로 위 `yield_keep_out` 안의 **서 있는** 로봇을 치운다. 출발
로봇과 차단 로봇이 같은 좌표(측위 실패·odom 원점)면, 출발점에서 목표로 그은 직선이
그 좌표를 지나 **자기 원점의 유령**을 길로 본다. 2026-09-18 시뮬에서 `rosy_01` 목표
하달이 `YIELDING` / `blocked_by rosy_02` 가 되고 `rosy_02` 가 양보 벽감으로 돌기
시작했다. 둘 다 pose ≈ (0,0) 이었다.

D-93 은 폭 면제를 거절한다. 겹친 보고를 면제하는 것은 폭이 아니라 **같은 점이라서
누가 길을 막는지 말할 수 없음**이다.

**Decision:**

- mover 와 후보의 pose 거리가 `COINCIDENT_M` (0.05 m) 미만이면 길로 보지 않는다
- 0.05 m 는 풋프린트보다 작고, factory spawn 간격(0.6 m)보다 훨씬 작다
- 이 가드가 AMCL 시드(D-115)를 대신하지 않는다. 둘 다 필요하다
- 실제 0.05 m 안에 두 대가 있는 배치는 이 가드가 중재를 포기한다. 그 배치는 시뮬
  spawn 계약이 아니다

**Alternatives:** (0,0) 만 특수 처리하는 안은 맵 원점 spawn 월드에서 실패한다.
양보를 끄면 D-93 실측(빈 방 맞물림)이 돌아온다.

**Consequences:** `traffic.coincident`. 호스트 pytest 로 DEVICE GO 하지 않는다.

**Validation / Transition:** `test_server_yield.py`. ROS-SIM HOLD.

**References:** D-12, D-93, D-115.

---
