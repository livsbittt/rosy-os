# 군집 대형 슬라이스 설계 — Fleet 없는 N대 추종

| 항목 | 값 |
|------|-----|
| Document | ROSY Swarm Formation Slice Design |
| Author | TBD |
| Date | 2026-09-08 |
| Status | Draft |
| Proposed ADR | D-35 후보: 대형 전체 HOLD 는 새 엔드포인트가 아니라 참조 스트림을 끊는 것으로 만든다 (§6.4) |
| Related | D-18, D-20, D-21, D-31; CORE SRS SWM-001~007; FLEET SRS FOR-001~004, TRF-001; API Ref §5.5, §6.2, §7.8; 계획서 P0-6, P5-1~P5-4 |

## Overview

로봇 쪽 추종 프리미티브는 완성돼 있다. `SwarmManager` 가 moving goal, 세대 관리,
SWM-004 HOLD, `map_id` 일치 검사, `max_speed` 클리핑, e-stop·도킹·stuck 양보를
다 하고 테스트 105개가 덮는다. 리더 pose 소켓(`/ws/swarm/pose`)과 팔로워
참조 소켓(`/ws/swarm/reference`)도 서빙된다(D-31).

그런데 **여러 대를 하나로 묶는 쪽은 비어 있다.** 리더 출력을 팔로워 입력에
실제로 잇는 코드가 없고, 대형 기하(FOR-001)와 슬롯 배정(FOR-002)이 없고, 한 대가
멈추면 나머지를 세우는 감시(FOR-004)가 없다. Fleet 서버는 없고 `FleetAgent` 는
스텁이다. 그래서 `capabilities.hardware.yaml` 은 `swarm.follow/lead: false` 로
잠겨 있다.

이 문서는 그 빈 자리를 **Fleet 서버 없이** 채우는 첫 슬라이스를 설계한다.
산출물은 `src/rosy_fleet/` 씨앗 패키지(대형 기하·배정·릴레이·세션), `gz_multi` 의
로봇별 `rosy_core` 기동, 그리고 시뮬 3대 계측 스크립트다. 실물 수락과 capability
점등은 다음 슬라이스다.

## Background & Motivation

### 운영 환경이 데이터 경로를 정한다

| 층 | 사실 | 결과 |
|---|---|---|
| 호스트 | Raspberry Pi 5, Raspberry Pi OS Lite 64-bit, systemd, NetworkManager | 로봇 간 통신은 WLAN 위 HTTP/WS 만 가능 |
| ROS | Jazzy 를 Docker 3컨테이너로 격리, `rosy-core` 가 FastAPI+rclpy 단일 프로세스 | 군집 로직은 `rosy-core` 안에 산다 |
| DDS | CycloneDDS localhost-only, 로봇마다 `ROS_DOMAIN_ID = 40+N`, 네임스페이스 `rosy_NN` (D-6, D-33) | **로봇끼리 ROS 로는 보이지 않는다.** 설계 의도다 |
| 네트워크 | 기본 `SITE_STA`, 같은 사업장 WLAN (D-26) | 로봇 API 소켓을 서로 직접 물릴 수 있다 |
| Fleet | 서버 없음, 아웃바운드 hold | 오케스트레이터 자리가 비어 있다 |

시뮬은 다르다. `gz_multi` 는 Gazebo 하나 위에 N대를 띄우므로 로봇들이 DDS 도메인
하나를 공유하고 네임스페이스로만 갈린다. 릴레이와 세션은 HTTP/WS 만 쓰므로 두
환경에서 같은 코드가 돌지만, 이 차이는 계측을 읽을 때 기억해야 한다 — 시뮬에서
보이지 않는 DDS 디스커버리 비용이 실물에는 없고, 시뮬에 없는 WLAN 지연이 실물에는
있다.

### 군집에 필요한 층과 지금 있는 것

| # | 층 | 상태 |
|---|---|---|
| a | 공통 좌표계 (같은 맵 + 로봇별 AMCL, `map_id` 일치 검사) | 있음 — `SwarmManager` 의 `map_mismatch` HOLD |
| b | 참조 스트림과 단절 정책 (≥10 Hz, 1 s 타임아웃 HOLD) | 있음 — SWM-003/004, D-31 소켓 |
| c | 추종 제어기 (moving goal ≤2 Hz, 세대, `max_speed`, 양보) | 있음 — `navigation/swarm.py` |
| d | 대형 기하 LINE/COLUMN/GRID/V/CIRCLE/FOLLOW | **없음** — 이 슬라이스 |
| e | 슬롯 배정 (거리 그리디, 교체 가능 인터페이스) | **없음** — 이 슬라이스 |
| f | 로봇 간 충돌 회피 | Nav2 local costmap 이 LiDAR 로 남을 본다 (TRF-001). 기하 하한으로 보강 (§4.3) |
| g | 대형 수준 안전 (1대 이상 → 전체 HOLD) | **없음** — 이 슬라이스 |
| h | 릴레이·오케스트레이터 | **없음** — 이 슬라이스 |
| i | 시뮬 다중 검증 | 부분 — `gz_multi` 는 Nav2 까지만 띄우고 `rosy_core` 는 안 띄운다 |

핵심 관찰: 팔로워는 이미 **리더 heading 기준 `(distance, lateral)` 오프셋**을
받는다(`follow_goal`). 모든 정적 대형은 슬롯별 오프셋 집합으로 환원되므로, 대형
기하는 로봇 계약을 한 글자도 바꾸지 않고 순수 함수 하나로 끝난다.

