# 로봇 축구 게임 호스트 설계 — 실기 Pinky 1v1

작성일: 2026-09-17

상태: LOCAL 호스트는 [2026-09-18-rosy-games-local-host.md](2026-09-18-rosy-games-local-host.md)로 닫힘 (`overhead.py`/`homography.py` 없음). 현장 1v1 GO가 아니다. DEVICE/FIELD가 PARKED인 동안 서로 박는 속도의 경기를 성공으로 적지 않는다. 축구는 본선 슬라이스가 아니다(논외). 그래도 패키지 경계는 CORE/Fleet 계약을 지킨다.

관련: D-1, D-2, D-12, D-33, D-38, D-59, D-62, **D-90** · [선택 슬라이스](2026-09-16-optional-runtime-slices-design.md) · [모듈형 미들웨어](2026-09-16-modular-middleware-goal-design.md) · [AI](../concept/11_ROSY_AI_and_Physical_AI.md) · [학습 파이프라인](../concept/12_ROSY_Dataset_and_Learning_Pipeline.md) · [Device 검증](2026-09-13-rosy-os-device-validation-implementation-plan.md) · CORE SRS §8.1 CMD-001 / SAF-001 / SAF-002 / SAF-004 · API Ref §5.5, §6.1

## 1. 방향

Pinky Pro 두 대로 **차체 푸시볼 1v1**을 한다. CORE에 `SOCCER` 모드를 넣지 않는다 (D-90). 경기의 집은 **`rosy_games`** 다. Fleet은 로봇 통로, Isaac은 나중에 붙는 시뮬/학습 어댑터다.

군집이 `NAVIGATION`을 유지한 채 역할만 노출하듯, 1단계 축구는 `MANUAL` + 기존 teleop다. 규칙·공·정책은 `rosy_games`가 맡고, 각 로봇은 지금 CORE 계약만 지킨다.

물리 제약:

- 차동 구동, 축간 0.15 m, 프로필 최대 0.20 m/s / 0.80 rad/s
- 키커 없음. 공은 범퍼로 민다
- 앞 카메라는 320×240, 8 fps, 바닥 전방 장애물용. 공 추적용이 아니다
- 로봇마다 `ROS_DOMAIN_ID = 40+N`, CycloneDDS localhost (D-33). 로봇끼리 ROS로 공을 공유하지 않는다

공은 **단계적으로** 본다. 1단계 천장 카메라 + 호스트, 2단계 온보드 앞 카메라. Isaac 학습 루프는 `game` 모듈이 pytest로 선 뒤에 연다. 1단계가 여러 번 반복되기 전에 온보드를 열지 않는다.

## 2. 하지 않는 것

- `RobotMode.SOCCER` 또는 CORE API에 축구 전용 모드
- 축구 코드의 최종 `cmd_vel` 발행 (D-2, D-38)
- `rosy_core`가 게임 패키지를 import
- 축구를 `rosy_fleet` 안에 넣기 (관제와 규칙·RL·Isaac이 한 패키지가 된다)
- 로봇 간 DDS / peer 소스를 축구 때문에 열기 (D-33, D-21)
- Nav2 골로 공을 쫓기
- Control 센서 정책을 켜서 전방 물체(공)를 일괄 정지
- 1단계 OpenCV를 `rosy-core` 이미지에 다시 넣기 (D-62, D-66)
- D-62 카탈로그에 `games` 슬라이스 등록, Pi 기본 이미지에 패키지 포함
- Isaac이 실기 Command Manager를 대체
- DEVICE/FIELD HOLD를 호스트 pytest로 승격

## 3. 층과 패키지

세 층이다. squatting하지 않는다.

| 층 | 패키지 | 소유 | 기본 이미지 |
|---|---|---|---|
| 관제 | `rosy_fleet` | 로봇 명단, 토큰, 일괄 stop. 나중에 “매치 시작” 버튼은 여기, `reset()`은 아님 | 관제 PC |
| 경기 | `src/rosy_games` | 규칙, 점수, 정책, soccer 플러그인, 실기 호스트 | 안 넣음 |
| 학습/시뮬 | 아직 디렉터리 없음 | Isaac Lab env가 `game.reset`/`step`만 호출. 1단계에서 폴더를 만들지 않는다 | 워크스테이션 |
| 로봇 | `rosy_core` | `MANUAL`, 워치독, E-stop, 유일한 `cmd_vel` | 로봇 |

