---
module: rosy_fleet
logical_modules: [M07, M11]
owner: FLEET
last_verified: { commit: "dc89264", date: 2026-09-17 }
gates:
  SOURCE:
    state: GO
    evidence: "패키지 순수성·hub CORE import 경계 계약 시험 통과 (2026-09-17, 6 passed). server/ 추가 후에도 rclpy 금지 유지"
    cmd: "python3 -m pytest src/rosy_fleet/test/test_boundaries.py -q"
  LOCAL:
    state: GO
    evidence: "235 passed, 5 skipped (2026-09-17 Windows, 미커밋 WIP 포함 작업 트리). Fleet 서버 v1 시험 19건 포함"
    cmd: "python3 -m pytest src/rosy_fleet/test -q"
  ROS-SIM:
    state: GO
    evidence: "Task 14 sim bench 실행 (2026-09-17, WSL ROS 2 Jazzy + Gazebo, rosy_swarm_bench 2대). follow: relay_tx_hz 9.93~10.07, leader_rx_hz 9.45~10.07 (D-31 요구 >=10 Hz), slot_err_m 최소 0.04 / 마지막 10 표본 최대 0.59. hold: 릴레이 pause(t=30.7) -> 팔로워 holding(t=31.8) = 1.07 s, stream_timeout_ms 1000 과 일치"
    cmd: "python3 src/rosy_gz_sim/scripts/swarm_bench.py --robots <robots.yaml> --leader rosy_01 --scenario follow|hold"
  ARTIFACT:
    state: PARKED
  DEVICE:
    state: PARKED
  FIELD:
    state: PARKED
adrs: [D-5, D-10, D-12, D-18, D-20, D-21, D-30, D-31, D-59, D-60]
plans:
  - docs/plans/2026-09-14-site-middleware-role-fabric-design.md
  - docs/plans/2026-09-14-site-middleware-role-fabric.md
  - docs/plans/2026-09-08-swarm-formation-slice-design.md
  - docs/plans/2026-09-08-swarm-formation-slice.md
  - docs/plans/2026-09-08-swarm-formation-slice-results.md
  - docs/plans/2026-09-15-module-harness-design.md
---
## 지금 상태

- Formation geometry(FOR-001)·slot assignment(FOR-002)는 순수 함수다. 리더→팔로워 pose 릴레이는 바이트 그대로 팬아웃하고 새 프레임을 합성하지 않는다(D-31). FOR-004 세션(arm→relay→watch→hold)과 SiteHub 계약 gather(hello/heartbeat/event)·REST scatter(e-stop)(D-59)까지 구현·시험됨.
- `test_boundaries.py`가 패키지 전체 `rclpy` 금지와 `hub/`의 `rosy_core.protocol.schemas` 외 CORE import 금지를 강제한다(D-18).
- **Fleet 서버 v1 있음**: `rosy_fleet console --robots robots.yaml` 이 N대를 한 화면에 모으고 로봇별 목표·취소와 전체 정지를 내린다(site-fabric 설계 §2, 전환 순서 3단계). WSL ROS 2 Jazzy + Gazebo 2대 위에서 지도 클릭 미션 하달 → 양쪽 `ARRIVED` 확인(2026-09-17).
- 아직 없는 것: `rosy_fleet hub --listen` 소켓과 CORE `FleetAgent` outbound. 그래서 v1 의 gather 는 REST 폴링이다 — 에이전트가 붙으면 `FleetConsole.snapshot()` 의 출처만 바뀐다.
- 물리 대형(FAT-06 등) 실측은 아직 없다. D-35(전체 HOLD는 릴레이를 끊는 것)는 sim bench 실측 대기 중인 후보이며 ADR log에는 의도적으로 미등재다(`adr_gaps`).
- 작업 트리에 미커밋 변경 있음(`AGENTS.md` 갱신 3건 + `formation/`·`swarm/` `AGENTS.md` 신규). LOCAL 증거는 이 작업 트리 기준이다.

## 다음 gate

1. 진행 중인 WIP를 커밋하고 LOCAL을 커밋 기준으로 재실행해 `last_verified.commit`을 채운다.
2. `swarm-formation-slice-results.md` Task 14 sim bench(`gz_multi robots:=N mode:=nav core:=true`)를 ROS box에서 실행해 `relay_tx_hz`/`slot_err_m`/HOLD latency를 실측하고 D-35 등록 여부를 결정한다.
3. `FleetAgent` outbound(WS hello/heartbeat/event)를 열어 관제 gather 를 폴링에서 밀어내기(설계 §3).
4. 실물 2대 FAT-06 변형 필드 시험(`capabilities.hardware.yaml`의 `swarm.follow/lead` 점등 포함) 후 FIELD를 승격한다.

## 현재 유효한 금지사항

- `formation/`과 `swarm/arming.py`는 `httpx`/`websockets`/`rclpy`/`asyncio`를 import하지 않는다(순수성, `test_boundaries.py`가 강제).
- `hub/`는 `rosy_core.protocol.schemas` 외 `rosy_core`의 무엇도 import하지 않는다(D-18, D-59).
- Hub는 `COMMAND` envelope, `cmd_vel`/`image`/`twist` 페이로드, `PEER` 참조 소스 scatter를 `ROLE_VIOLATION`으로 거절한다(D-59, D-31).
- 관제 UI 가 로봇 `cmd_vel`·DDS 에 붙지 않는다(설계 §6). 내리는 것은 원자 액션뿐이다.
- `map` 프레임을 로봇별로 접두하지 않는다. CORE 가 `map` 고정으로 pose 를 읽고 목표를 받는다(`ros_bridge._map_frame`).
- `rosy_core`를 이 패키지에서 수정하지 않는다. 로봇 계약에 없는 것은 API Ref 사이클의 finding이지 로컬 patch가 아니다.