### 대안과 기각 이유

- **Fleet 서버 본체(Phase 4)를 먼저 세운다.** 정석이지만 군집 검증이 수 주 뒤로
  밀리고, 이미 있는 추종 코드가 검증되지 않은 채 남는다. 여기서 만드는 모듈은
  `rosy_fleet` 안에 두므로 Phase 4 가 들어와도 옮길 일이 없다.
- **대형 계산을 로봇에 두고 리더가 대형 스펙을 방송한다.** Fleet 없이도 되지만
  "오케스트레이션은 Fleet, 로봇은 원자 액션"(D-12/D-20)을 깨고, 오프셋이 이미
  슬롯을 표현하므로 얻는 것이 없다.

## Goals

1. `rosy_fleet` 씨앗 패키지: 대형 기하, 슬롯 배정, 릴레이, 세션 오케스트레이터, CLI.
   전부 ROS import 없이 Windows pytest 로 검증된다.
2. `gz_multi.launch.py core:=true` 로 로봇별 `rosy_core` 가 기동된다.
3. 시뮬 3대에서 LINE → V 전환이 재배정과 함께 관측된다.
4. 릴레이가 재는 팔로워 수신 주기 ≥10 Hz, 릴레이 정지 후 전 팔로워 HOLD ≤1 s,
   팔로워 1대 stuck 주입 시 전체 정지가 계측으로 남는다.

## Non-Goals

- 실물 2대 수락과 `capabilities.hardware.yaml` 의 `swarm` 점등 (다음 슬라이스).
- Fleet 서버 본체: 레지스트리, 페어링, 아웃바운드 WS, 대시보드 (Phase 4).
- Hungarian 배정, `peer` 참조 소스(D-21 트리거 대기), pure-pursuit v2 소스.
- 로봇 쪽 `rosy_core` 변경. 이 슬라이스는 로봇 계약을 소비만 한다.
- 맵 배포(OPS-001). 시뮬은 같은 맵 파일을 쓰고, 실물은 당장 수동 복사다.

## Architecture

```text
src/rosy_fleet/                              ament_python. rosy_core 스키마만 import (D-18)
├── package.xml, setup.py, resource/rosy_fleet
├── rosy_fleet/
│   ├── formation/
│   │   ├── geometry.py        Formation, SlotOffset, slots()          ── 순수 함수 (FOR-001)
│   │   └── assignment.py      SlotAssigner, GreedyDistanceAssigner    ── 순수 함수 (FOR-002)
│   ├── swarm/
│   │   ├── robots.py          RobotEndpoint(base_url, token, robot_id), robots.yaml 로더
│   │   ├── transport.py       RobotClient 프로토콜 (REST + WS) 와 httpx/websockets 구현
│   │   ├── arming.py          FormationSpec + 순수 사전검사·배정 계획 (릴레이를 만지기 전에 끝난다)
│   │   ├── relay.py           리더 pose 소켓 1 → 팔로워 reference 소켓 N 팬아웃 (D-31)
│   │   └── session.py         FormationSession: 무장 → 릴레이 → 감시 → FOR-004
│   └── cli.py                 `rosy_fleet formation ...`, `rosy_fleet relay ...`
└── test/                      네트워크·ROS 없음. RobotClient 를 가짜로 주입

src/rosy_gz_sim/launch/gz_multi.launch.py    core:=true — 로봇별 rosy_core 노드
src/rosy_gz_sim/scripts/swarm_bench.py       리더 주행 + 팔로워 계측 CSV
```

경계 규칙 세 가지.

- **로봇 쪽은 건드리지 않는다.** `rosy_core` 는 소비 대상이다. 필요한 것이 로봇
  계약에 없으면 그것은 이 슬라이스의 발견이고, API Ref 개정은 별도 사이클이다.
- **릴레이는 envelope 을 열어보지 않는다.** 리더 소켓에서 받은 텍스트 프레임을
  그대로 팔로워 소켓에 쓴다. SWM-007 의 "소비자는 소스를 묻지 않는다"는 여기서
  실증된다. 릴레이가 계측을 위해 프레임을 파싱하는 것은 허용되지만, 전달하는
  바이트는 바꾸지 않는다.
- **`formation/` 은 전송을 모른다.** 입력은 숫자, 출력은 숫자다. `swarm/` 만
  `RobotClient` 를 통해 바깥을 본다. 테스트가 import 그래프로 이것을 확인한다
  (`rosy_fleet.formation` 이 `httpx`·`websockets`·`rosy_fleet.swarm` 을 import
  하지 않는다).

## Detailed Design

### 1. 대형 기하 (`formation/geometry.py`)

```python
class Formation(str, Enum):
    FOLLOW = "FOLLOW"; COLUMN = "COLUMN"; LINE = "LINE"
    V = "V"; GRID = "GRID"; CIRCLE = "CIRCLE"

@dataclass(frozen=True)
class SlotOffset:
    distance: float   # 리더 뒤 (+), m
    lateral: float    # 리더 왼쪽 (+), m

def slots(formation: Formation, followers: int, spacing: float,
          *, grid_cols: int = 2) -> list[SlotOffset]
```

좌표 규약은 `rosy_core.navigation.swarm.follow_goal` 과 같다: 리더 heading 기준,
`distance` 는 뒤쪽 양수, `lateral` 은 왼쪽 양수. 리더는 항상 슬롯 0 이며 목록에
들어가지 않는다 — 반환값은 팔로워 수만큼이다.