물리 필드는 바닥에만 있다. 전자가 아니다.

`rosy_games`는 `rosy_fleet`처럼 ROS 없는 ament_python이다. `board.yaml` 슬라이스가 아니고, compose 기본 서비스도 아니고, `rosy_core`를 import하지 않는다. Fleet의 `RobotClient`는 follow/goal/pose 스트림용이라 축구가 재사용하지 않는다. 호스트는 `mode` / `teleop` / `safety/stop`만 아는 얇은 `PlayerClient`를 둔다.

1단계 의존:

```text
policy  →  game  →  field
host    →  game, policy, field, Observer, PlayerClient
```

나중에 `isaac`은 `game`만 호출한다. `field`/`game`/`policy`는 `host`를 모른다.

### 3.1 1단계 파일 트리

이 목록이 구현 계약이다. 여기 없는 파일을 1단계에서 만들지 않는다. `isaac/` 디렉터리도 만들지 않는다.

```text
src/rosy_games/
  package.xml
  setup.py
  setup.cfg
  resource/rosy_games
  config/match.yaml
  rosy_games/
    __init__.py
    cli.py                         # rosy_games match --config ...
    field/
      __init__.py
      types.py                     # Pose2D, Twist, ZERO, Side
      geometry.py                  # Field: in_bounds, in_goal
      homography.py                # 픽셀 네 점 → m
    game/
      __init__.py
      state.py                     # Phase, Observation, MatchState, CommandSet
      protocol.py                  # Game
      soccer.py                    # SoccerGame
      gate.py                      # HOLD/GOAL이면 0, 이격 강제
    policy/
      __init__.py
      protocol.py                  # Policy
      heuristic.py                 # HeuristicPolicy
    host/
      __init__.py
      observer.py                  # Observer
      overhead.py                  # 천장 카메라. 패키지에서 유일한 cv2
      robots.py                    # match.yaml 엔드포인트
      transport.py                 # PlayerClient, HttpPlayerClient
      loop.py                      # MatchHost
  test/
    conftest.py
    fakes.py
    test_boundaries.py
    test_field.py
    test_homography.py
    test_soccer.py
    test_gate.py
    test_heuristic.py
    test_loop.py                   # FakeObserver + FakePlayerClient
```

`overhead.py`는 OpenCV를 import한다. LOCAL 기본 시험은 이 파일을 로드하지 않는다. `test_boundaries.py`가 `field`/`game`/`policy`/`loop.py`/`transport.py`에 `cv2`가 없음을 본다.

### 3.2 타입

`field/types.py`

```text
Pose2D(x, y, yaw)          # m, rad. 공은 yaw=0
Twist(linear, angular)     # m/s, rad/s
ZERO = Twist(0, 0)
Side = POSITIVE_X | NEGATIVE_X
```

`field/geometry.py`

```text
Field(width_m, height_m, goal_width_m, min_spacing_m=0.35)
  in_bounds(x, y) -> bool
  in_goal(x, y, side) -> bool
```

원점은 구장 중앙. +x는 `rosy_01`이 공격하는 골. 호모그래피의 네 모서리는 이 프레임의 네 코너다.

`game/state.py`

```text
Phase = KICKOFF | PLAY | HOLD | GOAL
Observation(t, ball, robots, lost_ball, lost_robots)
  ball: Pose2D | None
  robots: mapping robot_id -> Pose2D
MatchState(phase, score, reason)
CommandSet(twists, estop)
  twists: mapping robot_id -> Twist
  estop: true 이면 host가 양쪽 safety/stop
```

`reward` 필드는 1단계 `MatchState`에 두지 않는다. 학습 env가 나중에 같은 `step` 결과에서 계산한다.

### 3.3 프로토콜과 루프

```text
Game
  reset() -> MatchState
  step(obs: Observation) -> MatchState

Policy
  act(obs, state) -> dict[robot_id, Twist]

Observer
  observe() -> Observation

PlayerClient
  robot_id
  set_manual()
  teleop(linear, angular)
  estop()
```

`MatchHost` 한 틱:

```text
obs = observer.observe()
state = game.step(obs)
twists = policy.act(obs, state)
commands = gate(twists, obs, state)     # HOLD/GOAL/유실 → 0, 이격 강제
if commands.estop:
    양쪽 estop
else:
    각 PlayerClient.teleop(...)
```

