# rosy_games LOCAL 호스트 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 노트북에서 돌아가는 `rosy_games` 1단계 — 심판·휴리스틱·가짜 관측으로 두 대 CORE teleop를 내고, 카메라·Isaac·신경망 없이 LOCAL pytest가 득점·이격·쌍정지를 증명한다.

**Architecture:** 이미 있는 심판 스켈레톤(`15f7958`)을 설계 §3 트리에 맞춘다. `Game.step(obs)`는 규칙만, `Policy.act`는 속도만, `gate`가 HOLD/유실/이격을 강제한다. `MatchHost`가 셋을 묶고 `PlayerClient`만 CORE `mode`/`teleop`/`safety/stop`을 부른다. CORE·Fleet·이미지·`board.yaml`은 건드리지 않는다. 설계: `docs/plans/2026-09-17-robot-soccer-game-host-design.md` (D-90).

**Tech Stack:** Python 3.12, pytest, httpx, websockets, PyYAML. OpenCV는 `host/overhead.py`만, 이 계획의 기본 합격선에서 import하지 않는다. ROS/`rclpy` 없음.

**Windows:** 저장소 루트 `Rosy OS`에서 `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`.

---

## 지금 있는 것 / 없는 것

스켈레톤은 `src/rosy_games`에 있다. 심판이 공을 중앙에 두면 IN_PLAY로 넘기고, 골이면 점수·정지한다. 휴리스틱은 공을 쫓고 0.35 m 이내면 전진을 끊는다. `test/test_rosy_games_surface.py`가 이미지·슬라이스에 안 들어갔음을 본다.

빠진 것:

| 설계 §3 | 지금 |
|---|---|
| `test/conftest.py` | **있음** (Task 1). 루트 pytest 수집됨 |
| `field/types.py`, `geometry.py`, `homography.py` | `Field`가 `field/__init__.py`에 몰려 있음 |
| `Phase.HOLD` / `GOAL`, `lost_*`, `Game.step(obs)`만 | `KICKOFF`/`IN_PLAY`, `step(obs, actions)`가 정책 속도를 통과 |
| `game/gate.py` | 없음. 이격은 휴리스틱만 |
| `host/loop.py`, `transport.py`, `robots.py` | `host/` 빈 `__init__.py` |
| `cli.py`, `config/match.yaml` | 없음 |
| `isaac/` 없음 | **삭제함** (Task 1) |
| harness `progress.md` / `logs.md` | **있음** (Task 1). SOURCE/LOCAL HOLD |
| `src/AGENTS.md` pytest 목록 | **`rosy_games/test` 포함** |

하지 않는 것 (이 계획 밖): Isaac, `NeuralPolicy`, CORE 변경, D-62 슬라이스, 현장 두 대 충돌 속도, Fleet 콘솔 버튼.

구장 숫자는 스켈레톤을 유지한다. `Field.length_m` × `Field.width_m` (기본 1.8 × 1.2). 설계의 `width_m`/`height_m`으로 바꾸지 않는다. 원점은 중앙, +x는 home(`rosy_01`)이 공격하는 골.

---

### Task 1: 폴더 부트스트랩 — conftest, isaac 삭제, harness, pytest 목록

**Files:**
- Create: `src/rosy_games/test/conftest.py`
- Delete: `src/rosy_games/rosy_games/isaac/` (패키지 전체)
- Create: `src/rosy_games/progress.md`, `src/rosy_games/logs.md`
- Modify: `src/rosy_games/AGENTS.md`
- Modify: `tools/harness/harness.yaml`
- Modify: `src/AGENTS.md` Testing Requirements
- Modify: `docs/plans/AGENTS.md`

- [x] **Step 1: 실패하는 수집을 고정하는 테스트가 이미 있다**

루트에서:

```
python -m pytest src/rosy_games/test/test_soccer_game.py -q
```

Expected: ERROR `ModuleNotFoundError: No module named 'rosy_games'`

- [x] **Step 2: conftest — colcon 없이 패키지를 sys.path에 얹는다**

`src/rosy_games/test/conftest.py`:

```python
"""colcon install 없이 pytest를 돌린다 (Windows/CI)."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
entry = str(SRC / "rosy_games")
if entry not in sys.path:
    sys.path.insert(0, entry)
```

- [x] **Step 3: `isaac/`을 지운다**

설계 §3: 1단계에서 `isaac/` 디렉터리를 만들지 않는다. 빈 예약 패키지는 학습이 있는 것처럼 보인다.

- [x] **Step 4: 시험이 수집되고 스켈레톤 4개가 통과하는지 본다**

```
python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q
```

Expected: PASS (스켈레톤 3 + surface 2; boundaries 포함이면 4+2). `isaac` 폴더가 없어도 boundaries는 `field`/`game`/`policy`만 본다.

- [x] **Step 5: harness 기록**

`progress.md` 게이트: SOURCE HOLD (트리 미완), LOCAL HOLD (호스트 루프 없음), ROS-SIM/ARTIFACT N/A, DEVICE/FIELD PARKED. `adrs: [D-90]`. plans는 설계와 이 파일.

`logs.md` 첫 항목: conftest·isaac 삭제.

`AGENTS.md`에 `progress.md` / `logs.md` / `index.md`를 적고, harness 절차 한 줄을 넣는다.

`harness.yaml` modules에:

```yaml
  - name: rosy_games
    path: src/rosy_games
    tests: [src/rosy_games/test, test/test_rosy_games_surface.py]
    functional_kind: pytest
    functional: [src/rosy_games/test]
```

```
python tools/harness/rosy_harness.py generate
python -m pytest test/test_harness_contracts.py -q
```

Expected: PASS

- [x] **Step 6: `src/AGENTS.md` pytest 줄에 `rosy_games/test`를 넣는다**

- [x] **Step 7: Commit** (`06c0b22` / 계획 본문 `663a379`)

```
git add src/rosy_games tools/harness/harness.yaml src/AGENTS.md docs/plans/AGENTS.md
git commit -m "chore(games): bootstrap pytest path and drop the empty isaac package"
```

---

### Task 2: `Pose2D` / `Twist`와 구장 기하 분리

**Files:**
- Create: `src/rosy_games/rosy_games/field/types.py`
- Create: `src/rosy_games/rosy_games/field/geometry.py` (지금 `__init__.py`의 `Field`를 이동)
- Modify: `src/rosy_games/rosy_games/field/__init__.py` (재수출만)
- Create: `src/rosy_games/test/test_field.py`

- [x] **Step 1: 실패하는 시험**

`test_field.py`:

```python
from rosy_games.field import ZERO, Field, Pose2D, Twist


def test_home_scores_in_the_away_goal_mouth():
    field = Field()
    assert field.in_away_goal(field.length_m / 2, 0.0)
    assert not field.in_away_goal(0.0, 0.0)
    assert field.in_bounds(0.0, 0.0)
    assert not field.in_bounds(field.length_m, 0.0)


def test_zero_twist_is_a_full_stop():
    assert ZERO == Twist(0.0, 0.0)
    pose = Pose2D(0.1, -0.2, 1.5)
    assert (pose.x, pose.y, pose.yaw) == (0.1, -0.2, 1.5)
```

- [x] **Step 2: 실행해서 실패 확인**

```
python -m pytest src/rosy_games/test/test_field.py -v
```

Expected: FAIL — `Pose2D` / `Twist` / `ZERO` 없음

- [x] **Step 3: 최소 구현**

`types.py`: frozen `Pose2D(x, y, yaw)`, `Twist(linear, angular)`, `ZERO`.

`geometry.py`: 현재 `Field` 그대로 옮긴다. 기본값·`home_id`/`away_id`/`kickoff_radius_m`을 깨지 않는다.

`field/__init__.py`는 `Field`, `Pose2D`, `Twist`, `ZERO`만 재수출한다.

- [x] **Step 4: 기존 soccer/heuristic 시험도 통과**

```
python -m pytest src/rosy_games/test -q
```

Expected: PASS

- [x] **Step 5: Commit**