| 대형 | 리더 위치 | k 번째 팔로워 (k = 1..n), s = spacing |
|---|---|---|
| FOLLOW | 선두 | n = 1 만 허용. `(s, 0)` |
| COLUMN | 선두 | `(k·s, 0)` |
| LINE | 중앙 | `(0, ±⌈k/2⌉·s)` — 왼쪽, 오른쪽 교대 (k 홀수 왼쪽) |
| V | 꼭짓점 | `(⌈k/2⌉·s, ±⌈k/2⌉·s)` — 같은 교대 |
| GRID | 앞줄 왼쪽 끝 | 리더 포함 전체 n+1 을 `grid_cols` 열로 채운다. 인덱스 j = k 의 행 `⌊j/cols⌋`, 열 `j mod cols` → `(row·s, −col·s)` |
| CIRCLE | 원 위 한 점 | 반지름 `r = s / (2·sin(π/(n+1)))`. 리더를 원 위 각도 0 에 두고 중심을 리더 뒤 `r` 에 놓는다. k 번째 점은 각도 `2πk/(n+1)`. 리더 기준 상대좌표로 변환해 `(r − r·cos θ, r·sin θ)` |

거절 규칙(`ValueError`):

- `spacing < MIN_SPACING` (§4.3). 그 값에서는 팔로워 목표가 리더 장애물 안이다.
- `followers < 1`. FOLLOW 에 `followers > 1`.
- `grid_cols < 1`. 유한하지 않은 값.

CIRCLE 의 인접 점 간 호 길이가 아니라 **현의 길이**가 `s` 다 — 두 로봇 사이의
직선 거리가 안전 하한을 넘어야 하기 때문이다.

리더가 제자리에서 회전하면 측방 슬롯이 함께 돈다. 이것은 리더 기준 대형의
본질이고 ≤0.2 m/s 군집 속도(SWM-002)에서는 수용한다. 회전 중 팔로워가 큰 원을
그리는 것이 문제가 되면 그때 **리더 heading 을 저역통과**하는 옵션을 릴레이가
아니라 세션에 두어야 한다 — 릴레이는 프레임을 바꾸지 않는다(§Architecture). 이
슬라이스에서는 만들지 않고 계측으로 필요 여부를 본다.

### 2. 슬롯 배정 (`formation/assignment.py`)

```python
class SlotAssigner(Protocol):
    def assign(self, robots: Mapping[str, Point], slots: Sequence[Point]) -> dict[str, int]: ...

class GreedyDistanceAssigner:
    """전 (로봇, 슬롯) 쌍을 거리 오름차순으로 훑어 비어 있는 것부터 짝짓는다."""
```

입력은 로봇별 현재 월드 좌표와 슬롯의 월드 좌표다. 슬롯 월드 좌표는 세션이
리더 pose 로 `SlotOffset` 을 변환해 만든다(`follow_goal` 과 같은 식). 출력은
`robot_id → slot index`. 로봇 수와 슬롯 수가 다르면 `ValueError`.

그리디가 최적은 아니다(FOR-002 도 그렇게 적었다). 테스트가 고정하는 성질은 세
가지다: 전단사, 입력 순서 불변, 그리고 2대 경우에 교차 배정이 나오지 않는다는
것. Hungarian 은 같은 프로토콜의 두 번째 구현으로 들어온다.

재배정은 **대형 전환 시에만** 한다. 주행 중에는 리더 대비 오프셋이 고정이다 —
주행 중 재배정은 팔로워 둘의 목표를 서로 바꾸는 것이고, 그 순간 둘이 교차한다.

### 3. 로봇 목록과 전송 (`swarm/robots.py`, `swarm/transport.py`)

```yaml
# robots.yaml
robots:
  - robot_id: rosy_01
    base_url: http://192.168.0.11:8080
    token: <operator 이상>
  - robot_id: rosy_02
    base_url: http://192.168.0.12:8080
    token: <operator 이상>
```

토큰은 로봇마다 다르다(D-30: 장치 로컬 토큰). 참조 소켓은 operator 이상이고
(pose 를 밀어넣는 것은 로봇을 움직이는 일이다, D-31) `swarm/follow` 도 operator
다. 리더 pose 소켓은 viewer 면 되지만 같은 토큰을 쓴다. 파일 권한은 배포 문제라
여기서 강제하지 않되, CLI 는 world-readable 파일이면 경고한다.

`RobotClient` 프로토콜 (아래는 설계 시점의 스케치다. 구현은 `open_reference_sink()` 가 async 이고
`navigation_goal(x, y, yaw)` 이 있으며, **로봇이 4401/4403 으로 거부한 소켓은 `RobotApiError` 로 올라온다** —
"닫힘" 과 "거부" 를 구분하지 않으면 잘못된 토큰이 조용히 0 Hz 로 영원히 재시도된다는 것을 Task 5 리뷰가
잡았다. 정본은 `src/rosy_fleet/rosy_fleet/swarm/transport.py`):

