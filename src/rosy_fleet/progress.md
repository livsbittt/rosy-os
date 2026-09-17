---
module: rosy_fleet
logical_modules: [M07, M11]
owner: FLEET
last_verified: { commit: "uncommitted", date: 2026-09-15 }
gates:
  SOURCE:
    state: GO
    evidence: "패키지 순수성·hub CORE import 경계 계약 시험 통과 (2026-09-15, 6 passed)"
    cmd: "python3 -m pytest src/rosy_fleet/test/test_boundaries.py -q"
  LOCAL:
    state: GO
    evidence: "216 passed, 5 skipped (2026-09-15 Windows, 미커밋 WIP 포함 작업 트리)"
    cmd: "python3 -m pytest src/rosy_fleet/test -q"
  ROS-SIM:
    state: HOLD
    blocker: "swarm formation sim bench(Task 14, gz_multi robots:=N mode:=nav core:=true) 미실행. 패키지는 ROS를 import하지 않지만 relay·HOLD 지연 실측은 ROS/Gazebo 환경에서만 나온다"
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
- Fleet 서버·UI는 없다(Phase 4 대기). `rosy_fleet hub --listen` 소켓, 관제 UI, CORE `FleetAgent` outbound는 site-fabric 계획의 후속 항목이다.
- 물리 대형(FAT-06 등) 실측은 아직 없다. D-35(전체 HOLD는 릴레이를 끊는 것)는 sim bench 실측 대기 중인 후보이며 ADR log에는 의도적으로 미등재다(`adr_gaps`).
- 작업 트리에 미커밋 변경 있음(`AGENTS.md` 갱신 3건 + `formation/`·`swarm/` `AGENTS.md` 신규). LOCAL 증거는 이 작업 트리 기준이다.

## 다음 gate

1. 진행 중인 WIP를 커밋하고 LOCAL을 커밋 기준으로 재실행해 `last_verified.commit`을 채운다.
2. `swarm-formation-slice-results.md` Task 14 sim bench(`gz_multi robots:=N mode:=nav core:=true`)를 ROS box에서 실행해 `relay_tx_hz`/`slot_err_m`/HOLD latency를 실측하고 D-35 등록 여부를 결정한다.
3. 실물 2대 FAT-06 변형 필드 시험(`capabilities.hardware.yaml`의 `swarm.follow/lead` 점등 포함) 후 FIELD를 승격한다.

## 현재 유효한 금지사항

- `formation/`과 `swarm/arming.py`는 `httpx`/`websockets`/`rclpy`/`asyncio`를 import하지 않는다(순수성, `test_boundaries.py`가 강제).
- `hub/`는 `rosy_core.protocol.schemas` 외 `rosy_core`의 무엇도 import하지 않는다(D-18, D-59).
- Hub는 `COMMAND` envelope, `cmd_vel`/`image`/`twist` 페이로드, `PEER` 참조 소스 scatter를 `ROLE_VIOLATION`으로 거절한다(D-59, D-31).
- `rosy_core`를 이 패키지에서 수정하지 않는다. 로봇 계약에 없는 것은 API Ref 사이클의 finding이지 로컬 patch가 아니다.
