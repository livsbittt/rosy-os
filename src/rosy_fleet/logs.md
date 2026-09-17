# rosy_fleet logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [사이트 패브릭 계획](../../docs/plans/2026-09-14-site-middleware-role-fabric.md), [군집 대형 슬라이스 결과](../../docs/plans/2026-09-08-swarm-formation-slice-results.md)와 `git log -- src/rosy_fleet`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the rosy_fleet harness record
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python -m pytest src/rosy_fleet/test -q` 216 passed, 5 skipped (2026-09-15 Windows, 미커밋 WIP 포함 작업 트리); `python -m pytest src/rosy_fleet/test/test_boundaries.py -q` 6 passed
- gate 변화: 없음. SOURCE/LOCAL GO, ROS-SIM/ARTIFACT/DEVICE N/A(이 패키지에 ROS import 없음, 사이트 PC 전용이라 로봇 이미지·Pi 설치 대상 아님), FIELD PARKED(D-35 sim bench 실측 대기)를 스냅샷으로 기록
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-16 · uncommitted · docs(harness): hold the unrun formation sim bench
- 변경: 리뷰 반영. ROS-SIM을 HOLD로, `cmd`를 `python3`으로
- 증거: `python -m pytest src/rosy_fleet/test -q` 216 passed, 5 skipped; `test_boundaries.py` 6 passed (2026-09-16 재실행). sim bench 자체는 미실행
- gate 변화: ROS-SIM N/A→HOLD (패키지는 ROS를 import하지 않지만 Task 14 gz_multi sim bench가 이 모듈의 relay·HOLD 지연 증거다)
- 결정: 없음
- 교훈: 없음

## 2026-09-16 · uncommitted · docs(harness): park the site-PC deployment gates
- 변경: 2차 리뷰 반영. ARTIFACT/DEVICE를 PARKED로. 로봇 이미지 대상은 아니지만 SiteHub(`rosy_fleet hub --listen`)는 사이트 PC 산출물로 배포될 예정이며 Phase 4 대기다
- 증거: 미실행 — 기록 정정만
- gate 변화: ARTIFACT N/A→PARKED, DEVICE N/A→PARKED (첫 항목의 "ROS import 없음" 근거는 배포 적용 여부와 무관해 철회)
- 결정: 없음
- 교훈: 없음

## 2026-09-17 · uncommitted · feat(server): Fleet 서버 v1 — N대 관제 UI와 로봇별 미션 하달
- 변경: `rosy_fleet/server/` 신규(`console.py`, `app.py`, `web/`), `cli.py`에 `console` 서브커맨드, `swarm/transport.py`에 `map()` 추가, `package.xml`/`setup.py`에 fastapi·uvicorn과 UI 자산, 시험 2건 신규(`test_server_console.py`, `test_server_app.py`)
- 증거: `python -m pytest src/rosy_fleet/test -q` 235 passed, 5 skipped (2026-09-17 Windows); `python -m flake8 src/rosy_fleet --max-line-length=120` 신규 파일 무경고. 실환경: WSL ROS 2 Jazzy + Gazebo에서 `gz_multi robots:=2 mode:=nav core:=true` 위에 `rosy_fleet console`을 붙여 두 대를 한 화면에서 보고, 지도 클릭으로 `rosy_01 → (1.21, 0.86)`, `rosy_02 → (1.16, -0.64)` 하달 → 둘 다 `ARRIVED`, AMCL pose가 Gazebo 정답과 0.1 m 이내
- gate 변화: 없음. ROS-SIM은 HOLD 유지 — 이번에 실측한 것은 미션 경로이고, 이 gate의 blocker인 Task 14 대형 릴레이(`relay_tx_hz`/`slot_err_m`/HOLD latency)는 여전히 미실행이다
- 결정: 없음. site-fabric 설계 §2 역할표(사이트 오케스트레이터 + 관제 UI)와 D-12(미션은 Fleet 전용)를 그대로 구현했고 새 ADR은 필요하지 않다
- 교훈: 로봇 상태 스냅샷에 목표가 없다는 것이 D-12의 결과다. 목표를 화면에 그리려면 Fleet이 기억해야 하며, 로봇에게 되물으면 안 된다. 거절된 목표는 기억하지 않는다 — 남기면 가지도 않을 곳으로 간다고 읽힌다

## 2026-09-17 · uncommitted · feat(server): 좁은 통로 교행을 Fleet 이 정리한다
- 변경: `server/traffic.py`(경로 충돌 판정, 순수 기하), `FleetConsole` 에 경로 점유·미션 대기열, `swarm/transport.py` 에 `navigation_path()`, 관제 UI 에 대기 표시, 시험 `test_server_traffic.py` 13건
- 증거: `python -m pytest src/rosy_fleet/test -q` 249 passed, 5 skipped (2026-09-17 Windows). 실환경: 미로에서 두 대에 서로의 자리로 가는 미션을 내렸을 때, 코어 이벤트가 `nav.started`(13:41:06.989) → `nav.canceled by api:operator`(13:41:07.056, 67 ms) → `nav.started`(13:43:58.668, 2분 51초 뒤 자동 재하달) → `nav.completed`(13:46:37) 를 남겼고 두 대 다 목표에 도착했다. 같은 시나리오가 직전까지는 0.10 m 간격으로 둘 다 실패했다
- gate 변화: 없음(커밋 뒤 재실행으로 판정)
- 결정: 없음. D-12(미션은 Fleet 전용)의 범위 안이라 새 ADR 이 필요하지 않다
- 교훈: 교행은 로봇이 풀 수 없는 문제다. 로봇의 코스트맵은 자기 주변만 보므로, 상대를 본 순간에는 이미 비켜설 자리가 없다. 두 경로를 동시에 쥔 쪽만 순서를 정할 수 있고 그쪽이 Fleet 이다. 그리고 경로는 목표를 받은 뒤에야 생기므로, 판정은 "내려보내고 읽고 필요하면 취소" 순서가 된다

## 2026-09-17 · uncommitted · feat(server): 관제 화면에서 대형을 열고 닫는다
- 변경: `FleetConsole` 에 `formation_start/reform/resume/stop/status`(기존 `FormationSession` 을 그대로 씀), `/api/fleet/formation*` 경로 5개, 관제 UI 대형 패널(리더·모양·간격 + 무장/변경/재개/해제 + 릴레이 Hz·슬롯·HOLD 이유), 시험 `test_server_formation.py` 12건. 앞선 라운드에서 덮인 대기-상태 표시도 새 UI 위에 복구
- 증거: `python -m pytest src/rosy_fleet/test -q` 270 passed, 5 skipped. 실환경(rosy_swarm_bench, 2대): 무장 → `RUNNING`/`rosy_02` 슬롯 0.6 m, 리더에 목표를 주자 리더가 (-0.07,0.40)→(0.21,1.57) 주행하고 팔로워가 (-0.11,0.57)→(0.17,1.62) 로 추종, 릴레이 9.93~10.01 Hz 유지. 리더 항법이 실패하자 FOR-004 정책이 `HOLDING` + 릴레이 pause 로 떨어지고 이유 `['nav.failed','rosy_01']` 를 화면에 남겼다. V 0.7 m 로 재무장한 화면 캡처도 확인
- gate 변화: 없음(커밋 뒤 재실행으로 판정). ROS-SIM 의 Task 14 blocker 중 relay_tx_hz(9.93~10.07)·leader_rx_hz(9.45~10.07)·slot_err_m(최소 0.04, 수렴 0.59)는 실측됐고, HOLD 지연 실측만 남았다
- 결정: 없음
- 교훈: 대형에서 리더와 팔로워는 반대 규칙을 받는다. 처음에 둘 다 개별 미션을 막았더니 대형이 무장만 되고 아무 데도 가지 못했다 — 리더는 몰아야 하는 쪽이다

## 2026-09-17 · uncommitted · test(swarm): Task 14 sim bench 를 끝까지 돌려 HOLD 지연을 실측
- 변경: 기록만. `swarm_bench.py --scenario follow` 와 `--scenario hold` 를 실환경에서 실행
- 증거: WSL ROS 2 Jazzy + Gazebo, `rosy_swarm_bench.world` 2대. follow: `relay_tx_hz` 9.93~10.07, `leader_rx_hz` 9.45~10.07, `slot_err_m` 최소 0.04 / 마지막 10 표본 최대 0.59. hold: t=30.7 에 릴레이 pause 주입 → t=31.8 에 팔로워 `holding` — **1.07 s**, `stream_timeout_ms` 1000 과 일치한다
- gate 변화: ROS-SIM HOLD→GO. blocker 가 "Task 14 미실행" 이었고 이번에 실행했다
- 결정: 없음. D-35 등재 여부는 실측이 나왔으니 이제 판단할 수 있다
- 교훈: HOLD 는 로봇 쪽에서 스트림 타임아웃 한 번으로 성립한다 — 세션이 HOLDING 으로 떨어지는 것과는 다른 경로다. 릴레이만 끊어도 팔로워는 1 s 안에 선다