```python
class RobotClient(Protocol):
    robot_id: str
    async def state(self) -> dict                          # GET /api/v1/robot/state
    async def swarm_state(self) -> dict                    # GET /api/v1/swarm/state
    async def follow(self, params: SwarmFollowParams) -> dict   # POST /api/v1/swarm/follow (raises RobotApiError(code, status))
    async def swarm_cancel(self) -> dict                   # POST /api/v1/swarm/cancel
    async def navigation_cancel(self) -> dict              # POST /api/v1/navigation/cancel
    def pose_stream(self) -> AsyncIterator[str]            # WS /ws/swarm/pose, 텍스트 프레임
    def reference_sink(self) -> ReferenceSink              # WS /ws/swarm/reference, send(str)
    def events(self, types: Sequence[str]) -> AsyncIterator[dict]   # WS /ws/events?types=
```

구현은 httpx + websockets. 테스트는 이 프로토콜의 가짜를 주입한다.
`SwarmFollowParams` 는 `rosy_core.protocol.schemas` 의 것을 그대로 쓴다(D-18).

### 4. 릴레이 (`swarm/relay.py`)

리더 `pose_stream()` 을 읽어 각 팔로워 `reference_sink()` 에 같은 텍스트를
쓴다. 규칙:

- **합성하지 않는다.** 리더 소켓이 끊기면 마지막 프레임을 반복하지 않는다.
  팔로워는 SWM-004 로 `stream_timeout_ms` 안에 스스로 HOLD 한다. 릴레이가
  프레임을 반복하면 리더가 죽었는데 대형이 "살아 있는" 것으로 보인다.
- **팔로워 하나의 실패가 나머지를 막지 않는다.** 소켓별로 독립 태스크. 한
  팔로워 소켓이 끊기면 그 팔로워만 재연결하고(지수 backoff, 상한 2 s) 나머지는
  계속 받는다. 끊긴 동안 그 팔로워는 스스로 HOLD 한다.
- **느린 팔로워에 밀리지 않는다.** 소켓별 큐는 깊이 1 이며 최신 프레임이 이전
  것을 덮는다. 리더의 최신 위치를 잃는 것보다 중간 표본을 버리는 쪽이 맞다 —
  로봇 쪽도 같은 선택을 했다(2 Hz 창에서 최신 표본 유지).
- **`pause()` / `resume()`.** 일시정지 중에는 리더 소켓은 계속 읽되(재연결 비용을
  피한다) 팔로워에 쓰지 않는다. FOR-004 의 "전체 HOLD" 가 이것이다(§6.4).
- **계측.** 팔로워별 송신 주기(이동 평균)와 리더 수신 주기를 `RelayStats` 로
  노출한다. 리더 프레임을 파싱해 `seq` 간격을 세고, 빠진 `seq` 는 `dropped` 로
  센다(한 연결 안의 간격만 — 단절은 드롭이 아니다). 파싱 실패는 계측만 건너뛰고
  전달은 그대로 한다. **불변식: 스트림이 멎으면 주기는 0 으로 떨어진다.** 마지막
  표본이 0.5 s 보다 오래됐으면 `hz` 는 0 이고 `leader_age_s` 가 그 나이를 말한다.
  프레임을 합성하지 않는 릴레이가 건강한 주기를 합성하면 같은 거짓말이다 — Task 7
  리뷰가 이것을 잡았고, §8 의 `relay_tx_hz ≥ 10` 판정은 이 불변식 없이는 실패할
  수 없는 지표였다. 거부된 소켓은 리더든 팔로워든 `*_last_error` 에 이유를 남긴다.

### 5. 세션 (`swarm/session.py`)

```python
@dataclass
class FormationSpec:
    formation: Formation
    spacing: float = 0.6
    grid_cols: int = 2
    max_speed: float = 0.15
    stream_timeout_ms: int = 1000

class HoldPolicy(str, Enum):
    HOLD = "HOLD"      # 기본. 릴레이 pause + 리더 navigation/cancel
    ABORT = "ABORT"    # 전 팔로워 swarm/cancel + 리더 navigation/cancel

class FormationSession:
    def __init__(self, leader: RobotClient, followers: Sequence[RobotClient],
                 spec: FormationSpec, *, assigner: SlotAssigner = GreedyDistanceAssigner(),
                 policy: HoldPolicy = HoldPolicy.HOLD, relay_factory=Relay, clock=time.monotonic)
    async def start(self) -> None
    async def reform(self, spec: FormationSpec) -> None
    async def resume(self) -> None
    async def stop(self) -> None
    @property
    def state(self) -> SessionState   # ARMING | RUNNING | HOLDING | STOPPED, 사유 포함
```

**start.**

1. 리더와 팔로워 전원의 `state()` 를 읽는다. `map_id` 가 값이 있고 서로 다른
   로봇이 있으면 시작하지 않는다(`MapMismatch`). 로봇 쪽도 프레임마다 검사하지만
   시작 전에 알 수 있는 것을 시작 뒤에 알게 하지 않는다.
2. `slots()` → 리더 pose 로 월드 좌표 변환 → `assign()`.
3. 팔로워마다 `follow(SwarmFollowParams(target_robot_id=leader.robot_id,
   distance=slot.distance, lateral=slot.lateral, max_speed, stream_timeout_ms))`.
   **전부 아니면 전무**: 하나라도 실패(409/501/네트워크)하면 이미 무장된 팔로워에
   `swarm_cancel()` 을 보내고 `ArmingFailed(robot_id, code)` 로 끝낸다. 네트워크
   실패(타임아웃 등)는 **결과를 알 수 없는** 실패다 — 로봇이 follow 를 적용한 뒤에
   응답만 잃었을 수 있으므로, 그 로봇에도 `swarm_cancel()` 을 보낸다. 거절(`RobotApiError`)
   만이 "무장되지 않았다"를 뜻한다. 무장된
   팔로워만 남기면 그 팔로워는 참조 프레임 하나에 달려나갈 준비가 된 채로
   남는다 — 로봇 쪽 `swarm_follow` 라우트가 같은 이유로 같은 규칙을 쓴다.