`gate`는 정책이 신경망이 되어도 로봇끼리 박지 못하게 하는 마지막 클램프다. 휴리스틱이 이격을 해도 `gate`는 남는다.

`HttpPlayerClient`가 부르는 경로만:

- `POST /api/v1/mode` `{mode: MANUAL}`
- WS `{type: teleop, linear, angular}` (또는 REST `POST /api/v1/teleop`)
- `POST /api/v1/safety/stop`

follow / navigation / swarm 경로는 없다.

### 3.4 import 경계

`test_boundaries.py`가 AST로 강제한다. fleet `test_boundaries.py`와 같은 방식.

| 디렉터리 | 허용 | 금지 |
|---|---|---|
| `field/` | stdlib, 자기 패키지 | `cv2`, `httpx`, `websockets`, `rclpy`, `rosy_games.host`, `rosy_games.policy`, `rosy_core`, `rosy_fleet` |
| `game/` | stdlib, `rosy_games.field` | `cv2`, `httpx`, `websockets`, `rclpy`, `rosy_games.host`, `rosy_core`, `rosy_fleet` |
| `policy/` | stdlib, `rosy_games.field`, `rosy_games.game` | `cv2`, `httpx`, `websockets`, `rclpy`, `rosy_games.host`, `rosy_core`, `rosy_fleet` |
| `host/` except `overhead.py` | `httpx`, `websockets`, PyYAML, 위 세 모듈 | `cv2`, `rclpy`, `rosy_core`, `rosy_fleet`, Isaac |
| `host/overhead.py` | `cv2` + 위 | `rclpy`, `rosy_core.command`, Isaac |

패키지 전체: `rclpy` 없음. `rosy_core.*` 없음. `rosy_fleet.*` 없음. Fleet이 나중에 매치를 켤 때는 **Fleet → games** 한 방향이다.

### 3.5 `config/match.yaml`

```yaml
field:
  width_m: 2.0
  height_m: 1.4
  goal_width_m: 0.35
  min_spacing_m: 0.35
robots:
  - id: rosy_01
    url: http://rosy-01.local:8080
    token: ""
    aruco_id: 1
    attacks: positive_x
  - id: rosy_02
    url: http://rosy-02.local:8080
    token: ""
    aruco_id: 2
    attacks: negative_x
ball:
  hsv_low: [5, 120, 80]
  hsv_high: [25, 255, 255]
limits:
  linear: 0.08
  angular: 0.40
camera:
  index: 0
watchdog:
  lost_hold_s: 0.5
```

토큰은 커밋하지 않는다. 로컬 오버라이드(`match.local.yaml`, gitignore)가 실기 URL을 덮는다.

### 3.6 패키지 메타

- `package.xml` ament_python. `exec_depend`: `python3-httpx`, `python3-websockets`, `python3-yaml`. OpenCV는 `host/overhead.py`만 쓰므로 **exec_depend로 올리지 않는다** — 노트북에 있으면 실기 호스트가 되고, 없으면 LOCAL 시험은 그대로 통과한다.
- `console_scripts`: `rosy_games=rosy_games.cli:main`
- `deploy/robot` compose, `board.yaml` available slices, CORE 이미지 COPY에 이 패키지를 추가하지 않는다.

Fleet 콘솔에 축구 버튼을 나중에 달 수 있다. 버튼을 누르는 쪽은 Fleet, `Game.reset()`을 하는 쪽은 `rosy_games`다.

## 4. 1단계 — 천장 카메라 1v1

만드는 것: §3.1 트리 전부.  
안 만드는 것: `isaac/` 디렉터리, `NeuralPolicy`, CORE 변경, D-62 슬라이스, `rosy_fleet` import.

### 4.1 필드

- 구장 약 1.5–2.0 m × 1.0–1.5 m
- 네 모서리 테이프 + ArUco (호모그래피)
- 골 박스 폭 30–40 cm, 양 끝
- 공: 주황/형광 폼, 지름 6–8 cm
- 로봇 윗면 ArUco: id 1 = `rosy_01`, id 2 = `rosy_02`
- 웹캠 하나(삼각대 또는 천장)가 구장 전체를 담는다

