## D-121 Cyclone 적용은 CORE 기동 전이고 웹은 보고만 한다

**Status:** Accepted (2026-09-18). D-117의 기동 훅이다. 웹이 RMW를 바꾸지 않는다.

**Context:** RMW는 `rclpy.init()` 때 로드된다. 그 다음 `os.environ` 이나 REST 로
FastDDS→Cyclone 을 바꿔도 **이미 떠 있는 노드에는 안 먹는다.** 브라우저 버튼으로
"사이클론 적용"을 주면 화면만 바뀌고 DDS는 그대로다. 미들웨어(`rosy_core`)는
프로세스를 여는 쪽이라, init **앞**에서만 채울 수 있다.

이미 있는 것: compose/`rosy_env.sh`/`env.sh`/`gz_multi` 가 RMW를 박음 (D-117).
`RosGraphMonitor` 는 Cyclone XML 의 lo 여부를 본다. 대시보드는 isolation 을
보여 준다. 빠진 것은 (1) `ros2 run rosy_core` 처럼 env 가 비었을 때 CORE 스스로
채우기, (2) 잘못된 RMW로 기동을 거절, (3) 스냅샷에 `rmw` 이름.

**Decision:**

- `apply_cyclone_rmw(env)` 를 `rclpy.init()` **전에** 부른다
- `RMW_IMPLEMENTATION` 이 비면 `rmw_cyclonedds_cpp` 를 채운다
- 다른 값이면 기동 실패 (`RmwError`). 조용히 덮어쓰지 않는다
- `CYCLONEDDS_URI` 는 compose/`rosy_env.sh` 가 연다. CORE 가 XML 경로를 추측해
  덮지 않는다 (시뮬 D-120 과 로봇 lo 프로파일이 다르다)
- `GET /api/v1/system/runtime` 의 ros 스냅샷에 `rmw` 를 넣는다. 웹은 표시만
- RMW를 바꾸는 REST/WS/대시보드 버튼은 만들지 않는다
- Fleet 은 로봇 RMW를 원격 설정하지 않는다

**Alternatives:** 웹에서 적용하는 안은 init 이후라 거짓 성공이다. 잘못된 RMW를
덮어쓰는 안은 운영자가 FastDDS를 디버그로 켠 이유를 지운다.

**Consequences:** env 가 비어도 CORE 한 프로세스는 Cyclone으로 뜬다. 이미 FastDDS로
init 된 이웃 노드는 이 훅이 고치지 못한다 — 그쪽도 같은 env로 다시 띄운다.

**Validation / Transition:** `test_rmw.py`, `test_ros_graph_monitor.py`,
`test_dashboard.py`. DEVICE PARKED.

**References:** D-1, D-117, D-120.

**Amendment (2026-09-18):** FastDDS 거절은 D-122 가 다음 기동에서 고치는 쪽으로
바꾼다. 웹 버튼·`system.reboot` 로 RMW를 고치지 않는 결정은 유지한다.

---