4. 릴레이 시작. 각 로봇 `events(["nav.*", "swarm.*", "safety.estop"])` 구독.
5. `RUNNING`.

**reform.** 릴레이 `pause()` → 새 슬롯 계산·배정 → 팔로워마다 `follow()` 재호출
(로봇 쪽은 NAVIGATION 중 재호출을 대형 변경으로 받는다) → `resume()`. 팔로워는
pause 동안 HOLD 하고 새 오프셋으로 이어간다. 재호출이 하나라도 실패하면 **정책과
무관하게 세션을 끝낸다** (`STOPPED(reason=reform_failed)`, 전 팔로워 `swarm_cancel`,
리더 `navigation_cancel`). 그 시점에 재무장된 팔로워는 이미 풀렸고 나머지는 옛
오프셋의 follow 세션을 쥐고 있어, HOLD 로 두고 나중에 스트림을 다시 켜면 대형이
둘로 갈린다. 절반 대형은 재개할 수 없으므로 종료가 정직하다. 운영자가 새 formation
명령으로 다시 무장한다.

**reform 의 거절은 두 종류다.** 로봇을 하나도 건드리기 전에 알 수 있는 거절 —
잘못된 대형 스펙(`slots()` 의 `FormationError`), 맵 불일치, 리더 e-stop, 배정 불가,
사전 `state()` 읽기의 네트워크 실패 — 은 **세션을 있던 그대로 둔다** (RUNNING 이면
릴레이를 아예 멈추지 않았고, HOLDING 이면 HOLDING). 이 계산은 순수 함수
(`swarm/arming.py`) 로 릴레이 `pause()` **앞**에서 끝난다. 불변식: *릴레이를 멈추는
것은 그것을 다시 켤 수 있는 상태를 함께 세우는 것뿐이다.* 재무장이 시작된 뒤의
실패(어느 팔로워든 `follow` 를 다시 받은 뒤)만 위의 "절반 대형" 이라 종료한다.
Task 12 리뷰가 이 구분을 잡았다 — 고치기 전에는 `reform FOLLOW` 오타 하나가 릴레이만
멈춘 채 RUNNING 으로 남아 `resume` 도 듣지 않았고, 리더 e-stop 뒤의 reform 이 멀쩡한
대형을 종료시켰다(그런데 `resume` 의 거절 메시지는 reform 을 권했다).

**reform 도중 FOR-004 트리거가 오면 reform 은 그것을 덮어쓰지 않는다.** 재무장은
로봇 수만큼의 HTTP 왕복이고 그 사이에 감시 태스크가 돈다. 세션은 정책 세대 카운터를
들고 있어, 재무장이 끝났을 때 세대가 바뀌었으면 (HOLD 가 걸렸으면) 새 오프셋은
무장된 채 **HOLDING 에 머물고 릴레이를 켜지 않는다** — 운영자가 본다. 세션이 그
사이 STOPPED 가 됐으면 (ABORT) 재무장된 로봇을 다시 풀고 `SessionError` 로 끝낸다.
Task 8 리뷰가 이 창을 잡았다: 고치기 전에는 e-stop 이 났는데 reform 이 RUNNING 으로
되돌리고, ABORT 정책에서는 취소한 로봇을 죽은 릴레이에 다시 무장시켰다.

**stop.** 릴레이 종료 → 전 팔로워 `swarm_cancel()` → `STOPPED`. 리더 항법은 건드리지
않는다 — 운영자가 리더를 몰고 있었다면 그것은 운영자의 것이다.

### 6. FOR-004 감시

#### 6.1 트리거

어느 로봇(리더 포함)에서든 다음 이벤트가 오면 정책을 적용한다.

| 이벤트 | 뜻 |
|---|---|
| `nav.stuck` | 30 s 무진척. 로봇 쪽은 이미 그 팔로워의 세션을 닫았다 |
| `nav.failed` | Nav2 목표 실패 |
| `nav.blocked` | 경로 막힘 |
| `swarm.aborted` | 팔로워가 어떤 이유로든 대형을 떠났다 (e-stop, 도킹, 수동, 취소) |
| `safety.estop` | 어느 로봇이든 |

#### 6.2 자기 유발과 정보성 이벤트는 트리거가 아니다

- `swarm.hold(reason=reference stream lost)` — 릴레이가 `pause()` 상태이거나
  팔로워 소켓이 재연결 중이면 우리가 만든 것이다. `HOLDING` 중에는 무시하고,
  `RUNNING` 중에 오면 그 팔로워의 소켓 상태를 보고 재연결 중이 아닐 때만 경고
  로그를 남긴다. 트리거는 아니다 — 그 팔로워는 이미 서 있다.
- `swarm.hold(reason=map_mismatch)` — 로봇 쪽이 이미 목표를 거뒀고 대형은 유지
  중이다. 경고 로그. 시작 전 검사(§5.1)를 통과했으므로 주행 중 맵이 바뀐 경우다.
- `nav.started` / `nav.completed` / `nav.canceled` — 정보. `nav.canceled` 는 우리의
  `navigation_cancel()` 결과이기도 하다.