호스트는 모서리 마커로 호모그래피를 한 번 잡고, 이후 프레임의 공·로봇 픽셀을 필드 좌표(m)로 바꾼다. OpenCV는 `host` 관측 어댑터에만 산다.

### 4.2 명령 경로

기존 API만 쓴다.

```text
천장 카메라
  → host 관측 어댑터: 공·로봇 pose
  → game.soccer 심판 (킥오프 / 인플레이 / 득점 / 리셋)
  → HeuristicPolicy → (v, ω) 두 벌
  → 각 CORE
       POST /api/v1/mode {mode: MANUAL}
       WS teleop {type: teleop, linear, angular}
  → Command Manager (유일한 cmd_vel, 50 Hz)
  → bringup 모터
```

REST `POST /api/v1/teleop`도 동일 워치독(SAF-002, 500 ms)을 탄다. 호스트 루프는 약 20 Hz라서 워치독보다 짧다. 끊기면 로봇은 선다.

첫 접촉 속도는 프로필 최대가 아니다. `PUT /api/v1/safety/limits`로 0.08–0.10 m/s 근처. 0.20 m/s는 저속 1v1이 반복된 뒤다.

### 4.3 플레이어 정책 (1단계 최소)

인플레이에서 각 로봇은:

1. 공 − 자기 위치의 각도로 회전
2. 각도가 작으면 전진
3. 자기 골이 아니라 상대 골 쪽으로 살짝 치우침 (약한 바이어스)
4. 상대 로봇과 중심 거리 < 약 0.35 m 이면 접근 성분을 제거하거나 둘 다 감속

킥오프는 사람이 공을 중앙에 두고, 호스트가 두 마커와 공을 본 뒤에만 인플레이로 넘긴다. 득점은 공이 골 폴리곤에 들어가면 양쪽 0, 점수 +1, 킥오프 안내.

Nav2를 쓰지 않는다. 공을 밀어야 하므로 MANUAL이다.

## 5. 안전과 실패

CORE 안전을 게임 때문에 끄지 않는다. 호스트가 죽거나 헷갈리면 **두 대 모두 선다.**

이미 있는 것:

- 텔레옵 워치독 500 ms → 속도 0
- `POST /api/v1/safety/stop` (Viewer↑). 스페이스, 창 닫기, 예외는 양쪽 호출
- E-stop 중 teleop는 `EMERGENCY_ACTIVE`. 해제는 Admin `release`
- `cmd_vel` publisher는 CORE 하나 (D-2). 호스트는 HTTP/WS만

호스트가 추가로 맡는 것:

| 상황 | 동작 |
|---|---|
| 공 또는 로봇 마커 1프레임 유실 | 그 사이클 속도 0. 추측으로 달리지 않음 |
| 0.5 s 이상 유실 | 양쪽 HOLD. 다시 보이면 킥오프부터 |
| 한쪽 CORE 무응답 | 둘 다 stop. 한 대만 뛰는 경기 없음 |
| 두 대 중심 거리 < 발자국+여유 (약 0.35 m) | 접근 성분 제거 또는 둘 다 감속 |
| 공이 필드 밖 | HOLD, 사람이 리셋 |
| 호스트 프로세스 종료 | 워치독이 나머지를 처리 |

라이다 근접 정지를 공에도 걸면 공을 못 민다. 1단계는 MANUAL + 호스트 이격만 쓴다. 운영 프로필의 Control 센서 정책(`safety.control_policy_required`, 기본 false)을 축구 때문에 켜지 않는다. 경기는 바닥에서 한다. 테이블 낙하를 축구 규칙으로 다루지 않는다.

현장 게이트: 그 기기의 정지·워치독·단일 publisher가 확인되기 전에는 두 대가 서로를 향해 달리는 속도를 내지 않는다. 첫 세션은 한 대 공 밀기 → 두 대 저속 → 그다음 속도. 사람이 호스트 앞에서 스페이스를 쥔다.

학습된 정책도 이 게이트를 우회하지 않는다. 개념 11: AI Policy → desired action → ROSY Runtime 검증 → 액추에이터. NeuralPolicy의 `(v, ω)`도 teleop/CMD-001로만 들어간다.

## 6. 2단계 — 온보드 시야 (예약)

1단계 현장 4항(두 대 + 공, 저속)이 여러 번 반복된 뒤에만 연다.

