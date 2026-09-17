# 로봇 축구 게임 호스트 설계 — 실기 Pinky 1v1

작성일: 2026-09-17

상태: 방향 합의. 구현·현장 1v1 GO가 아니다. DEVICE/FIELD 검증이 HOLD인 동안 서로 박는 속도의 경기를 성공으로 적지 않는다. 축구는 본선 슬라이스가 아니다(논외). 그래도 패키지 경계는 CORE/Fleet 계약을 지킨다.

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

세 층이다.  squatting하지 않는다.

| 층 | 패키지 | 소유 | 기본 이미지 |
|---|---|---|---|
| 관제 | `rosy_fleet` | 로봇 명단, 토큰, 일괄 stop. 나중에 “매치 시작” 버튼은 여기, `reset()`은 아님 | 관제 PC |
| 경기 | `src/rosy_games` | 규칙, 점수, 정책 프로토콜, soccer 플러그인 | 안 넣음 |
| 학습/시뮬 | `rosy_games.isaac` (나중) | Isaac 월드 + Lab env가 `game.reset`/`step`만 호출 | 워크스테이션 |
| 로봇 | `rosy_core` | `MANUAL`, 워치독, E-stop, 유일한 `cmd_vel` | 로봇 |

물리 필드는 네 번째 덩어리로 바닥에만 있다. 전자가 아니다.

### 3.1 `rosy_games` 안쪽

```text
src/rosy_games/                    # ROS 없음. 선택 ament_python. 논외
  rosy_games/
    field/                         # 구장·골·좌표·호모그래피 숫자. 순수
    game/                          # 심판 상태기계 + Policy 프로토콜. 순수
      soccer.py                    # 첫 게임 플러그인
    policy/                        # HeuristicPolicy 지금, NeuralPolicy 나중
    host/                          # 실기 루프: 관측 → game → RobotClient
    isaac/                         # 예약. 1단계에서 비움
  test/                            # cv2·Isaac 없이 game 시험
```

의존은 한 방향이다.

```text
policy  →  game  →  field
host    →  game, 관측 어댑터, RobotClient
isaac   →  game
```

`game`은 `cv2`도 Isaac도 모른다. 인터페이스는 학습 env와 같다.

- `reset()` → 킥오프
- `observe()` → 공·로봇 pose
- `step(actions)` → 심판 + 다음 상태
- `reward`는 나중에 붙는 필드. 1단계는 비워 둔다

관측 소스만 갈아 끼운다. 천장 카메라, Isaac 그라운드 트루스, 나중 온보드 blob. `host`의 로봇 호출은 `rosy_fleet` `RobotClient`를 재사용하거나 같은 프로토콜만 복제한다. `rosy_games`가 `rosy_core`를 import하지 않는다. 스키마가 필요하면 `rosy_core.protocol.schemas`만 (D-18과 같은 선).

명령 경로:

```text
rosy_games.host  →  RobotClient (명단·토큰·일괄 stop)
                 →  각 CORE  teleop / mode / safety/stop
                 →  Command Manager 만 cmd_vel
```

Fleet 콘솔에 축구 버튼을 나중에 달 수 있다. 버튼을 누르는 쪽은 Fleet, `reset()`을 하는 쪽은 `rosy_games`다.

## 4. 1단계 — 천장 카메라 1v1

만드는 것: `field` + `game.soccer` + `HeuristicPolicy` + `host`(천장 카메라).  
안 만드는 것: Isaac 패키지, 신경망, CORE 변경, D-62 슬라이스.

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

이 문서는 실행 계획이 아니다. 구현을 열려면 별도 execute plan이 필요하고, 최소한 다음이 빠져 있으면 안 된다.

- LOCAL 시험이 있는 `src/rosy_games` 골격 (`field` / `game` / `policy` / `host`)
- `game`이 카메라·Isaac 없이 득점·이격·쌍정지를 돌리는지
- 호스트가 쓰는 CORE 경로가 API Ref §5.5 / §6.1 그대로인지
- 한 대 명령 경로 증거가 Device 검증 계획의 안전 게이트와 모순되지 않는지
- `rosy_games`가 기본 compose·board.yaml 슬라이스에 없는지

준비되면 `superpowers:writing-plans`로 실행 계획을 쪼갠다.