#### 6.3 정책

- **HOLD (기본):** 릴레이 `pause()` → 팔로워 전원이 `stream_timeout_ms` 안에 스스로
  HOLD → 리더 `navigation_cancel()`. 세션은 `HOLDING(reason, robot_id)`. 팔로워의
  follow 세션은 살아 있으므로 `resume()` 하면 새 follow 명령 없이 이어간다.
- **ABORT:** 팔로워 전원 `swarm_cancel()` → 리더 `navigation_cancel()` → `STOPPED`.

`resume()` 은 운영자 명령이다. 자동 재개는 없다 — 로봇 쪽이 e-stop 해제와
stuck 을 "재개가 아니라 해제"로 다루는 것과 같은 규칙이고, 자동 재개는 SRS 가
금지한 자동 재시도가 된다.

**HOLDING 중에 다른 로봇의 트리거가 오면 버리지 않고 `pending_triggers` 에 쌓는다.**
리더를 다시 세우지는 않지만(이미 서 있다) 정보는 남긴다. `resume()` 은 그 목록이
비어 있지 않으면 거절하고, 비어 있어도 릴레이를 켜기 전에 팔로워 전원의
`swarm/state` 를 다시 읽어 `active: false` 인 팔로워가 있으면 거절한다 — HOLD 중에
대형을 떠난 로봇을 향해 스트림을 켜면 안 된다. 거절 메시지는 `reform`(재무장) 이나
`stop` 을 가리킨다. `reform` 이 성공하면 목록은 비워진다 — e-stop 상태의 로봇은
`follow` 를 거절하므로 그것은 `ArmingFailed` 로 드러난다.

#### 6.4 결정: 전체 HOLD 는 스트림을 끊는 것이다 (D-35 후보)

FOR-004 는 "형성 중단 + 전체 HOLD" 를 요구하고, 로봇 API 에는 hold 엔드포인트가
없다. 두 길이 있었다.

- 로봇 API 에 `POST /swarm/hold` 를 추가한다. 명시적이지만 계약 개정이고, 이미
  있는 SWM-004 와 의미가 겹치는 두 번째 HOLD 경로가 생긴다.
- **참조 스트림을 끊는다.** SWM-004 는 정확히 이 상황을 위해 있다 — 스트림이
  끊기면 자리를 지킨다. 오케스트레이터가 그것을 의도적으로 쓴다.

두 번째를 택한다. 로봇 계약이 그대로이고, HOLD 경로가 하나이며, 릴레이 장애와
의도된 HOLD 가 로봇에서 같은 코드로 처리되므로 테스트된 경로만 밟는다. 비용은
HOLD 진입에 `stream_timeout_ms`(기본 1 s) 가 걸린다는 것이고, 그 값은 SWM-004 가
이미 수용한 값이다. 급한 정지는 HOLD 가 아니라 e-stop 이며 별도 경로다.

이 결정은 ADR Log 에 D-35 로 올릴 후보다. 이 문서는 후보로 표시만 하고, ADR
등록은 시뮬 계측이 HOLD ≤1 s 를 실제로 보여준 뒤에 한다.

### 7. CLI (`cli.py`)

```bash
rosy_fleet relay     --robots robots.yaml --leader rosy_01                 # 릴레이만
rosy_fleet formation --robots robots.yaml --leader rosy_01 \
                     --formation V --spacing 0.6 --max-speed 0.15 \
                     [--policy HOLD|ABORT] [--grid-cols 2]
```

`formation` 은 세션을 열고 stdin 명령을 받는다: `reform <FORMATION> [spacing]`,
`resume`, `stop`, `status`. 릴레이 통계와 세션 상태를 1 s 마다 한 줄로 찍는다.
콘솔 스크립트 `rosy_fleet` 으로 설치된다.

### 8. 시뮬 하네스

#### 8.1 `gz_multi.launch.py core:=true`

로봇 i 마다 `rosy_core` 노드를 추가한다.

| 항목 | 값 |
|---|---|
| 네임스페이스 | `rosy_0i` (`Node(namespace=ns)` — 노드 하나라 `PushRosNamespace` 그룹과 같다). `rosy_core` 의 토픽은 상대 이름이라 그대로 붙는다 |
| `ROSY_NAMESPACE` | `rosy_0i` → `frame_prefix = rosy_0i/`. `_tick_state` 가 `map → rosy_0i/base_footprint` 를 찾는다 |
| `ROSY_CONFIG` | 런치 시 생성한 YAML. `robot.id: rosy_0i`, `robot.name`, `network.api_port: 8080 + i − 1` |
| `HOME` | `additional_env` 로 로봇별 임시 디렉터리. `~/.rosy/waypoints.json` 과 그 옆의 `audit.jsonl` 이 `Path.home()` 에 고정돼 있어, 갈라 주지 않으면 N대가 한 파일을 쓴다. 각 코어의 `~/.ros/log` 도 그 임시 HOME 아래로 간다 |
| `use_sim_time` | `True` |
| capabilities | 기본 `config/capabilities.yaml` 이 이미 `swarm.follow/lead: true` 다. 별도 파일 없음 |

런치가 `robots.yaml` 도 같은 임시 디렉터리에 써 준다 — `base_url:
http://127.0.0.1:808(i−1)`, 토큰은 기본 설정의 `rosy-dev-operator`. CLI 에 그
경로를 넘기면 된다.