온보드는 선택 슬라이스다. CORE는 import하지 않고 토픽·CMD-001 후보만 본다 (D-62). 앞 카메라 blob으로 공이 보이면 로컬 추적, 시야 밖이면 호스트 명령을 쓴다. 심판(득점, 킥오프, 양쪽 stop)은 계속 `rosy_games`다.

온보드가 최종 `cmd_vel`을 내지 않는다. v2 군집이 예약한 CMD-001 로컬 소스와 같은 구멍이다. 구현 세부는 1단계 증거 다음 문서다.

## 7. Isaac과 RL (예약)

Isaac은 심판 UI이자 학습장이다. 실기 Command Manager가 아니다.

- Gazebo(`rosy_gz_sim`)는 CORE ROS-SIM용으로 남긴다. 축구 체육관으로 승격하지 않는다
- Isaac Lab env는 `rosy_games.game`만 호출한다. 규칙을 Isaac 스크립트에 복제하지 않는다
- 에피소드 기록은 개념 12 파이프라인(Record → Train → Deploy)에 맞출 수 있다. 1단계 범위가 아니다
- Isaac 없는 실기 1v1이 `game`만으로 성립해야 한다. 학습이 실기의 전제가 아니다

## 8. 시험

호스트 pytest가 현장 1v1을 대신하지 않는다.

**LOCAL (Windows, ROS 없음)** — 1단계 코드의 기본 합격선.

- 네 모서리 → 호모그래피 → 필드 좌표 (`field`)
- `game.soccer`: 골 폴리곤 → 득점, 양쪽 명령 0
- `HeuristicPolicy`: 공 방향 회전·전진, 0.35 m 이내 접근 성분 제거
- 마커/공 유실, 한쪽 클라이언트 실패 → 둘 다 0
- 속도는 항상 limits 안
- `game` / `policy` / `field` 가 `cv2`·Isaac·`rclpy`를 import하지 않음 (경계 시험)

**명령 경로 (한 대).** 호스트 20 Hz teleop, 프로세스 종료 후 500 ms 안 속도 0, 스페이스 → `safety/stop`, `cmd_vel` publisher 1. 한 대로 공을 저속 골인까지 밀면 비전+정책+텔레옵이 맞다.

**ROS-SIM (선택).** `gz_multi`에 공 모델. 천장 카메라 대신 시뮬 좌표를 `game`에 넣는다. 지금 다중 로봇 시뮬 벤치가 HOLD면 LOCAL을 막지 않는다. Isaac 시험은 §7이 열린 뒤다.

**현장 순서 (건너뛰지 않음).**

1. 카메라만: 구장·공·로봇이 안정적으로 보이는지. 모터 없음
2. 한 대, 0.08 m/s, 공 밀기 → 골 → HOLD
3. 두 대, 공 없이, 가까이 가면 감속
4. 두 대 + 공, 같은 저속 1v1
5. 득점 후 킥오프 리셋이 사람 손으로 반복 가능한지

2단계와 Isaac은 4가 반복된 뒤에만. DEVICE/FIELD HOLD 동안 서로 박는 속도의 경기를 성공으로 적지 않는다.

## 9. 구현 게이트

[2026-09-18-rosy-games-local-host.md](2026-09-18-rosy-games-local-host.md)가 LOCAL 호스트를 닫았다. `host/overhead.py`와 `field/homography.py`는 만들지 않았다. 천장 카메라 실측은 다음 계획이다.

LOCAL GO:

```
python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q
```

카메라 없이 통과. DEVICE/FIELD는 PARKED.

닫힌 항목:

- §3.1 트리에서 `overhead.py`·`homography.py`·`test_homography.py`만 다음 계획으로 미룸. `isaac/` 없음
- `test_games_boundaries.py`가 §3.4를 통과 (host 중 `overhead.py`만 cv2 허용; 지금은 그 파일이 없음. `loop.py`/`transport.py`는 cv2 없음)
- soccer / gate / heuristic / loop가 카메라 없이 득점·이격·쌍정지
- `HttpPlayerClient`가 API Ref §5.5 / §6.1의 mode·teleop·stop만 부름
- `rosy_games`가 기본 compose·board.yaml 슬라이스에 없음

아직 열린 항목:

- 한 대 명령 경로 증거가 Device 검증 계획의 안전 게이트와 모순되지 않는지 (DEVICE)
- 현장 1v1 (FIELD)
