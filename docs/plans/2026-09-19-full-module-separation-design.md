# 완전 모듈 분리 설계 (D-126)

작성일: 2026-09-19 / 상태: Proposed

관련: D-1, D-2, D-38, D-62, D-63, D-64, D-125 · [D-64 실행 계획](2026-09-16-core-control-import-boundary.md) · [미들웨어 목표](2026-09-16-modular-middleware-goal-design.md)
(실측 근거: 2026-09-19 작업 트리 결합도 평가 — `package.xml` 19개, 비테스트 import sweep, `cmd_vel` 발행/구독 grep.)

## 목표

D-125가 `core`를 5개 도메인 라이브러리로 나눈 뒤에도 남은 패키지 간 이음새 5곳을 닫고,
"CORE는 슬라이스 코드를 import하지 않고 최종 `cmd_vel`만 낸다"를 기계 검사 가능한 상태로 만든다.
런타임은 그대로 단일 프로세스(D-1)이며, 새로 쪼개는 ROS 패키지는 없다.

## 닫을 이음새 5곳 (2026-09-19 작업 트리 실측)

| # | 이음새 | 실측 | 목표 |
|---|---|---|---|
| S1 | `core → control` 미선언 import | `src/core/core/core/bridge/control_sensor_adapter.py:118,140,213`이 `control.*` 3모듈 import. `src/core/core/package.xml`에는 `control` 없음 | 어댑터가 증거 토픽 구독으로 전환, `control` import 0건. D-63 "그다음 단계에서 그 파일도 토픽 경계로"의 이행 |
| S2 | `control`의 최종 `cmd_vel` 구독 잔재 | `src/apps/control/control/web_node.py:431`, `control/wander/node.py:36`이 `'cmd_vel'` 구독 | `cmd_vel_raw`/세션 계열로 개명·삭제. 운영 launch 미포함 계약 고정 |
| S3 | `fleet` 선언이 실제보다 넓음 | `package.xml`은 `exec_depend: core`이나 비테스트 생산 코드는 `core_common.protocol.schemas` 5파일만 참조 (`hub/hub.py`, `hub/registry.py`, `swarm/arming.py`, `swarm/session.py`, `swarm/transport.py`). `core_features.swarm` 참조는 `test_geometry.py`뿐 | `exec_depend`를 `core_common`으로 축소, 시험용은 `test_depend: core_features`로 명시 |
| S4 | `gz_sim → fleet` 직접 import | `src/sim/gz_sim/scripts/swarm_bench.py`가 `fleet.formation.geometry`, `fleet.swarm.{robots,session,transport}` 직접 참조. 벤치의 목적 자체가 fleet 세션을 시뮬에서 돌리는 것이라 CLI 경유 재작성은 이득 없이 깨지기만 한다. `package.xml`에 선언으로 고정하고, 같은 파일의 미선언 `navigation` import도 함께 선언 | `exec_depend: fleet`(기존 유지) + `exec_depend: navigation`(추가). 시뮬→함대/내비는 하향 의존이라 허용 |
| S5 | `core_api_web` fan-out | `api/v1/*` 12개 모듈이 `core_features` 하위 7개 영역(`command.arbitration`, `navigation.manager`, `docking.database`, `diagnostics.collector`, `maps`, `swarm`, `waypoints`) 직접 참조 | `api/deps.py` 파사드 뒤로 통합. 라우터는 `deps`만 본다 |

비고: `test/test_runtime_slices.py`의 D-64 가드는 구 경로(`src/rosy_core`)를 가리켜 신 구조에서 검사하지 않는다.
가드 재건(S0)이 모든 작업보다 먼저다. 가드 없는 분리는 증명되지 않는다.

## 끝 상태 가드 (전부 기계 검사)

1. `src/core/**` 생산 코드에 `control`, `fleet`, `bringup`, `navigation`, `emotion`, `omx_adapter`, `games` import 0건 (AST 검사).
2. `src/apps/control/**` 생산 코드에 최종 토픽 문자열 `'cmd_vel'`(정확히 일치, 따옴표 포함) 0건. `cmd_vel_raw` 등은 허용. 유일한 예외는 핀된 레거시 비교 그래프 발행자 선언 1곳(`control/safety/node.py:88`, `test_os_control_graph.py`가 `safety_node`를 레거시 최종 발행자로 고정).
3. 각 `package.xml`의 의존 집합이 코드 import 집합을 덮는다 (선언 ⊇ 실제). 미선언 import 0건.
4. 최종 `cmd_vel` 발행자는 `src/core/core/core/bridge/ros_bridge.py` 1곳 (D-2).
5. `fleet` 생산 코드는 `core_common`만 참조. `core_features` 참조는 시험 한정.

## 순서

S0 가드 재건 → S2 → S3 → S4 → S6(문서·ADR 수용) → S1 → S5 → 회귀.
S1(토픽 경계)이 가장 크므로 S2~S4의 작은 이음새를 먼저 닫고, S1·S5는 동작 불변 리팩토링으로 나눈다.

## 이 설계가 아닌 것

- `core_features` 추가 분할 (safety/power/docking/navigation…): B1~B3 미충족. 한 requirement family씩 이미 소유 중이며 더 나누면 이음새만 늘어난다.
- 멀티 프로세스/마이크로서비스화: D-125에서 보류한 Option B. 다시 열지 않는다.
- `mapping/` 분리, nav overlay, vision/omx 오버레이: D-63 후속 4~6단계의 기존 계획이 주인이다.
- 이미지·compose 변경: 배포층 fan-out은 현재 느슨해서 적정. 건드리지 않는다.