#### 8.2 `swarm_bench.py`

`rosy_gz_sim/scripts/` 의 계측 스크립트 자리다 (도킹 측정 리그 브랜치의 `dock_sweep.py` 와 같은 자리·구조 — 그 파일은 아직 main 에 없다). 리더에 `POST /navigation/goal` 로
waypoint 를 순서대로 걸고(다음 목표는 `nav.completed` 이벤트로), 1 s 마다 팔로워
전원의 `GET /swarm/state`(`holding`, `stream_age_s`)와 `GET /robot/state` pose 를
읽어, 그 시각 리더 pose 로 계산한 슬롯 월드 좌표와의 거리 오차를 CSV 한 줄로
남긴다. 열: `t, robot_id, holding, stream_age_s, slot_err_m, relay_tx_hz`.

시나리오 인자:

- `--scenario follow` : 3대 COLUMN, 리더가 waypoint 4개 순회
- `--scenario reform` : 주행 중 LINE → V 전환
- `--scenario hold` : 릴레이 `pause()` 주입 → 전원 `holding` 까지의 시간
- `--scenario stuck` : 팔로워 하나 앞에 `gz service` 로 장애물 모델 스폰 → `nav.stuck` → 전체 정지까지의 시간

### 9. 오류 처리 요약

| 상황 | 처리 |
|---|---|
| 사전검사 거절 (스펙·맵·리더 e-stop·배정, 그리고 사전 `state()` 읽기의 네트워크 실패 → `ArmingFailed(TRANSPORT)`) | 로봇을 건드리지 않았으므로 세션은 있던 그대로. `start` 는 STOPPED, `reform` 은 원래 상태 유지, `resume` 은 HOLDING 유지 |
| 무장 중 한 대 실패 | 무장된 것 전부 cancel(결과 미상인 그 로봇 포함), `ArmingFailed`. 릴레이 시작 안 함 |
| 무장은 됐는데 릴레이를 못 만들거나 못 켬 | 팔로워 전원 cancel, `STOPPED`, `SessionError`. 무장된 채 ARMING 에 걸려 있으면 안 된다 |
| ABORT 뒤 | 감시 태스크도 끝낸다 — 세션이 끝난 로봇의 이벤트 소켓을 계속 열어 두지 않는다 |
| 시작 전 `map_id` 불일치 | 시작 거절 `MapMismatch` |
| 리더 소켓 단절 | 재연결(backoff ≤2 s). 합성 없음. 팔로워는 스스로 HOLD |
| 리더 소켓 거부 | `RobotApiError` 로 올라온다. 릴레이는 재연결을 계속하되 `RelayStats.leader_last_error` 에 이유를 남기고 CLI 가 그것을 찍는다 — "0 Hz 가 영원히" 에는 이유가 붙어야 한다. **와이어 사실:** `rosy_core` 의 `_authorize` 는 `accept()` 전에 `close(4401|4403)` 하므로 uvicorn 은 이것을 HTTP 403 핸드셰이크 거절로 보낸다. 클라이언트가 보는 코드는 `WS_403` 이고 4401/4403 의 구분은 와이어에서 사라진다. accept-then-close 로 바꿔 코드를 살리는 것은 로봇 쪽 사이클의 일이다(이 슬라이스는 `rosy_core` 를 건드리지 않는다) |
| 팔로워 소켓 거부 | 같은 규칙: 그 레인만 backoff 로 재연결하고 `RelayStats.follower_last_error[robot_id]` 에 이유를 남긴다. 연결은 됐는데 send 에서 깨지는 소켓도 backoff 를 키운다 |
| 팔로워 소켓 단절 | 그 소켓만 재연결. 나머지 계속 |
| 이벤트 소켓 단절 | 재연결(backoff, 조용한 종료도 같다 — 꺼진 로봇을 향해 빈 루프를 돌면 안 된다). 끊긴 동안의 이벤트는 놓친다 — 재연결 직후 그 로봇을 다시 본다: 팔로워는 `swarm_state()` 의 `active: false` 를 `swarm.aborted` 로, 리더는 `robot/state` 의 `mode == EMERGENCY` 를 `safety.estop` 으로 간주한다(리더에는 swarm 세션이 없어 `swarm_state` 로는 볼 수 없다). RUNNING 이면 정책, HOLDING 이면 `pending_triggers` |
| FOR-004 트리거 | §6.3 정책 |
| reform 실패 | 정책과 무관하게 종료: 전 팔로워 cancel, 릴레이 종료, 리더 cancel → `STOPPED(reform_failed)`. 절반 대형은 재개할 수 없다 (§5 reform) |
| CLI 종료 (SIGINT) | `stop()` — 팔로워 전원 cancel 뒤 종료. 릴레이만 죽이고 팔로워를 무장 상태로 두지 않는다 |

## Testing Strategy

### 단위 (`src/rosy_fleet/test/`, ROS·네트워크 없음)

- `test_geometry.py`: 6종 대형의 슬롯 좌표를 손으로 계산한 값과 비교. 하한 미만
  spacing 거절. FOLLOW 에 2대 거절. CIRCLE 인접 현 길이 = spacing. GRID 가
  cols 를 넘기면 다음 행.
- `test_assignment.py`: 전단사, 입력 순서 불변, 2대 비교차, 개수 불일치 거절.
- `test_relay.py`: 가짜 소켓으로 프레임이 바이트 동일하게 전달됨, pause 중 전달
  없음, 팔로워 하나 실패 시 나머지 전달, 리더 단절 시 합성 없음, 깊이 1 큐가 최신을
  남김, `seq` 갭이 `dropped` 로 집계됨.