```
git commit -m "refactor(games): split field types from pitch geometry"
```

---

### Task 3: 심판은 관측만 먹고 HOLD/GOAL을 갖는다

**Files:**
- Create: `src/rosy_games/rosy_games/game/state.py`
- Create: `src/rosy_games/rosy_games/game/protocol.py`
- Modify: `src/rosy_games/rosy_games/game/soccer.py`
- Modify: `src/rosy_games/rosy_games/game/__init__.py`
- Modify: `src/rosy_games/test/test_soccer_game.py` (이름은 유지해도 되고 `test_soccer.py`로 옮겨도 된다. 둘을 동시에 두지 말 것)

심판 계약:

```text
Game.reset() -> MatchState
Game.step(obs: Observation) -> MatchState
```

`step`에 정책 속도를 넣지 않는다. `IN_PLAY`는 `PLAY`로 바꾼다. 추가:

- 공 또는 로봇 유실(`lost_ball` 또는 `lost_robots` 또는 `ball is None` / 두 id 중 하나 없음) → `HOLD`, reason 기록
- 골 → `GOAL` 한 틱(점수 +1) 다음 `reset`은 호출자가 한다. 구현이 골 직후 내부에서 `KICKOFF`로 돌아가도 된다. 시험은 **그 틱의 점수가 오르고 다음 틱이 킥오프**면 통과
- 킥오프는 공·두 로봇이 보이고 공이 `kickoff_radius_m` 안일 때만 `PLAY`

`Observation`은 `Pose2D`를 쓴다. 하위 호환 튜플 입력은 넣지 않는다. 기존 시험을 새 타입으로 고친다.

- [x] **Step 1: 실패하는 시험 — 유실이면 HOLD**

```python
from rosy_games.field import Pose2D
from rosy_games.game import Observation, Phase, SoccerGame


def _obs(*, ball=(0.0, 0.0), r1=( -0.4, 0.0, 0.0), r2=(0.4, 0.0, 3.1), lost_ball=False, lost=()):
    return Observation(
        t=0.0,
        ball=None if ball is None else Pose2D(ball[0], ball[1], 0.0),
        robots={"rosy_01": Pose2D(*r1), "rosy_02": Pose2D(*r2)},
        lost_ball=lost_ball,
        lost_robots=frozenset(lost),
    )


def test_missing_ball_in_play_holds():
    game = SoccerGame()
    game.step(_obs())  # kickoff -> play
    held = game.step(_obs(ball=None, lost_ball=True))
    assert held.phase is Phase.HOLD
    assert held.score["rosy_01"] == 0
```

기존 `test_reset_is_kickoff...` / `test_a_ball_in_the_away_goal...`도 `Pose2D`와 `step(obs)` 한 인자로 고친다. 골 틱에서 `actions`를 보지 않는다 — 정지는 `gate` 몫 (Task 4).

- [x] **Step 2: 실패 확인**

Expected: FAIL — `step`이 아직 actions를 받고 `HOLD`가 없음

- [x] **Step 3: `state.py` + `SoccerGame.step(obs)`**

`MatchState(phase, score, reason, scorer=None)`.

- [x] **Step 4: soccer + heuristic 시험 PASS** (heuristic는 아직 옛 `Observation`을 쓰면 이 Task에서 같이 `Pose2D`로 맞춘다)

- [x] **Step 5: Commit**

```
git commit -m "feat(games): referee holds on lost ball and drops policy actions"
```

---

### Task 4: `gate` — HOLD/GOAL/유실/이격은 정책과 무관하게 0

**Files:**
- Create: `src/rosy_games/rosy_games/game/gate.py`
- Create: `src/rosy_games/test/test_gate.py`

```text
gate(twists, obs, state, field) -> CommandSet
  CommandSet(twists: dict[str, Twist], estop: bool)
```

규칙:

- `state.phase`가 `PLAY`가 아니면 모든 twist `ZERO`, `estop=False` (워치독이 서게 한다. 호스트가 프로세스 사망 시에만 진짜 stop)
- `lost_ball` 또는 `lost_robots` 또는 한쪽 CORE를 이 함수가 알 필요는 없다. 유실은 이미 HOLD
- 두 로봇 거리 < `field` 기본 0.35 m 이면 접근하는 쪽 `linear`를 `min(linear, 0)`
- 입력 twist의 무한대/NaN은 `ZERO`로 교체

한쪽 클라이언트 실패로 양쪽 `estop=True`는 **루프**(Task 6) 몫이다. gate는 기하만 본다.

- [x] **Step 1: 실패하는 시험**

```python
from rosy_games.field import ZERO, Field, Pose2D, Twist
from rosy_games.game import Observation, Phase
from rosy_games.game.gate import gate
from rosy_games.game.state import MatchState


def test_gate_zeros_when_not_in_play_and_clips_ramming():
    field = Field()
    obs = Observation(
        t=0.0,
        ball=Pose2D(0.5, 0.0, 0.0),
        robots={
            "rosy_01": Pose2D(0.0, 0.0, 0.0),
            "rosy_02": Pose2D(0.1, 0.0, 0.0),
        },
        lost_ball=False,
        lost_robots=frozenset(),
    )
    hold = MatchState(phase=Phase.HOLD, score={"rosy_01": 0, "rosy_02": 0}, reason="lost")
    out = gate({"rosy_01": Twist(0.08, 0.0)}, obs, hold, field)
    assert out.twists["rosy_01"] == ZERO
    play = MatchState(phase=Phase.PLAY, score=hold.score, reason="")
    ram = gate({"rosy_01": Twist(0.08, 0.0), "rosy_02": Twist(0.08, 0.0)}, obs, play, field)
    assert ram.twists["rosy_01"].linear <= 0.0
    assert ram.twists["rosy_02"].linear <= 0.0
```

- [x] **Step 2–4: 구현, PASS, commit**

```
git commit -m "feat(games): clamp non-play and ramming twists in the referee gate"
```

---

### Task 5: `Policy` 프로토콜과 휴리스틱 dict

**Files:**
- Create: `src/rosy_games/rosy_games/policy/protocol.py`
- Modify: `src/rosy_games/rosy_games/policy/heuristic.py`
- Modify: `src/rosy_games/test/test_heuristic_policy.py`

```text
Policy.act(obs, state) -> dict[robot_id, Twist]
```

휴리스틱은 두 로봇 모두에 대해 지금과 같은 추적·골 바이어스·이격을 한다. `PLAY`가 아니면 빈 dict 또는 모두 `ZERO` — gate가 한 번 더 자른다.

기존 `act(robot_id, observation)` 시그니처는 삭제한다. 시험 한 곳에서만 호출한다.

- [x] **Step 1–5: 실패 시험 → 구현 → 기존 추적/이격 assert를 dict 결과에 맞게 → commit**

```
git commit -m "feat(games): policy returns twists for both robots"
```

---

### Task 6: `MatchHost` 루프 (가짜 관측·가짜 클라이언트)

**Files:**
- Create: `src/rosy_games/rosy_games/host/observer.py`
- Create: `src/rosy_games/rosy_games/host/loop.py`
- Create: `src/rosy_games/test/fakes.py`
- Create: `src/rosy_games/test/test_loop.py`
- Modify: `src/rosy_games/test/test_games_boundaries.py` — `host/loop.py`에 `cv2`/`rclpy`/`rosy_core`/`rosy_fleet` 없음

한 틱:

```text
obs = observer.observe()
state = game.step(obs)
twists = policy.act(obs, state)
commands = gate(twists, obs, state, field)
if commands.estop:
    양쪽 estop()
else:
    각 client.teleop(twist)
```

가짜 클라이언트가 `teleop` 호출을 기록한다. 시나리오:

1. 킥오프 준비 안 됨 → teleop 모두 0
2. 인플레이 추적 → linear > 0 인 쪽이 있다
3. `observe()`가 한쪽 로봇을 빼면 HOLD, 양쪽 0
4. 가짜 클라이언트 하나가 `teleop`에서 예외 → 루프가 **양쪽** `estop()` (CommandSet.estop=True)

