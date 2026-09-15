# 항법과 군집 추종 분리 설계

작성일: 2026-09-15

상태: D-60 Accepted(설계 결정). 코드 이동은 [실행 계획](2026-09-15-navigation-swarm-split.md).

관련: [ADR Log](../reference/ROSY%20ADR%20Log.md) D-2, D-12, D-20, D-31, D-38, D-59, D-60 · [module split](2026-09-06-module-split-criteria.md) · [사이트 패브릭](2026-09-14-site-middleware-role-fabric-design.md)

## 1. 왜 나누는가

`navigation/`이 NAV와 SWM을 같이 주장한다. 추종 상태머신은 `swarm.py`에 있지만 패키지 목적, import 경로, 항법 오류 문구가 군집을 알고 있다. 항법 실행기가 대형·참조 스트림·팔로워 세션을 생각하면, 목표 한 건을 보내는 일 외에 신경 쓸 것이 생긴다.

이 분리는 새 기능이 아니다. 이미 있는 두 역할을 각자 집에 두는 것이다. 매핑 세션(C7)과 사이트 Hub listen은 이번 범위가 아니다.

## 2. 역할

| 역할 | 산다 | 한다 | 모른다 |
|---|---|---|---|
| **항법 실행** | `rosy_core.navigation` | 단발 목표, moving-goal 세션, 취소, stuck, (당분간) 매핑 세션 | 리더/팔로워, pose 소켓, 대형 기하, 참조 소스 |
| **추종 실행** | `rosy_core.swarm` | 참조 pose → 오프셋 목표, 2 Hz 상한, 단절 HOLD, e-stop/도킹 양보 | Nav2 액션 클라이언트, DDS, Fleet 릴레이, 슬롯 배정 |
| **조립** | `services.py` | `SwarmManager(nav=...)` 주입, `session_closed_listener` 연결 | 추종 공식, Nav2 핸들 |
| **HTTP/WS** | `api/v1/swarm.py`, `api/ws.py` | 계약 envelope을 `svc.swarm`에 전달 | `navigation.swarm` 경로 |

의존 방향은 한쪽만이다. **swarm → navigation** (목표를 넣는다). **navigation → swarm 금지.**

사이트 오케스트레이터(`rosy_fleet`)는 로봇 `SwarmManager`를 import하지 않는다. 로봇 계약만 쓴다(D-31, D-59).

## 3. 패키지 형태 (split 기준)

B1: SWM은 navigation이 주장하던 가문이고, 옮긴 뒤 navigation은 NAV만 주장한다.  
B2: 두 파일, 두 역할 — `poses.py`(표본·오프셋)와 `manager.py`(세션).  
B3: `api/`, `services.py`, 시험, `rosy_fleet` 기하 대조가 소비한다.

```text
rosy_core/swarm/
  AGENTS.md
  __init__.py          # 공개: ReferencePose, follow_goal, SwarmManager, SwarmError
  poses.py             # ReferencePose, follow_goal → NavGoalSpec
  manager.py           # SwarmManager. navigation.manager 를 실행기로만 호출
```

`navigation/swarm.py`는 삭제한다. 이중 경로는 두지 않는다. 모든 import를 `rosy_core.swarm`으로 바꾼다.

`follow_goal`이 `NavGoalSpec`을 만드는 것은 허용된 의존이다. 추종이 항법의 목표 타입으로 말하는 것이고, 항법이 추종 타입을 아는 것이 아니다.

## 4. 항법이 군집 이름을 버리는 곳

`NavigationManager`는 moving-goal 세션을 일반 기능으로 둔다. 오류 문구와 주석에서 `swarm follow`를 빼고 `moving-goal session`이라고 부른다. `moving_goal(..., source=)`의 기본값은 호출자가 넘긴다. 항법 모듈이 `"swarm"`을 기본으로 넣지 않는다.

`open_moving_session` / `session_closed_listener` / `moving_goal`은 그대로다. 추종이 세션 임자인 것은 조립(`services.py`)이 리스너를 붙이는 방식으로만 드러난다.

`command/arbitration.py`의 `"swarm": Priority.NAVIGATION`은 명령 소스 이름이다. 항법 패키지가 아니다. 우선순위 표는 유지한다.

## 5. 하지 않는 것

- `mapping/` 패키지. NavigationManager의 매핑 세션 C7은 그대로 둔다.
- `rosy_fleet` 기하를 로봇 쪽으로 옮기기. 로봇 `follow_goal`은 한 대의 오프셋이고, Fleet `slots()`는 대형이다.
- pose WebSocket을 swarm 패키지로 옮기기. 소켓은 API 층이다. SwarmManager는 소스를 묻지 않는다(SWM-007).
- 동작 변경. 2 Hz, HOLD, 맵 불일치, 도킹 양보, e-stop 해제는 그대로다.
- 새 ROS 패키지.

## 6. 검증

- `rosy_core.navigation` 트리에 `swarm` import가 없다 (시험이 파일 텍스트를 본다).
- `rosy_core.swarm.manager`는 `rosy_core.navigation.manager`의 `NavGoalSpec` / `moving_goal` / `cancel`만 쓴다.
- 기존 `test_swarm.py`, `test_swarm_api.py`, `test_swarm_stream.py`, `test_swarm_integration.py`가 import 경로만 바꿔 통과한다.
- `rosy_fleet/test/test_geometry.py`의 `follow_goal` 대조는 새 경로를 쓴다.
- 사이트 Hub·FleetAgent·compose는 건드리지 않는다.