- `test_session.py`: 전부 아니면 전무 무장(2번째 팔로워 409 → 1번째 cancel 호출),
  시작 전 map 불일치 거절, 5개 트리거 각각 → HOLD 정책의 호출 순서(pause → 리더
  cancel), ABORT 정책, `HOLDING` 중 `swarm.hold` 무시, `resume()` 만 재개,
  reform 이 pause → follow 재호출 → resume 순서, stop 이 전원 cancel.
- `test_boundaries.py`: `rosy_fleet.formation` 의 모듈 import 그래프에
  `httpx`·`websockets`·`rosy_fleet.swarm`·`rclpy` 가 없다.

### 런치 (ROS 있는 환경)

- `gz_multi.launch.py core:=true robots:=3` 의 `OpaqueFunction` 을 단위 실행해
  로봇별 `rosy_core` 액션 3개, 서로 다른 `api_port`, 서로 다른 `HOME` 을 확인한다
  (계획서가 `gz_multi` 에 이미 쓰는 방식).

### 시뮬 계측 (완료 기준)

| 항목 | 기준 | 시나리오 |
|---|---|---|
| 스트림 | 팔로워별 `relay_tx_hz ≥ 10` | follow |
| 추종 | 정상 주행 구간 `slot_err_m` 중앙값 기록(기준값은 이 계측이 정한다), `holding` 없음 | follow |
| 재배정 | LINE → V 전환 뒤 각 팔로워가 새 슬롯으로 수렴, 교차 없음 | reform |
| HOLD | pause 뒤 전원 `holding: true` 까지 ≤1 s + 폴링 간격 | hold |
| FOR-004 | stuck 이벤트 뒤 전원 정지, 리더 `nav.canceled` | stuck |

CI 는 `src/rosy_fleet` 을 colcon 빌드하고 `python3 -m pytest src/rosy_fleet/test/`
를 기존 `rosy_core` 스텝 옆에 추가한다. 시뮬 계측은 CI 밖이다.

## Risks & Preconditions

- **`gz_multi` nav 모드는 아직 런타임 미검증이다.** 계획서 P0-6 의 수용 기준
  "시뮬 2대 독립 주행" 은 M0 항목으로 남아 있고, `nav2_params.yaml` 의 프레임
  이름(`base_footprint`, `odom`, `map`)이 `frame_prefix` 와 맞물리는지가 첫 관문이다.
  이 슬라이스의 **1단계는 그것을 확인하는 것**이며, 여기서 막히면 그 수정이 이
  슬라이스보다 먼저다.
- **2 Hz 목표 교체 때 Nav2 BT 재시작 거동**은 계측으로만 안다. `slot_err_m` 이
  진동하면 원인은 여기일 가능성이 크다.
- **한 호스트에 `rosy_core` N개.** `HOME` 분리로 파일 충돌은 피하지만, 포트·로그
  경로 등 아직 모르는 공유 자원이 나올 수 있다. 런치 단위 실행이 잡지 못하는
  것은 시뮬 첫 기동에서 드러난다.
- **리더가 팔로워 costmap 의 장애물이다.** Nav2 는 목표점이 아니라 팔로워의
  footprint 로 충돌을 검사하므로 하한은 `inflation_radius + 리더 외접반경 + 팔로워
  외접반경 + footprint_padding = 0.15 + 0.085 + 0.085 + 0.03 ≈ 0.35 m` 다. LINE 과
  GRID 앞줄은 팔로워를 리더와 나란히 세우므로 이 값이 그대로 로봇 사이 거리다.
  `MIN_SPACING = 0.4` 는 그 위로 약 5 cm 여유이며 넉넉하지 않다. (Task 2 리뷰가
  "반폭 0.06 + inflation 0.15 = 0.21" 이라는 첫 유도가 점 목표 기준이라 실제보다
  낮다는 것을 잡았다.) Nav2 파라미터가 바뀌면 이 식으로 다시 계산한다 — 상수 옆에
  같은 식을 적어 둔다.
- **시뮬과 실물의 DDS 차이**(§Background). 시뮬 통과가 WLAN 지연을 검증하지는
  않는다. 실물 슬라이스에서 `relay_tx_hz` 와 `stream_age_s` 를 다시 잰다.

## Open Questions

없음. 아래는 계측이 답할 것이지 설계가 정할 것이 아니다.

- 정상 주행 `slot_err_m` 의 기준값.
- 리더 heading 저역통과가 필요한가(§1 말미).
- Hungarian 이 필요한 대수.

## Migration / Rollout

1. `gz_multi robots:=2 mode:=nav` 런타임 확인 (선행 관문).
2. `rosy_fleet` 패키지 + 단위 테스트 + CI 스텝.
3. `gz_multi core:=true` + 런치 단위 테스트.
4. `swarm_bench.py` 4개 시나리오 실행, CSV 를 `docs/plans/2026-09-08-swarm-formation-slice.md`
   (실행 계획서) 에 표로 요약.
5. 계측이 HOLD ≤1 s 를 보이면 D-35 를 ADR Log 에 올린다.
6. 다음 슬라이스: 실물 2대, FAT-06 변형(Fleet 단절 대신 릴레이 pause 주입),
   `capabilities.hardware.yaml` 점등.