`PlayerClient` 프로토콜은 이 Task에서 `host/transport.py`에 시그니처만 두거나 `loop.py` 옆에 둔다. HTTP는 Task 7.

- [x] **Step 1–5: TDD, commit**

```
git commit -m "feat(games): run the match loop against fake robots"
```

---

### Task 7: `HttpPlayerClient` — mode / teleop / stop만

**Files:**
- Create: `src/rosy_games/rosy_games/host/robots.py`
- Create: `src/rosy_games/rosy_games/host/transport.py`
- Create: `src/rosy_games/test/test_transport.py`
- Modify: `package.xml` — `exec_depend` `python3-httpx`, `python3-websockets`, `python3-yaml`

`PlayerClient`: `robot_id`, `set_manual()`, `teleop(linear, angular)`, `estop()`.

HTTP 경로는 API Ref §5.5 / §6.1만:

- `POST /api/v1/mode` `{"mode": "MANUAL"}`
- `POST /api/v1/teleop` `{"linear": ..., "angular": ...}` (1단계 REST. WS는 같은 워치독이라 나중에 바꿔도 됨)
- `POST /api/v1/safety/stop`

follow / navigation / swarm 문자열은 이 파일에 없어야 한다. 시험은 `httpx.MockTransport` 또는 기록용 핸들러.

4xx면 예외를 올려 루프가 양쪽 estop 하게 한다.

- [x] **Step 1–5: TDD, commit**

```
git commit -m "feat(games): talk to CORE with mode, teleop, and stop only"
```

---

### Task 8: `match.yaml`과 CLI

**Files:**
- Create: `src/rosy_games/config/match.yaml` (설계 §3.5, 토큰 빈 문자열)
- Create: `src/rosy_games/rosy_games/cli.py`
- Modify: `src/rosy_games/setup.py` entry point `rosy_games=rosy_games.cli:main`
- Create: `src/rosy_games/test/test_cli.py`

CLI:

```
python -m rosy_games.cli match --config src/rosy_games/config/match.yaml --dry-run
```

`--dry-run`은 YAML을 읽고 `Field`+두 엔드포인트를 만들고 네트워크를 열지 않는다. 시험은 dry-run만.

`.gitignore`에 `src/rosy_games/config/match.local.yaml`을 넣는다. 실기 URL은 로컬 오버라이드.

- [x] **Step 1–5: TDD, commit**

```
git commit -m "feat(games): load a match config without touching the robots"
```

---

### Task 9: 문서·경계 시험 마무리 (overhead는 열지 않음)

**Files:**
- Modify: `src/rosy_games/AGENTS.md`, `progress.md`, `logs.md`
- Modify: `src/rosy_games/test/test_games_boundaries.py` — host 중 `overhead.py`만 cv2 허용, 나머지 host는 금지
- Modify: `docs/plans/2026-09-17-robot-soccer-game-host-design.md` §9 게이트를 이 계획이 닫은 항목으로 갱신
- Run: `python tools/harness/rosy_harness.py generate`

`host/overhead.py`와 `field/homography.py`는 **만들지 않는다.** 천장 카메라 실측이 다음 계획이다. LOCAL GO의 정의는:

```
python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q
```

카메라 없이 통과. `progress.md` LOCAL을 그 명령·증거로 GO. DEVICE/FIELD는 PARKED 유지.

- [x] **Step 1: 전체 시험**

Expected: PASS, `isaac` 경로 없음, Dockerfile에 `rosy_games` 없음

- [x] **Step 2: harness generate, `test/test_harness_contracts.py` PASS**

- [x] **Step 3: Commit**

```
git commit -m "docs(games): mark LOCAL host complete without overhead camera"
```

---

## 실행 순서

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. 6은 4·5 없이 가짜 정책으로 건너뛰지 않는다. 7은 6의 프로토콜을 구현한다.

현장 한 대 공 밀기는 이 파일이 닫은 뒤, Device 정지·워치독 증거가 있는 다음 계획이다.
