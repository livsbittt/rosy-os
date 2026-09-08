# Swarm Formation Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fleet 서버 없이 N대 로봇을 대형으로 묶는다 — `rosy_fleet` 씨앗 패키지(대형 기하·슬롯 배정·릴레이·FOR-004 세션·CLI), `gz_multi core:=true`, 시뮬 계측 스크립트.

**Architecture:** 로봇 쪽 `rosy_core` 는 건드리지 않고 그 REST/WS 계약만 소비한다. 모든 대형은 팔로워가 이미 받는 `(distance, lateral)` 오프셋으로 환원되고, 릴레이는 리더 pose 프레임을 바꾸지 않고 팔로워 reference 소켓에 그대로 전달한다. 대형 전체 HOLD 는 릴레이를 멈춰 각 팔로워의 SWM-004 가 발동하게 하는 것으로 만든다(D-35 후보). 설계: `docs/plans/2026-09-08-swarm-formation-slice-design.md`.

**Tech Stack:** Python 3.12, pydantic(`rosy_core.protocol.schemas` 재사용), httpx 0.28, websockets 17, PyYAML, asyncio, pytest(비동기는 `asyncio.run` 헬퍼로, pytest-asyncio 없음), ament_python, ROS 2 Jazzy launch (`gz_multi`).

**Branch:** `feat/swarm-formation-slice` (main 기반). 커밋 메시지는 이 저장소의 관례대로 `type(scope): 무엇을 왜` 한 줄 + 본문, 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

**Windows 에서 실행:** 이 계획의 단위 테스트는 전부 ROS 없이 돈다. 명령은 저장소 루트에서 `python -m pytest src/rosy_fleet/test -v` 형태다. Task 12(런치 테스트)와 Task 14(시뮬 계측)만 ROS 환경이 필요하다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `src/rosy_fleet/package.xml`, `setup.py`, `setup.cfg`, `resource/rosy_fleet` | ament_python 패키지 뼈대. 콘솔 스크립트 `rosy_fleet` |
| `src/rosy_fleet/rosy_fleet/__init__.py` | 버전 문자열만 |
| `src/rosy_fleet/rosy_fleet/formation/geometry.py` | `Formation`, `SlotOffset`, `slots()`, `slot_world_position()`, `MIN_SPACING`. 순수 함수 |
| `src/rosy_fleet/rosy_fleet/formation/assignment.py` | `SlotAssigner` 프로토콜, `GreedyDistanceAssigner`. 순수 함수 |
| `src/rosy_fleet/rosy_fleet/swarm/robots.py` | `RobotEndpoint`, `load_robots()`, `write_robots()`, `ws_url()` |
| `src/rosy_fleet/rosy_fleet/swarm/transport.py` | `RobotClient` 프로토콜, `RobotApiError`, `HttpRobotClient`(httpx + websockets) |
| `src/rosy_fleet/rosy_fleet/swarm/relay.py` | `Relay`, `RelayStats`: 리더 소켓 1 → 팔로워 소켓 N, pause/resume, 계측 |
| `src/rosy_fleet/rosy_fleet/swarm/session.py` | `FormationSession`, `FormationSpec`, `HoldPolicy`, `SessionState`, FOR-004 |
| `src/rosy_fleet/rosy_fleet/cli.py` | `rosy_fleet relay` / `rosy_fleet formation` |
| `src/rosy_fleet/test/conftest.py` | `src/rosy_core` 를 sys.path 에 얹어 colcon 없이 스키마 import |
| `src/rosy_fleet/test/fakes.py` | `FakeRobot`, `FakeSink`, `FakeRelay`, `run()` 헬퍼 — 릴레이·세션 테스트가 공유 |
| `src/rosy_fleet/test/test_*.py` | geometry, assignment, robots, transport, relay, session, boundaries |
| `src/rosy_gz_sim/launch/gz_multi.launch.py` | `core:=true`, `api_port_base:=8080` — 로봇별 `rosy_core` + `robots.yaml` 생성 |
| `src/rosy_gz_sim/test/test_gz_multi_core.py` | 런치 `OpaqueFunction` 단위 실행 (ROS 환경) |
| `src/rosy_gz_sim/scripts/swarm_bench.py`, `CMakeLists.txt` | 4개 시나리오 계측 → CSV |
| `.github/workflows/ci.yml` | `rosy_fleet` 테스트 스텝, flake8 대상 추가 |
| `docs/plans/AGENTS.md` | 이 계획 인덱스 |

---

### Task 1: `rosy_fleet` 패키지 뼈대와 테스트 부트스트랩

**Files:**
- Create: `src/rosy_fleet/package.xml`
- Create: `src/rosy_fleet/setup.py`
- Create: `src/rosy_fleet/setup.cfg`
- Create: `src/rosy_fleet/resource/rosy_fleet` (빈 파일)
- Create: `src/rosy_fleet/rosy_fleet/__init__.py`
- Create: `src/rosy_fleet/rosy_fleet/formation/__init__.py` (빈 파일)
- Create: `src/rosy_fleet/rosy_fleet/swarm/__init__.py` (빈 파일)
- Create: `src/rosy_fleet/test/conftest.py`
- Create: `src/rosy_fleet/test/test_package.py`

- [ ] **Step 1: 실패하는 테스트 — 패키지가 import 되고 `rosy_core` 스키마에 닿는다**

`src/rosy_fleet/test/test_package.py`:

```python
"""패키지 뼈대. rosy_fleet 이 import 되고, D-18 대로 rosy_core 스키마를 재사용할 수 있다."""


def test_package_imports_and_reaches_rosy_core_schemas():
    import rosy_fleet
    from rosy_core.protocol.schemas import SwarmFollowParams

    assert rosy_fleet.__version__ == "0.1.0"
    assert SwarmFollowParams(target_robot_id="rosy_01").distance == 0.5
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_package.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rosy_fleet'`

- [ ] **Step 3: conftest — colcon 없이 두 패키지를 sys.path 에 얹는다**

`src/rosy_fleet/test/conftest.py`:

```python
"""colcon install 없이 pytest 를 돌린다 (Windows/CI).

`rosy_fleet` 은 `rosy_core.protocol.schemas` 를 import 한다(D-18). 두 패키지 모두
소스 트리에서 바로 찾도록 sys.path 를 잡는다 — 루트 `test/conftest.py` 가
`deploy/release` 에 하는 것과 같은 방식이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]

for path in (SRC / "rosy_fleet", SRC / "rosy_core"):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)
```

- [ ] **Step 4: 패키지 파일들**

`src/rosy_fleet/rosy_fleet/__init__.py`:

```python
"""rosy_fleet — Fleet 쪽 씨앗: 대형 기하·슬롯 배정·참조 스트림 릴레이·FOR-004 세션.

Fleet 서버 본체(Phase 4)는 아직 없다. 여기 있는 것은 로봇 계약(API Ref)만
소비하며 `rosy_core` 는 스키마 재사용을 위해서만 import 한다(D-18).
"""

__version__ = "0.1.0"
```

`src/rosy_fleet/rosy_fleet/formation/__init__.py`, `src/rosy_fleet/rosy_fleet/swarm/__init__.py`: 빈 파일.

`src/rosy_fleet/resource/rosy_fleet`: 빈 파일.

`src/rosy_fleet/package.xml`:

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>rosy_fleet</name>
  <version>0.1.0</version>
  <description>ROSY FLEET seed — formation geometry, slot assignment, reference stream relay, FOR-004 session (ROSY-FLEET-SRS-001 FOR-001~004)</description>
  <maintainer email="dev@rosy.local">rosy</maintainer>
  <license>Apache-2.0</license>

  <!-- D-18: 프로토콜 스키마는 rosy_core 의 것을 import 한다. ROS 런타임 의존은 없다. -->
  <exec_depend>rosy_core</exec_depend>
  <exec_depend>python3-httpx</exec_depend>
  <exec_depend>python3-websockets</exec_depend>
  <exec_depend>python3-yaml</exec_depend>

  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

`src/rosy_fleet/setup.py`:

```python
from setuptools import find_packages, setup

package_name = 'rosy_fleet'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='rosy',
    maintainer_email='dev@rosy.local',
    description='ROSY FLEET seed: formation geometry, slot assignment, relay, FOR-004 session',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'rosy_fleet=rosy_fleet.cli:main',
        ],
    },
)
```

`src/rosy_fleet/setup.cfg`:

```ini
[develop]
script_dir=$base/lib/rosy_fleet
[install]
install_scripts=$base/lib/rosy_fleet
```

- [ ] **Step 5: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_package.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: 커밋**

```bash
git add src/rosy_fleet
git commit -m "feat(fleet): seed the rosy_fleet package that will hold what joins robots together

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: 대형 기하 — `slots()` 와 `slot_world_position()`

**Files:**
- Create: `src/rosy_fleet/rosy_fleet/formation/geometry.py`
- Create: `src/rosy_fleet/test/test_geometry.py`

- [ ] **Step 1: 실패하는 테스트 — 6종 대형의 손계산 값**

`src/rosy_fleet/test/test_geometry.py`:

```python
"""FOR-001 대형 → 슬롯 오프셋. 좌표 규약은 rosy_core.navigation.swarm.follow_goal 과 같다:
distance 는 리더 뒤(+), lateral 은 리더 왼쪽(+). 리더는 슬롯 0 이며 목록에 없다."""

import math

import pytest

from rosy_fleet.formation.geometry import (
    MIN_SPACING,
    Formation,
    FormationError,
    SlotOffset,
    slot_world_position,
    slots,
)


def _close(a: SlotOffset, b: tuple[float, float]) -> bool:
    return math.isclose(a.distance, b[0], abs_tol=1e-9) and math.isclose(a.lateral, b[1], abs_tol=1e-9)


def test_column_stacks_behind_the_leader():
    got = slots(Formation.COLUMN, 3, 0.5)
    assert [(s.distance, s.lateral) for s in got] == [(0.5, 0.0), (1.0, 0.0), (1.5, 0.0)]


def test_line_alternates_left_then_right_beside_the_leader():
    got = slots(Formation.LINE, 3, 0.5)
    assert [(s.distance, s.lateral) for s in got] == [(0.0, 0.5), (0.0, -0.5), (0.0, 1.0)]


def test_v_opens_behind_the_leader_alternating_sides():
    got = slots(Formation.V, 2, 0.5)
    assert [(s.distance, s.lateral) for s in got] == [(0.5, 0.5), (0.5, -0.5)]


def test_grid_fills_rows_of_grid_cols_with_the_leader_at_front_left():
    got = slots(Formation.GRID, 3, 0.5, grid_cols=2)
    # 인덱스 0 은 리더 (row 0, col 0). k=1 → (0, col 1) 오른쪽, k=2 → 다음 행 왼쪽, k=3 → 그 오른쪽.
    assert [(s.distance, s.lateral) for s in got] == [(0.0, -0.5), (0.5, 0.0), (0.5, -0.5)]


def test_circle_puts_the_leader_on_the_ring_and_keeps_the_chord_equal_to_spacing():
    s = 0.5
    got = slots(Formation.CIRCLE, 3, s)
    r = s / (2 * math.sin(math.pi / 4))
    assert _close(got[0], (r, r))            # θ = 90°
    assert _close(got[1], (2 * r, 0.0))      # θ = 180°
    assert _close(got[2], (r, -r))           # θ = 270°
    # 인접 현 길이가 spacing 이다 — 두 로봇 사이 직선 거리가 안전 하한을 넘어야 하므로.
    ring = [(0.0, 0.0)] + [(p.distance, p.lateral) for p in got]
    for a, b in zip(ring, ring[1:] + ring[:1]):
        assert math.isclose(math.dist(a, b), s, abs_tol=1e-9)


def test_follow_is_exactly_one_slot_behind():
    assert slots(Formation.FOLLOW, 1, 0.7) == [SlotOffset(0.7, 0.0)]


@pytest.mark.parametrize("bad", [MIN_SPACING - 0.01, 0.0, -1.0, float("inf"), float("nan")])
def test_spacing_below_the_floor_is_refused(bad):
    with pytest.raises(FormationError):
        slots(Formation.COLUMN, 2, bad)


def test_follow_refuses_more_than_one_follower():
    with pytest.raises(FormationError):
        slots(Formation.FOLLOW, 2, 0.6)


@pytest.mark.parametrize("followers", [0, -1])
def test_a_formation_needs_at_least_one_follower(followers):
    with pytest.raises(FormationError):
        slots(Formation.LINE, followers, 0.6)


def test_grid_refuses_zero_columns():
    with pytest.raises(FormationError):
        slots(Formation.GRID, 2, 0.6, grid_cols=0)


def test_slot_world_position_matches_follow_goal_convention():
    # 리더 (1, 2) 가 +y 를 본다. 뒤 1 m 는 (1, 1), 왼쪽 1 m 는 -x 쪽 (0, 2).
    behind = slot_world_position(SlotOffset(1.0, 0.0), 1.0, 2.0, math.pi / 2)
    left = slot_world_position(SlotOffset(0.0, 1.0), 1.0, 2.0, math.pi / 2)
    assert math.isclose(behind[0], 1.0, abs_tol=1e-9) and math.isclose(behind[1], 1.0, abs_tol=1e-9)
    assert math.isclose(left[0], 0.0, abs_tol=1e-9) and math.isclose(left[1], 2.0, abs_tol=1e-9)
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rosy_fleet.formation.geometry'`

- [ ] **Step 3: 구현**

`src/rosy_fleet/rosy_fleet/formation/geometry.py`:

```python
"""rosy_fleet.formation.geometry — FOR-001 대형을 슬롯 오프셋으로 (순수 함수).

팔로워는 리더 heading 기준 `(distance, lateral)` 오프셋을 받는다
(`rosy_core.navigation.swarm.follow_goal`). 모든 정적 대형은 그 오프셋의 집합이므로
로봇 계약을 바꾸지 않고 여기서 끝난다. 이 모듈은 전송도 로봇도 모른다 — 입력은
숫자, 출력은 숫자다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable

#: 두 로봇이 가장 가까워지는 거리의 하한. LINE 과 GRID 앞줄은 팔로워를 리더와 나란히
#: 세우므로 이 값이 그대로 로봇 사이 거리다. Nav2 는 목표점이 아니라 **팔로워의
#: footprint** 로 충돌을 검사하므로 하한은
#:   inflation_radius + 리더 외접반경 + 팔로워 외접반경 + footprint_padding
#:   = 0.15 + 0.085 + 0.085 + 0.03 ≈ 0.35 m
#: 이다 (`src/rosy_navigation/params/nav2_params.yaml`: footprint 반폭 6 cm(한 변 12 cm) 정사각 → 외접반경
#: 0.085, inflation_radius 0.15, global costmap footprint_padding 0.03). 0.4 는 그 위로
#: 약 5 cm 여유다 — 넉넉하지 않다. Nav2 파라미터가 바뀌면 이 식으로 다시 계산한다.
MIN_SPACING = 0.4
DEFAULT_SPACING = 0.6

Point = tuple[float, float]


class Formation(str, Enum):
    FOLLOW = "FOLLOW"
    COLUMN = "COLUMN"
    LINE = "LINE"
    V = "V"
    GRID = "GRID"
    CIRCLE = "CIRCLE"


class FormationError(ValueError):
    """대형을 만들 수 없는 파라미터."""


@dataclass(frozen=True)
class SlotOffset:
    """리더 heading 기준 슬롯. `distance` 는 리더 뒤(+), `lateral` 은 리더 왼쪽(+), m."""

    distance: float
    lateral: float


def _side(k: int) -> float:
    """k 번째 팔로워의 좌우. 홀수는 왼쪽(+), 짝수는 오른쪽(−)."""
    return 1.0 if k % 2 == 1 else -1.0


def _rank(k: int) -> int:
    """좌우 교대에서 k 번째 팔로워가 리더에서 몇 칸 떨어지는지."""
    return math.ceil(k / 2)


def _column(n: int, s: float, _cols: int) -> list[SlotOffset]:
    return [SlotOffset(k * s, 0.0) for k in range(1, n + 1)]


def _line(n: int, s: float, _cols: int) -> list[SlotOffset]:
    return [SlotOffset(0.0, _side(k) * _rank(k) * s) for k in range(1, n + 1)]


def _v(n: int, s: float, _cols: int) -> list[SlotOffset]:
    return [SlotOffset(_rank(k) * s, _side(k) * _rank(k) * s) for k in range(1, n + 1)]


def _grid(n: int, s: float, cols: int) -> list[SlotOffset]:
    # 리더가 인덱스 0 (앞줄 왼쪽 끝). 팔로워 k 는 인덱스 k. 열은 오른쪽(−)으로 채운다.
    return [SlotOffset((k // cols) * s, -(k % cols) * s) for k in range(1, n + 1)]


def _circle(n: int, s: float, _cols: int) -> list[SlotOffset]:
    # 리더를 포함한 n+1 점을 원 위에 등간격으로. 인접 점 사이의 **현** 길이가 s 다 —
    # 두 로봇 사이의 직선 거리가 하한을 넘어야 하기 때문이다(호 길이가 아니다).
    total = n + 1
    r = s / (2.0 * math.sin(math.pi / total))
    # 리더는 각도 0 에 있고 원의 중심은 리더 뒤 r 에 있다. 점 θ 의 리더 기준 좌표:
    # 뒤로 r(1 − cos θ), 왼쪽으로 r sin θ.
    out = []
    for k in range(1, n + 1):
        theta = 2.0 * math.pi * k / total
        out.append(SlotOffset(r - r * math.cos(theta), r * math.sin(theta)))
    return out


_GENERATORS: dict[Formation, Callable[[int, float, int], list[SlotOffset]]] = {
    Formation.FOLLOW: _column,
    Formation.COLUMN: _column,
    Formation.LINE: _line,
    Formation.V: _v,
    Formation.GRID: _grid,
    Formation.CIRCLE: _circle,
}


def slots(formation: Formation, followers: int, spacing: float, *,
          grid_cols: int = 2) -> list[SlotOffset]:
    """`followers` 명의 팔로워 슬롯. 리더는 슬롯 0 이며 반환 목록에 들어가지 않는다."""
    if not math.isfinite(spacing) or spacing < MIN_SPACING:
        raise FormationError(
            f"spacing {spacing} is below the floor {MIN_SPACING} m — the follower's goal "
            "would sit inside the leader's inflated footprint")
    if followers < 1:
        raise FormationError("a formation needs at least one follower")
    if formation is Formation.FOLLOW and followers != 1:
        raise FormationError("FOLLOW is a single follower; use COLUMN for more")
    if grid_cols < 1:
        raise FormationError("grid_cols must be at least 1")
    return _GENERATORS[Formation(formation)](followers, spacing, grid_cols)


def slot_world_position(offset: SlotOffset, x: float, y: float, yaw: float) -> Point:
    """리더 pose `(x, y, yaw)` 에서 슬롯의 월드 좌표. `follow_goal` 과 같은 식이다."""
    heading = (math.cos(yaw), math.sin(yaw))
    left = (-math.sin(yaw), math.cos(yaw))
    return (
        x - offset.distance * heading[0] + offset.lateral * left[0],
        y - offset.distance * heading[1] + offset.lateral * left[1],
    )
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_geometry.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/rosy_fleet/rosy_fleet/formation/geometry.py src/rosy_fleet/test/test_geometry.py
git commit -m "feat(fleet): express every formation as the offsets the follower already accepts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: 슬롯 배정 — `GreedyDistanceAssigner`

**Files:**
- Create: `src/rosy_fleet/rosy_fleet/formation/assignment.py`
- Create: `src/rosy_fleet/test/test_assignment.py`

- [ ] **Step 1: 실패하는 테스트**

`src/rosy_fleet/test/test_assignment.py`:

```python
"""FOR-002 슬롯 배정. 그리디는 최적이 아니다 — 테스트가 고정하는 것은 전단사, 입력
순서 불변, 2대 비교차, 개수 불일치 거절이다. Hungarian 은 같은 프로토콜로 들어온다."""

import pytest

from rosy_fleet.formation.assignment import AssignmentError, GreedyDistanceAssigner, SlotAssigner


def test_the_greedy_assigner_satisfies_the_protocol():
    assert isinstance(GreedyDistanceAssigner(), SlotAssigner)


def test_two_robots_do_not_cross():
    robots = {"a": (0.0, 0.0), "b": (1.0, 0.0)}
    slots = [(0.0, 1.0), (1.0, 1.0)]
    assert GreedyDistanceAssigner().assign(robots, slots) == {"a": 0, "b": 1}


def test_the_assignment_is_a_bijection():
    robots = {"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 3.0)}
    slots = [(2.9, 0.1), (0.1, 2.9), (0.1, 0.1)]
    got = GreedyDistanceAssigner().assign(robots, slots)
    assert sorted(got) == ["a", "b", "c"]
    assert sorted(got.values()) == [0, 1, 2]
    assert got == {"a": 2, "b": 0, "c": 1}


def test_input_order_does_not_change_the_result():
    robots = {"a": (0.0, 0.0), "b": (3.0, 0.0), "c": (0.0, 3.0)}
    slots = [(2.9, 0.1), (0.1, 2.9), (0.1, 0.1)]
    forward = GreedyDistanceAssigner().assign(robots, slots)
    backward = GreedyDistanceAssigner().assign(dict(reversed(list(robots.items()))), slots)
    assert forward == backward


def test_ties_break_deterministically():
    # 두 로봇이 두 슬롯에서 같은 거리다. 어느 쪽이든 되지만 매번 같아야 한다.
    robots = {"a": (0.0, 0.0), "b": (0.0, 0.0)}
    slots = [(1.0, 0.0), (-1.0, 0.0)]
    first = GreedyDistanceAssigner().assign(robots, slots)
    assert all(GreedyDistanceAssigner().assign(robots, slots) == first for _ in range(5))
    assert sorted(first.values()) == [0, 1]


def test_robot_and_slot_counts_must_match():
    with pytest.raises(AssignmentError):
        GreedyDistanceAssigner().assign({"a": (0.0, 0.0)}, [(0.0, 1.0), (1.0, 1.0)])
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_assignment.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`src/rosy_fleet/rosy_fleet/formation/assignment.py`:

```python
"""rosy_fleet.formation.assignment — FOR-002 슬롯 배정 (순수 함수).

거리 기반 그리디가 v1 이다. FOR-002 는 알고리즘을 인터페이스 뒤에 두어 Hungarian
으로 바꿀 수 있어야 한다고 했으므로, 인터페이스가 먼저고 구현은 그중 하나다.
"""

from __future__ import annotations

import math
from typing import Mapping, Protocol, Sequence, runtime_checkable

from rosy_fleet.formation.geometry import Point


class AssignmentError(ValueError):
    """배정할 수 없는 입력."""


@runtime_checkable
class SlotAssigner(Protocol):
    def assign(self, robots: Mapping[str, Point], slots: Sequence[Point]) -> dict[str, int]:
        """`robot_id → slot index`. 전단사여야 한다."""
        ...


class GreedyDistanceAssigner:
    """모든 (로봇, 슬롯) 쌍을 거리 오름차순으로 훑어, 둘 다 비어 있으면 짝짓는다.

    최적은 아니지만 결정적이다: 거리가 같으면 robot_id, 그다음 슬롯 번호로 가른다.
    그래서 입력 dict 의 순서가 결과를 바꾸지 않는다.
    """

    def assign(self, robots: Mapping[str, Point], slots: Sequence[Point]) -> dict[str, int]:
        if len(robots) != len(slots):
            raise AssignmentError(
                f"{len(robots)} robots for {len(slots)} slots — the formation must have one "
                "slot per follower")
        pairs = sorted(
            (math.dist(pos, slots[j]), robot_id, j)
            for robot_id, pos in robots.items()
            for j in range(len(slots))
        )
        taken_robots: set[str] = set()
        taken_slots: set[int] = set()
        out: dict[str, int] = {}
        for _, robot_id, j in pairs:
            if robot_id in taken_robots or j in taken_slots:
                continue
            out[robot_id] = j
            taken_robots.add(robot_id)
            taken_slots.add(j)
        return out
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_assignment.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/rosy_fleet/rosy_fleet/formation/assignment.py src/rosy_fleet/test/test_assignment.py
git commit -m "feat(fleet): assign slots by distance behind an interface Hungarian can take over

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: 로봇 목록 — `robots.yaml` 로더와 WS URL

> **리뷰 후 갱신 (2026-09-08):** 아래 Step 3 코드는 첫 판이다. Task 4 리뷰가 잡은 것 — `UnicodeDecodeError`
> 는 `OSError` 가 아니라 새어 나감, 스킴 없는 `base_url` 이 `ws:///...` 를 만듦, YAML 이 `token: 01234567`
> 을 8진 정수로 읽어 `str()` 이 다른 비밀을 만듦, `write_robots` 가 로더가 거절할 파일을 씀, 대문자
> `HTTPS` 가 `ws` 로 떨어져 토큰이 평문으로 나감 — 은 커밋 `b160042` 와 그 다음 fix 커밋에서 고쳤다.
> 정본은 `src/rosy_fleet/rosy_fleet/swarm/robots.py` 와 `test/test_robots.py` 다. 실행 전 그 파일을 읽을 것.


**Files:**
- Create: `src/rosy_fleet/rosy_fleet/swarm/robots.py`
- Create: `src/rosy_fleet/test/test_robots.py`

- [ ] **Step 1: 실패하는 테스트**

`src/rosy_fleet/test/test_robots.py`:

```python
"""robots.yaml — 오케스트레이터가 아는 로봇 목록. 토큰은 로봇마다 다르다(D-30)."""

import pytest

from rosy_fleet.swarm.robots import RobotEndpoint, RobotsFileError, load_robots, write_robots, ws_url


def test_load_reads_every_field_and_strips_the_trailing_slash(tmp_path):
    p = tmp_path / "robots.yaml"
    p.write_text(
        "robots:\n"
        "  - robot_id: rosy_01\n"
        "    base_url: http://10.0.0.11:8080/\n"
        "    token: tok-1\n"
        "  - robot_id: rosy_02\n"
        "    base_url: http://10.0.0.12:8080\n"
        "    token: tok-2\n",
        encoding="utf-8",
    )
    assert load_robots(p) == [
        RobotEndpoint("rosy_01", "http://10.0.0.11:8080", "tok-1"),
        RobotEndpoint("rosy_02", "http://10.0.0.12:8080", "tok-2"),
    ]


def test_write_then_load_round_trips(tmp_path):
    p = tmp_path / "robots.yaml"
    robots = [RobotEndpoint("rosy_01", "http://127.0.0.1:8080", "a"),
              RobotEndpoint("rosy_02", "http://127.0.0.1:8081", "b")]
    write_robots(p, robots)
    assert load_robots(p) == robots


@pytest.mark.parametrize("body", [
    "",
    "robots: []\n",
    "robots:\n  - robot_id: rosy_01\n    base_url: http://x:8080\n",           # token 없음
    "robots:\n  - robot_id: rosy_01\n    token: t\n",                          # base_url 없음
    "robots:\n  - base_url: http://x:8080\n    token: t\n",                    # robot_id 없음
    "robots:\n  - {robot_id: a, base_url: http://x, token: t}\n"
    "  - {robot_id: a, base_url: http://y, token: t}\n",                       # 중복
])
def test_malformed_files_are_refused(tmp_path, body):
    p = tmp_path / "robots.yaml"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(RobotsFileError):
        load_robots(p)


def test_ws_url_switches_scheme_and_carries_the_token():
    assert ws_url("http://10.0.0.11:8080", "/ws/swarm/pose", "t") == "ws://10.0.0.11:8080/ws/swarm/pose?token=t"
    assert ws_url("https://rosy-01.local", "/ws/events", "t") == "wss://rosy-01.local/ws/events?token=t"


def test_ws_url_appends_extra_query():
    got = ws_url("http://h:1", "/ws/events", "t", types="nav.*,swarm.*")
    assert got == "ws://h:1/ws/events?token=t&types=nav.%2A%2Cswarm.%2A"
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_robots.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`src/rosy_fleet/rosy_fleet/swarm/robots.py`:

```python
"""rosy_fleet.swarm.robots — 오케스트레이터가 아는 로봇 목록 (robots.yaml).

토큰은 로봇마다 다르다(D-30: 장치 로컬 토큰). 참조 소켓과 swarm/follow 는 operator
이상이어야 한다(D-31) — 파일에 든 토큰은 그 역할이어야 하며 여기서는 형식만 본다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

import yaml


class RobotsFileError(ValueError):
    """robots.yaml 을 읽을 수 없다."""


@dataclass(frozen=True)
class RobotEndpoint:
    robot_id: str
    base_url: str   # 끝 슬래시 없음
    token: str


_REQUIRED = ("robot_id", "base_url", "token")


def load_robots(path: Path) -> list[RobotEndpoint]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rows = data.get("robots") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RobotsFileError(f"{path}: needs a non-empty 'robots' list")
    seen: set[str] = set()
    out: list[RobotEndpoint] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RobotsFileError(f"{path}: robots[{i}] is not a mapping")
        for key in _REQUIRED:
            if not row.get(key):
                raise RobotsFileError(f"{path}: robots[{i}] is missing '{key}'")
        robot_id = str(row["robot_id"])
        if robot_id in seen:
            raise RobotsFileError(f"{path}: duplicate robot_id {robot_id!r}")
        seen.add(robot_id)
        out.append(RobotEndpoint(robot_id, str(row["base_url"]).rstrip("/"), str(row["token"])))
    return out


def write_robots(path: Path, robots: list[RobotEndpoint]) -> None:
    """`gz_multi core:=true` 가 시뮬 로봇 목록을 써 주는 데 쓴다."""
    Path(path).write_text(
        yaml.safe_dump({"robots": [asdict(r) for r in robots]}, sort_keys=False),
        encoding="utf-8",
    )


def ws_url(base_url: str, path: str, token: str, **query: str) -> str:
    """REST base_url → 같은 호스트의 WS URL. 토큰은 쿼리로 간다 (API Ref §6)."""
    scheme, _, host = base_url.partition("://")
    ws_scheme = "wss" if scheme == "https" else "ws"
    params = {"token": token, **query}
    return f"{ws_scheme}://{host}{path}?{urlencode(params)}"
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_robots.py -v`
Expected: PASS (리뷰 후 추가된 테스트를 포함해 전부)

- [ ] **Step 5: 커밋**

```bash
git add src/rosy_fleet/rosy_fleet/swarm/robots.py src/rosy_fleet/test/test_robots.py
git commit -m "feat(fleet): read the robot list the orchestrator will drive, one token per robot

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: 전송 — `RobotClient` 프로토콜과 `HttpRobotClient`

> **리뷰 후 갱신 (2026-09-08):** 아래 Step 3 코드는 첫 판이다. Task 5 리뷰가 잡은 것 — 로봇이 4401/4403 으로
> 거부한 소켓이 정상 종료와 구분되지 않아 잘못된 토큰이면 릴레이가 영원히 조용히 재시도함, 200 응답이 JSON
> 객체가 아닐 때 bare 예외, 프레임 변환 로직이 테스트 불가 — 은 그 다음 fix 커밋에서 고쳤다: **거부(4401/4403,
> 핸드셰이크 거절)는 `RobotApiError`(code `WS_<code>`) 로 올라오고, 그 외 종료는 조용히 끝난다.** 와이어 사실
> (Task 7 리뷰): 로봇은 `accept()` 전에 close 하므로 실제로 보이는 코드는 `WS_403` 이다 — 4401/4403 분기는
> accept-then-close 하는 로봇을 위한 것이고, 핸드셰이크 403 경로가 테스트된다. 순수 변환은
> `_as_text`/`_as_event` 로 나뉘어 테스트된다. 정본은 `src/rosy_fleet/rosy_fleet/swarm/transport.py` 다.
> Task 7 의 릴레이는 그 예외를 받아 `RelayStats.leader_last_error` 에 남기고 재연결을 계속한다(아래 반영).


**Files:**
- Create: `src/rosy_fleet/rosy_fleet/swarm/transport.py`
- Create: `src/rosy_fleet/test/test_transport.py`

REST 는 httpx `MockTransport` 로 검증한다. WS 는 `websockets` 를 실제로 열지 않고,
URL 조립과 프레임 변환만 검증한다 — 소켓 위의 동작(재연결, pause)은 Task 6/7 이
가짜 클라이언트로 검증한다.

- [ ] **Step 1: 실패하는 테스트**

`src/rosy_fleet/test/test_transport.py`:

```python
"""HttpRobotClient — 로봇 REST 를 부르는 유일한 곳. 에러 본문은 ERR-101 형식이다."""

import asyncio
import json

import httpx
import pytest

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.swarm.robots import RobotEndpoint
from rosy_fleet.swarm.transport import HttpRobotClient, RobotApiError, RobotClient

EP = RobotEndpoint("rosy_02", "http://robot:8080", "op-token")


def run(coro):
    return asyncio.run(coro)


def _client(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=EP.base_url)
    return HttpRobotClient(EP, http=http)


def test_it_satisfies_the_protocol():
    assert isinstance(_client(lambda r: httpx.Response(200, json={})), RobotClient)


def test_follow_posts_the_params_with_a_bearer_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"role": "follower", "active": True})

    params = SwarmFollowParams(target_robot_id="rosy_01", distance=0.6, lateral=-0.6,
                               max_speed=0.15, stream_timeout_ms=1000)
    got = run(_client(handler).follow(params))
    assert got["active"] is True
    assert seen["path"] == "/api/v1/swarm/follow"
    assert seen["auth"] == "Bearer op-token"
    assert seen["body"]["target_robot_id"] == "rosy_01"
    assert seen["body"]["lateral"] == -0.6
    assert seen["body"]["source"] == "fleet"


def test_an_error_body_becomes_a_robot_api_error_with_the_robots_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": {"code": "DOCKING_ACTIVE",
                                                   "message": "a docking run owns navigation",
                                                   "detail": None}})

    with pytest.raises(RobotApiError) as exc:
        run(_client(handler).follow(SwarmFollowParams(target_robot_id="rosy_01")))
    assert exc.value.robot_id == "rosy_02"
    assert exc.value.status == 409
    assert exc.value.code == "DOCKING_ACTIVE"


def test_a_non_json_error_still_raises_with_an_http_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    with pytest.raises(RobotApiError) as exc:
        run(_client(handler).state())
    assert exc.value.code == "HTTP_502"


@pytest.mark.parametrize("method, path", [
    ("state", "/api/v1/robot/state"),
    ("swarm_state", "/api/v1/swarm/state"),
    ("swarm_cancel", "/api/v1/swarm/cancel"),
    ("navigation_cancel", "/api/v1/navigation/cancel"),
])
def test_each_call_hits_its_route(method, path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx.Response(200, json={"ok": True})

    assert run(getattr(_client(handler), method)()) == {"ok": True}
    assert seen["path"] == path
    assert seen["method"] == ("GET" if method.endswith("state") else "POST")


def test_navigation_goal_posts_x_y_yaw():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["path"] = request.url.path
        return httpx.Response(200, json={"accepted": True})

    run(_client(handler).navigation_goal(1.0, 2.0, 0.5))
    assert seen["path"] == "/api/v1/navigation/goal"
    assert seen["body"] == {"x": 1.0, "y": 2.0, "yaw": 0.5}


def test_socket_urls_point_at_the_robot():
    c = _client(lambda r: httpx.Response(200, json={}))
    assert c.pose_url() == "ws://robot:8080/ws/swarm/pose?token=op-token"
    assert c.reference_url() == "ws://robot:8080/ws/swarm/reference?token=op-token"
    assert c.events_url(["nav.*", "swarm.*"]) == "ws://robot:8080/ws/events?token=op-token&types=nav.%2A%2Cswarm.%2A"
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_transport.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`src/rosy_fleet/rosy_fleet/swarm/transport.py`:

```python
"""rosy_fleet.swarm.transport — 로봇 계약(API Ref)을 부르는 유일한 곳.

릴레이와 세션은 `RobotClient` 프로토콜만 본다. 테스트는 가짜를 끼우고, 운용은
`HttpRobotClient`(httpx + websockets) 를 끼운다. WS 이터레이터는 소켓이 닫히면
**조용히 끝난다** — 재연결은 호출자(릴레이/세션)의 정책이다.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional, Protocol, Sequence, runtime_checkable

import httpx

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.swarm.robots import RobotEndpoint, ws_url


class RobotApiError(Exception):
    """로봇이 4xx/5xx 를 돌려줬다. `code` 는 ERR-101 본문의 것, 없으면 `HTTP_<status>`."""

    def __init__(self, robot_id: str, status: int, code: str, message: str) -> None:
        super().__init__(f"{robot_id}: {code} ({status}) {message}")
        self.robot_id = robot_id
        self.status = status
        self.code = code
        self.message = message


class ReferenceSink(Protocol):
    async def send(self, frame: str) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class RobotClient(Protocol):
    robot_id: str

    async def state(self) -> dict: ...
    async def swarm_state(self) -> dict: ...
    async def follow(self, params: SwarmFollowParams) -> dict: ...
    async def swarm_cancel(self) -> dict: ...
    async def navigation_cancel(self) -> dict: ...
    async def navigation_goal(self, x: float, y: float, yaw: float) -> dict: ...
    def pose_stream(self) -> AsyncIterator[str]: ...
    async def open_reference_sink(self) -> ReferenceSink: ...
    def events(self, types: Sequence[str]) -> AsyncIterator[dict]: ...


class _WebsocketSink:
    def __init__(self, ws) -> None:
        self._ws = ws

    async def send(self, frame: str) -> None:
        await self._ws.send(frame)

    async def close(self) -> None:
        await self._ws.close()


class HttpRobotClient:
    def __init__(self, endpoint: RobotEndpoint, *, http: Optional[httpx.AsyncClient] = None,
                 timeout_s: float = 5.0) -> None:
        self.robot_id = endpoint.robot_id
        self._ep = endpoint
        self._http = http or httpx.AsyncClient(base_url=endpoint.base_url, timeout=timeout_s)

    # --- REST -----------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._ep.token}"}

    def _check(self, resp: httpx.Response) -> dict:
        if resp.status_code < 400:
            return resp.json() if resp.content else {}
        code, message = f"HTTP_{resp.status_code}", resp.text
        try:
            err = resp.json().get("error") or {}
            code = str(err.get("code") or code)
            message = str(err.get("message") or message)
        except (ValueError, AttributeError):
            pass
        raise RobotApiError(self.robot_id, resp.status_code, code, message)

    async def _get(self, path: str) -> dict:
        return self._check(await self._http.get(path, headers=self._headers()))

    async def _post(self, path: str, body: Optional[dict[str, Any]] = None) -> dict:
        return self._check(await self._http.post(path, json=body, headers=self._headers()))

    async def state(self) -> dict:
        return await self._get("/api/v1/robot/state")

    async def swarm_state(self) -> dict:
        return await self._get("/api/v1/swarm/state")

    async def follow(self, params: SwarmFollowParams) -> dict:
        return await self._post("/api/v1/swarm/follow", params.model_dump(mode="json"))

    async def swarm_cancel(self) -> dict:
        return await self._post("/api/v1/swarm/cancel")

    async def navigation_cancel(self) -> dict:
        return await self._post("/api/v1/navigation/cancel")

    async def navigation_goal(self, x: float, y: float, yaw: float) -> dict:
        return await self._post("/api/v1/navigation/goal", {"x": x, "y": y, "yaw": yaw})

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- WS -------------------------------------------------------------------

    def pose_url(self) -> str:
        return ws_url(self._ep.base_url, "/ws/swarm/pose", self._ep.token)

    def reference_url(self) -> str:
        return ws_url(self._ep.base_url, "/ws/swarm/reference", self._ep.token)

    def events_url(self, types: Sequence[str]) -> str:
        return ws_url(self._ep.base_url, "/ws/events", self._ep.token, types=",".join(types))

    async def pose_stream(self) -> AsyncIterator[str]:
        """리더 pose 프레임(텍스트). 소켓이 닫히면 끝난다 — 재연결은 호출자 몫."""
        import websockets

        try:
            async with websockets.connect(self.pose_url()) as ws:
                async for frame in ws:
                    yield frame if isinstance(frame, str) else frame.decode("utf-8")
        except (OSError, websockets.exceptions.WebSocketException):
            return

    async def open_reference_sink(self) -> ReferenceSink:
        import websockets

        return _WebsocketSink(await websockets.connect(self.reference_url()))

    async def events(self, types: Sequence[str]) -> AsyncIterator[dict]:
        import websockets

        try:
            async with websockets.connect(self.events_url(types)) as ws:
                async for frame in ws:
                    try:
                        event = json.loads(frame)
                    except (TypeError, ValueError):
                        continue
                    if isinstance(event, dict):
                        yield event
        except (OSError, websockets.exceptions.WebSocketException):
            return
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_transport.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/rosy_fleet/rosy_fleet/swarm/transport.py src/rosy_fleet/test/test_transport.py
git commit -m "feat(fleet): put every call to the robot contract behind one client protocol

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: 테스트 가짜들 — `FakeRobot`, `FakeSink`, `FakeRelay`

**Files:**
- Create: `src/rosy_fleet/test/fakes.py`

릴레이(Task 7)와 세션(Task 8)이 같은 가짜를 쓴다. 가짜는 **호출을 기록**하고,
스트림은 `asyncio.Queue` 로 바깥에서 밀어 넣는다. 큐에 `None` 을 넣으면 그 스트림은
끝난다(소켓 단절을 흉내낸다).

- [ ] **Step 1: 가짜 작성**

`src/rosy_fleet/test/fakes.py`:

```python
"""릴레이·세션 테스트가 공유하는 가짜 전송계층.

`RobotClient` 프로토콜을 만족하되 네트워크는 없다. 스트림은 큐로 밀어 넣고,
`None` 을 넣으면 그 스트림은 끝난다(소켓 단절). 모든 호출은 `calls` 에 남는다.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional, Sequence

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.swarm.transport import RobotApiError

END = None


def run(coro):
    return asyncio.run(coro)


async def settle(rounds: int = 20) -> None:
    """대기 중인 태스크들이 한 바퀴씩 돌게 한다. 시간이 아니라 스케줄 회전이다."""
    for _ in range(rounds):
        await asyncio.sleep(0)


class FakeSink:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.fail_on_send = fail_on_send
        #: 잡혀 있으면 send 가 여기서 기다린다 — 느린 팔로워를 흉내낸다.
        self.gate: Optional[asyncio.Event] = None

    async def send(self, frame: str) -> None:
        if self.gate is not None:
            await self.gate.wait()
        if self.fail_on_send:
            raise ConnectionError("sink broke")
        self.sent.append(frame)

    async def close(self) -> None:
        self.closed = True


class FakeRobot:
    def __init__(self, robot_id: str, *, state: Optional[dict] = None,
                 follow_error: Optional[RobotApiError] = None,
                 swarm_state: Optional[dict] = None, log: Optional[list] = None) -> None:
        self.robot_id = robot_id
        self.calls: list[tuple] = []
        #: 여러 로봇의 호출 순서를 한 줄로 보고 싶을 때 같은 리스트를 넘긴다.
        self.log = log if log is not None else []
        self._state = state or {"robot_id": robot_id, "map_id": "m1",
                                "pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}
        self._swarm_state = swarm_state or {"active": True, "holding": False}
        self.follow_error = follow_error
        self.pose_frames: asyncio.Queue = asyncio.Queue()
        self.event_frames: asyncio.Queue = asyncio.Queue()
        self.sinks: list[FakeSink] = []
        #: 다음 open_reference_sink 가 이만큼 실패한다.
        self.sink_failures = 0
        self.next_sink_fail_on_send = False
        self.pose_opens = 0
        self.event_opens = 0
        #: 설정돼 있으면 pose_stream 이 열리자마자 이것을 raise 한다 (4401/4403 거부 흉내).
        self.pose_error = None

    def _record(self, *call) -> None:
        self.calls.append(call)
        self.log.append((self.robot_id,) + call)

    async def state(self) -> dict:
        self._record("state")
        return dict(self._state)

    async def swarm_state(self) -> dict:
        self._record("swarm_state")
        return dict(self._swarm_state)

    async def follow(self, params: SwarmFollowParams) -> dict:
        self._record("follow", params)
        if self.follow_error is not None:
            raise self.follow_error
        return {"role": "follower", "active": True}

    async def swarm_cancel(self) -> dict:
        self._record("swarm_cancel")
        return {"active": False}

    async def navigation_cancel(self) -> dict:
        self._record("navigation_cancel")
        return {"canceled": True}

    async def navigation_goal(self, x: float, y: float, yaw: float) -> dict:
        self._record("navigation_goal", x, y, yaw)
        return {"accepted": True}

    async def pose_stream(self) -> AsyncIterator[str]:
        self.pose_opens += 1
        if self.pose_error is not None:
            await asyncio.sleep(0)
            raise self.pose_error
        while True:
            frame = await self.pose_frames.get()
            if frame is END:
                return
            # 실제 소켓은 프레임 사이에 제어권을 놓는다. 큐는 비어 있지 않으면 놓지
            # 않으므로 여기서 한 번 양보한다 — 아니면 N 프레임이 한 번에 처리돼
            # 깊이 1 큐가 그것을 하나로 합치고, "프레임마다 전달" 테스트가 거짓 실패한다.
            await asyncio.sleep(0)
            yield frame

    async def open_reference_sink(self) -> FakeSink:
        if self.sink_failures > 0:
            self.sink_failures -= 1
            raise ConnectionError("cannot open reference socket")
        sink = FakeSink(fail_on_send=self.next_sink_fail_on_send)
        self.next_sink_fail_on_send = False
        self.sinks.append(sink)
        return sink

    async def events(self, types: Sequence[str]) -> AsyncIterator[dict]:
        self.event_opens += 1
        self._record("events", tuple(types))
        while True:
            ev = await self.event_frames.get()
            if ev is END:
                return
            await asyncio.sleep(0)
            yield ev


class FakeRelay:
    """세션 테스트용. 실제 소켓 대신 호출 순서만 남긴다."""

    def __init__(self, leader, followers, *, log: Optional[list] = None, **_) -> None:
        self.leader = leader
        self.followers = list(followers)
        self.log = log if log is not None else []
        self.paused = False
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True
        self.log.append(("relay", "start"))

    async def stop(self) -> None:
        self.stopped = True
        self.log.append(("relay", "stop"))

    def pause(self) -> None:
        self.paused = True
        self.log.append(("relay", "pause"))

    def resume(self) -> None:
        self.paused = False
        self.log.append(("relay", "resume"))

    def is_connected(self, robot_id: str) -> bool:
        return True
```

- [ ] **Step 2: import 만 확인**

Run: `python -c "import sys; sys.path[:0]=['src/rosy_fleet','src/rosy_core','src/rosy_fleet/test']; import fakes; print('ok')"`
Expected: `ok`

- [ ] **Step 3: 커밋**

```bash
git add src/rosy_fleet/test/fakes.py
git commit -m "test(fleet): one set of fakes for the relay and session tests to share

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: 릴레이 — 팬아웃, 깊이 1 큐, pause, 재연결, 계측

**Files:**
- Create: `src/rosy_fleet/rosy_fleet/swarm/relay.py`
- Create: `src/rosy_fleet/test/test_relay.py`

- [ ] **Step 1: 실패하는 테스트**

`src/rosy_fleet/test/test_relay.py`:

```python
"""릴레이는 리더 프레임을 바꾸지 않고 팔로워에 전달한다(D-31). 합성하지 않고,
느린 팔로워에 밀리지 않고, 팔로워 하나가 죽어도 나머지는 계속 받는다."""

import asyncio
import json

from fakes import END, FakeRobot, run, settle

from rosy_fleet.swarm.relay import Relay
from rosy_fleet.swarm.transport import RobotApiError


def frame(seq: int) -> str:
    return json.dumps({"type": "pose", "payload": {"robot_id": "rosy_01", "seq": seq,
                                                    "pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}})


def _no_sleep():
    async def sleep(_s):
        await asyncio.sleep(0)
    return sleep


def test_frames_reach_every_follower_byte_for_byte():
    async def main():
        leader, f1, f2 = FakeRobot("rosy_01"), FakeRobot("rosy_02"), FakeRobot("rosy_03")
        relay = Relay(leader, [f1, f2], sleep=_no_sleep())
        await relay.start()
        await settle()
        leader.pose_frames.put_nowait(frame(1))
        leader.pose_frames.put_nowait(frame(2))
        await settle()
        assert f1.sinks[0].sent == [frame(1), frame(2)]
        assert f2.sinks[0].sent == [frame(1), frame(2)]
        await relay.stop()
    run(main())


def test_pause_stops_delivery_and_resume_restarts_it_without_replaying():
    async def main():
        leader, f1 = FakeRobot("rosy_01"), FakeRobot("rosy_02")
        relay = Relay(leader, [f1], sleep=_no_sleep())
        await relay.start()
        await settle()
        leader.pose_frames.put_nowait(frame(1))
        await settle()
        relay.pause()
        leader.pose_frames.put_nowait(frame(2))
        leader.pose_frames.put_nowait(frame(3))
        await settle()
        assert f1.sinks[0].sent == [frame(1)]
        relay.resume()
        await settle()
        assert f1.sinks[0].sent == [frame(1)]          # 멈춘 동안의 프레임은 재생하지 않는다
        leader.pose_frames.put_nowait(frame(4))
        await settle()
        assert f1.sinks[0].sent == [frame(1), frame(4)]
        await relay.stop()
    run(main())


def test_a_slow_follower_gets_the_latest_frame_not_the_backlog():
    async def main():
        leader, f1 = FakeRobot("rosy_01"), FakeRobot("rosy_02")
        relay = Relay(leader, [f1], sleep=_no_sleep())
        await relay.start()
        await settle()
        sink = f1.sinks[0]
        sink.gate = asyncio.Event()                     # send 가 여기서 막힌다
        leader.pose_frames.put_nowait(frame(1))        # 전송 중에 걸린다
        await settle()
        leader.pose_frames.put_nowait(frame(2))
        leader.pose_frames.put_nowait(frame(3))
        await settle()
        sink.gate.set()
        await settle()
        assert sink.sent == [frame(1), frame(3)]        # 2 는 3 에 덮였다
        await relay.stop()
    run(main())


def test_one_broken_follower_does_not_stop_the_others():
    async def main():
        leader, f1, f2 = FakeRobot("rosy_01"), FakeRobot("rosy_02"), FakeRobot("rosy_03")
        f1.next_sink_fail_on_send = True
        relay = Relay(leader, [f1, f2], sleep=_no_sleep())
        await relay.start()
        await settle()
        leader.pose_frames.put_nowait(frame(1))
        await settle()
        assert f2.sinks[0].sent == [frame(1)]
        # f1 은 첫 소켓이 깨져 재연결했고, 그다음 프레임은 새 소켓으로 받는다.
        leader.pose_frames.put_nowait(frame(2))
        await settle()
        assert len(f1.sinks) >= 2
        assert f1.sinks[-1].sent == [frame(2)]
        assert relay.is_connected("rosy_02")
        await relay.stop()
    run(main())


def test_a_lost_leader_is_reconnected_and_nothing_is_synthesized():
    async def main():
        leader, f1 = FakeRobot("rosy_01"), FakeRobot("rosy_02")
        relay = Relay(leader, [f1], sleep=_no_sleep())
        await relay.start()
        await settle()
        leader.pose_frames.put_nowait(frame(1))
        leader.pose_frames.put_nowait(END)              # 리더 소켓 단절
        await settle()
        assert f1.sinks[0].sent == [frame(1)]           # 반복 전송 없음
        assert leader.pose_opens >= 2                   # 다시 열었다
        leader.pose_frames.put_nowait(frame(2))
        await settle()
        assert f1.sinks[0].sent == [frame(1), frame(2)]
        await relay.stop()
    run(main())


def test_a_follower_socket_that_will_not_open_is_retried():
    async def main():
        leader, f1 = FakeRobot("rosy_01"), FakeRobot("rosy_02")
        f1.sink_failures = 2
        relay = Relay(leader, [f1], sleep=_no_sleep())
        await relay.start()
        await settle(40)
        assert len(f1.sinks) == 1
        assert relay.is_connected("rosy_02")
        await relay.stop()
    run(main())


def test_stats_count_frames_and_seq_gaps():
    async def main():
        leader, f1 = FakeRobot("rosy_01"), FakeRobot("rosy_02")
        relay = Relay(leader, [f1], sleep=_no_sleep())
        await relay.start()
        await settle()
        for seq in (1, 2, 5, 6):                        # 3, 4 가 빠졌다
            leader.pose_frames.put_nowait(frame(seq))
        leader.pose_frames.put_nowait("not json")      # 계측만 건너뛰고 전달은 한다
        await settle()
        stats = relay.stats()
        assert stats.leader_frames == 5
        assert stats.leader_dropped == 2
        assert stats.follower_tx["rosy_02"] == 5
        assert f1.sinks[0].sent[-1] == "not json"
        await relay.stop()
    run(main())


def test_a_rejected_leader_socket_is_named_in_the_stats_and_still_retried():
    async def main():
        leader, f1 = FakeRobot("rosy_01"), FakeRobot("rosy_02")
        leader.pose_error = RobotApiError("rosy_01", 403, "WS_4403", "capability swarm.lead not declared")
        relay = Relay(leader, [f1], sleep=_no_sleep())
        await relay.start()
        await settle(40)
        assert relay.stats().leader_last_error is not None
        assert "WS_4403" in relay.stats().leader_last_error
        assert leader.pose_opens >= 2                   # 포기하지 않는다 — 정책은 호출자 것
        leader.pose_error = None
        leader.pose_frames.put_nowait(frame(1))
        await settle(40)
        assert f1.sinks[0].sent == [frame(1)]
        assert relay.stats().leader_last_error is None  # 프레임이 오면 지운다
        await relay.stop()
    run(main())


def test_stop_closes_the_sinks():
    async def main():
        leader, f1 = FakeRobot("rosy_01"), FakeRobot("rosy_02")
        relay = Relay(leader, [f1], sleep=_no_sleep())
        await relay.start()
        await settle()
        await relay.stop()
        assert f1.sinks[0].closed
        assert not relay.is_connected("rosy_02")
    run(main())
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_relay.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rosy_fleet.swarm.relay'`

- [ ] **Step 3: 구현**

`src/rosy_fleet/rosy_fleet/swarm/relay.py`:

```python
"""rosy_fleet.swarm.relay — 리더 pose 소켓 1 → 팔로워 reference 소켓 N (D-31).

규칙:
- 프레임을 바꾸지 않는다. 계측을 위해 파싱은 하되 전달하는 바이트는 그대로다.
- 합성하지 않는다. 리더가 끊기면 팔로워는 SWM-004 로 스스로 HOLD 한다. 마지막
  프레임을 반복하면 죽은 리더가 살아 있는 것으로 보인다.
- 팔로워 하나의 실패가 나머지를 막지 않는다. 소켓별 태스크, 소켓별 재연결.
- 느린 팔로워에 밀리지 않는다. 소켓별 큐는 깊이 1, 최신이 이전을 덮는다.
- `pause()` 중에는 리더를 계속 읽되 팔로워에 쓰지 않는다. FOR-004 의 "전체 HOLD"
  가 이것이다 (설계 §6.4, D-35 후보).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Sequence

from rosy_fleet.swarm.transport import RobotApiError, RobotClient

_BACKOFF_FIRST_S = 0.1
_RATE_WINDOW = 20


@dataclass
class RelayStats:
    leader_frames: int = 0
    leader_dropped: int = 0
    leader_rx_hz: float = 0.0
    #: 리더 소켓이 마지막으로 **거부**된 이유 (4401/4403 → RobotApiError 문자열). 재연결은
    #: 계속하지만, "0 Hz 가 영원히" 인 화면에 이유가 붙어야 한다. 프레임이 오면 None 으로 돈다.
    leader_last_error: Optional[str] = None
    paused: bool = False
    follower_tx: dict[str, int] = field(default_factory=dict)
    follower_tx_hz: dict[str, float] = field(default_factory=dict)
    follower_connected: dict[str, bool] = field(default_factory=dict)


class _Rate:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._stamps: deque[float] = deque(maxlen=_RATE_WINDOW)

    def tick(self) -> None:
        self._stamps.append(self._clock())

    def hz(self) -> float:
        if len(self._stamps) < 2:
            return 0.0
        span = self._stamps[-1] - self._stamps[0]
        return (len(self._stamps) - 1) / span if span > 0 else 0.0


class _Lane:
    """팔로워 하나. 깊이 1 큐 + 연결 상태 + 송신 계측."""

    def __init__(self, robot: RobotClient, clock: Callable[[], float]) -> None:
        self.robot = robot
        self.latest: Optional[str] = None
        self.wake = asyncio.Event()
        self.connected = False
        self.tx = 0
        self.rate = _Rate(clock)
        self.sink = None


class Relay:
    def __init__(self, leader: RobotClient, followers: Sequence[RobotClient], *,
                 clock: Callable[[], float] = time.monotonic,
                 reconnect_max_s: float = 2.0,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._leader = leader
        self._lanes = {f.robot_id: _Lane(f, clock) for f in followers}
        self._clock = clock
        self._reconnect_max = reconnect_max_s
        self._sleep = sleep
        self._paused = False
        self._tasks: list[asyncio.Task] = []
        self._leader_frames = 0
        self._leader_dropped = 0
        self._leader_rate = _Rate(clock)
        self._last_seq: Optional[int] = None
        self._leader_last_error: Optional[str] = None
        self._running = False

    # --- 수명 --------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._tasks.append(asyncio.create_task(self._read_leader()))
        for lane in self._lanes.values():
            self._tasks.append(asyncio.create_task(self._feed(lane)))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        for lane in self._lanes.values():
            if lane.sink is not None:
                try:
                    await lane.sink.close()
                except Exception:
                    pass
                lane.sink = None
            lane.connected = False

    def pause(self) -> None:
        self._paused = True
        for lane in self._lanes.values():
            lane.latest = None   # 멈추기 전 프레임이 resume 뒤에 나가면 안 된다

    def resume(self) -> None:
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    def is_connected(self, robot_id: str) -> bool:
        lane = self._lanes.get(robot_id)
        return bool(lane and lane.connected)

    def stats(self) -> RelayStats:
        return RelayStats(
            leader_frames=self._leader_frames,
            leader_dropped=self._leader_dropped,
            leader_rx_hz=self._leader_rate.hz(),
            leader_last_error=self._leader_last_error,
            paused=self._paused,
            follower_tx={rid: lane.tx for rid, lane in self._lanes.items()},
            follower_tx_hz={rid: lane.rate.hz() for rid, lane in self._lanes.items()},
            follower_connected={rid: lane.connected for rid, lane in self._lanes.items()},
        )

    # --- 리더 --------------------------------------------------------------------

    async def _read_leader(self) -> None:
        backoff = _BACKOFF_FIRST_S
        while self._running:
            got_any = False
            try:
                async for frame in self._leader.pose_stream():
                    got_any = True
                    backoff = _BACKOFF_FIRST_S
                    self._leader_last_error = None
                    self._on_frame(frame)
            except asyncio.CancelledError:
                raise
            except RobotApiError as exc:
                # 4401/4403: 토큰이나 capability 문제다. 재연결은 계속하되 이유를 남긴다 —
                # 조용히 0 Hz 로 도는 것이 이 릴레이의 가장 나쁜 실패다.
                self._leader_last_error = str(exc)
            except Exception:
                pass
            if not self._running:
                return
            # 소켓이 끝났다. 합성하지 않고 다시 연다.
            await self._sleep(backoff if not got_any else _BACKOFF_FIRST_S)
            backoff = min(backoff * 2, self._reconnect_max)

    def _on_frame(self, frame: str) -> None:
        self._leader_frames += 1
        self._leader_rate.tick()
        seq = _seq_of(frame)
        if seq is not None:
            if self._last_seq is not None and seq > self._last_seq + 1:
                self._leader_dropped += seq - self._last_seq - 1
            self._last_seq = seq
        if self._paused:
            return
        for lane in self._lanes.values():
            lane.latest = frame        # 깊이 1: 덮는다
            lane.wake.set()

    # --- 팔로워 ------------------------------------------------------------------

    async def _feed(self, lane: _Lane) -> None:
        backoff = _BACKOFF_FIRST_S
        while self._running:
            try:
                lane.sink = await lane.robot.open_reference_sink()
            except asyncio.CancelledError:
                raise
            except Exception:
                lane.connected = False
                await self._sleep(backoff)
                backoff = min(backoff * 2, self._reconnect_max)
                continue
            lane.connected = True
            backoff = _BACKOFF_FIRST_S
            try:
                while self._running:
                    await lane.wake.wait()
                    lane.wake.clear()
                    frame, lane.latest = lane.latest, None
                    if frame is None:
                        continue
                    await lane.sink.send(frame)
                    lane.tx += 1
                    lane.rate.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                lane.connected = False
                try:
                    await lane.sink.close()
                except Exception:
                    pass
                lane.sink = None
                await self._sleep(backoff)


def _seq_of(frame: str) -> Optional[int]:
    try:
        payload = json.loads(frame).get("payload") or {}
        seq = payload.get("seq")
        return int(seq) if isinstance(seq, int) else None
    except (TypeError, ValueError, AttributeError):
        return None
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_relay.py -v`
Expected: PASS (전부 — 리뷰 후 추가된 테스트 포함)

`test_a_slow_follower_gets_the_latest_frame_not_the_backlog` 가 흔들리면 `settle()`
회전 수를 늘린다. 시간 기반 대기는 쓰지 않는다.

- [ ] **Step 5: 커밋**

```bash
git add src/rosy_fleet/rosy_fleet/swarm/relay.py src/rosy_fleet/test/test_relay.py
git commit -m "feat(fleet): relay the leader's frames untouched, and never invent one

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: 세션 — 무장, FOR-004, reform, resume, stop

**Files:**
- Create: `src/rosy_fleet/rosy_fleet/swarm/session.py`
- Create: `src/rosy_fleet/test/test_session.py`

- [ ] **Step 1: 실패하는 테스트**

`src/rosy_fleet/test/test_session.py`:

```python
"""FormationSession — 무장은 전부 아니면 전무, HOLD 는 릴레이를 멈추는 것(D-35 후보),
재개는 운영자만 한다."""

import math

import pytest
from fakes import END, FakeRelay, FakeRobot, run, settle

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.formation.geometry import Formation, SlotOffset
from rosy_fleet.swarm.session import (
    ArmingFailed,
    FormationSession,
    FormationSpec,
    HoldPolicy,
    MapMismatch,
    SessionState,
)
from rosy_fleet.swarm.transport import RobotApiError


def _robots(n=2, log=None, leader_pose=(0.0, 0.0, 0.0)):
    log = log if log is not None else []
    leader = FakeRobot("rosy_01", log=log, state={
        "robot_id": "rosy_01", "map_id": "m1",
        "pose": {"x": leader_pose[0], "y": leader_pose[1], "yaw": leader_pose[2]}})
    followers = [FakeRobot(f"rosy_{i:02d}", log=log) for i in range(2, 2 + n)]
    return leader, followers, log


def _session(leader, followers, spec=None, log=None, **kw):
    spec = spec or FormationSpec(Formation.COLUMN, spacing=0.6)
    return FormationSession(leader, followers, spec,
                            relay_factory=lambda l, f, **_: FakeRelay(l, f, log=log), **kw)


def _follows(robot):
    return [c[1] for c in robot.calls if c[0] == "follow"]


def test_start_arms_every_follower_with_its_slot_and_then_starts_the_relay():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        assert s.state is SessionState.RUNNING
        params = {f.robot_id: _follows(f)[0] for f in followers}
        assert all(isinstance(p, SwarmFollowParams) for p in params.values())
        assert {p.target_robot_id for p in params.values()} == {"rosy_01"}
        assert sorted(p.distance for p in params.values()) == [0.6, 1.2]
        assert all(p.max_speed == 0.15 and p.stream_timeout_ms == 1000 for p in params.values())
        kinds = [entry[1] for entry in log if entry[0] == "relay" or entry[1] == "follow"]
        assert kinds.index("start") > max(i for i, k in enumerate(kinds) if k == "follow")
        await s.stop()
    run(main())


def test_the_nearest_follower_takes_the_nearest_slot():
    async def main():
        leader, followers, log = _robots(2)
        # V, spacing 0.6: 슬롯은 리더 뒤 0.6, 좌 +0.6 / 우 −0.6. rosy_02 는 왼쪽에 있다.
        followers[0]._state["pose"] = {"x": -0.6, "y": 0.6, "yaw": 0.0}
        followers[1]._state["pose"] = {"x": -0.6, "y": -0.6, "yaw": 0.0}
        s = _session(leader, followers, spec=FormationSpec(Formation.V, spacing=0.6), log=log)
        await s.start()
        assert s.assignment["rosy_02"] == SlotOffset(0.6, 0.6)
        assert s.assignment["rosy_03"] == SlotOffset(0.6, -0.6)
        await s.stop()
    run(main())


def test_one_refused_follow_cancels_the_ones_already_armed_and_never_starts_the_relay():
    async def main():
        leader, followers, log = _robots(2)
        followers[1].follow_error = RobotApiError("rosy_03", 409, "DOCKING_ACTIVE", "busy")
        s = _session(leader, followers, log=log)
        with pytest.raises(ArmingFailed) as exc:
            await s.start()
        assert exc.value.robot_id == "rosy_03" and exc.value.code == "DOCKING_ACTIVE"
        assert ("swarm_cancel",) in followers[0].calls
        assert ("relay", "start") not in log
        assert s.state is SessionState.STOPPED
    run(main())


def test_a_map_mismatch_is_refused_before_any_follow():
    async def main():
        leader, followers, log = _robots(2)
        followers[1]._state["map_id"] = "other"
        s = _session(leader, followers, log=log)
        with pytest.raises(MapMismatch):
            await s.start()
        assert not any(_follows(f) for f in followers)
    run(main())


def test_a_robot_without_a_map_id_does_not_block_the_start():
    async def main():
        leader, followers, log = _robots(2)
        followers[1]._state["map_id"] = None
        s = _session(leader, followers, log=log)
        await s.start()
        assert s.state is SessionState.RUNNING
        await s.stop()
    run(main())


@pytest.mark.parametrize("event_type", ["nav.stuck", "nav.failed", "nav.blocked",
                                        "swarm.aborted", "safety.estop"])
def test_each_for_004_trigger_pauses_the_relay_and_cancels_the_leader(event_type):
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": event_type, "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        assert s.reason == (event_type, "rosy_02")
        assert s.relay.paused
        assert ("navigation_cancel",) in leader.calls
        assert log.index(("relay", "pause")) < log.index(("rosy_01", "navigation_cancel"))
        await s.stop()
    run(main())


def test_a_trigger_on_the_leader_counts_too():
    async def main():
        leader, followers, log = _robots(1)
        s = _session(leader, followers, log=log)
        await s.start()
        leader.event_frames.put_nowait({"type": "nav.failed", "robot_id": "rosy_01", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        await s.stop()
    run(main())


def test_swarm_hold_is_not_a_trigger_and_holding_ignores_further_events():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "swarm.hold", "robot_id": "rosy_02",
                                              "data": {"reason": "map_mismatch"}})
        await settle()
        assert s.state is SessionState.RUNNING
        followers[0].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        cancels = leader.calls.count(("navigation_cancel",))
        followers[1].event_frames.put_nowait({"type": "swarm.hold", "robot_id": "rosy_03",
                                              "data": {"reason": "reference stream lost"}})
        followers[1].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_03", "data": {}})
        await settle()
        assert leader.calls.count(("navigation_cancel",)) == cancels   # 두 번 처리하지 않는다
        await s.stop()
    run(main())


def test_resume_is_the_only_way_back_to_running():
    async def main():
        leader, followers, log = _robots(1)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.blocked", "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.HOLDING
        await settle(50)
        assert s.state is SessionState.HOLDING            # 시간이 지나도 스스로 돌아오지 않는다
        await s.resume()
        assert s.state is SessionState.RUNNING and not s.relay.paused and s.reason is None
        await s.resume()                                   # RUNNING 에서 resume 은 무해하다
        assert s.state is SessionState.RUNNING
        await s.stop()
    run(main())


def test_the_abort_policy_cancels_every_follower_and_ends_the_session():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log, policy=HoldPolicy.ABORT)
        await s.start()
        followers[0].event_frames.put_nowait({"type": "nav.stuck", "robot_id": "rosy_02", "data": {}})
        await settle()
        assert s.state is SessionState.STOPPED
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert ("navigation_cancel",) in leader.calls
        assert s.relay.stopped
    run(main())


def test_reform_pauses_rearms_with_the_new_offsets_and_resumes():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        mark = len(log)
        await s.reform(FormationSpec(Formation.LINE, spacing=0.6))
        tail = log[mark:]
        assert tail[0] == ("relay", "pause")
        assert tail[-1] == ("relay", "resume")
        second = {f.robot_id: _follows(f)[1] for f in followers}
        assert sorted(p.lateral for p in second.values()) == [-0.6, 0.6]
        assert all(p.distance == 0.0 for p in second.values())
        assert s.state is SessionState.RUNNING
        await s.stop()
    run(main())


def test_a_failed_reform_ends_the_session_because_half_a_formation_cannot_be_resumed():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[1].follow_error = RobotApiError("rosy_03", 409, "EMERGENCY_ACTIVE", "estop")
        with pytest.raises(ArmingFailed):
            await s.reform(FormationSpec(Formation.LINE, spacing=0.6))
        # 재무장된 팔로워는 이미 풀렸고 나머지는 옛 오프셋을 쥐고 있다. 그 상태로 스트림을
        # 다시 켜면 대형이 둘로 갈린다 — HOLD 가 아니라 종료가 정직하다.
        assert s.state is SessionState.STOPPED
        assert s.reason[0].startswith("reform_failed")
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert ("navigation_cancel",) in leader.calls
        assert s.relay.stopped
    run(main())


def test_stop_cancels_every_follower_and_stops_the_relay():
    async def main():
        leader, followers, log = _robots(2)
        s = _session(leader, followers, log=log)
        await s.start()
        await s.stop()
        assert s.state is SessionState.STOPPED
        assert all(("swarm_cancel",) in f.calls for f in followers)
        assert ("navigation_cancel",) not in leader.calls     # 리더 항법은 운영자의 것
        assert s.relay.stopped
    run(main())


def test_an_events_socket_that_drops_is_reopened_and_a_follower_found_inactive_is_an_abort():
    async def main():
        leader, followers, log = _robots(1)
        s = _session(leader, followers, log=log)
        await s.start()
        followers[0]._swarm_state = {"active": False, "holding": False}
        followers[0].event_frames.put_nowait(END)          # 이벤트 소켓 단절
        await settle(40)
        assert followers[0].event_opens >= 2
        assert s.state is SessionState.HOLDING
        assert s.reason == ("swarm.aborted", "rosy_02")
        await s.stop()
    run(main())
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rosy_fleet.swarm.session'`

- [ ] **Step 3: 구현**

`src/rosy_fleet/rosy_fleet/swarm/session.py`:

```python
"""rosy_fleet.swarm.session — 대형 세션: 무장 → 릴레이 → 감시 → FOR-004.

- 무장은 **전부 아니면 전무**다. 하나라도 거절되면 이미 무장된 팔로워를 풀고 끝낸다.
  무장된 팔로워만 남기면 참조 프레임 하나에 달려나갈 준비가 된 채로 남는다.
- FOR-004 기본 정책 HOLD 는 릴레이를 멈추는 것이다(설계 §6.4, D-35 후보). 팔로워는
  SWM-004 로 스스로 자리를 지키고, 리더 항법만 취소한다.
- 재개는 운영자만 한다. 자동 재개는 SRS 가 금지한 자동 재시도다.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional, Sequence

from rosy_core.protocol.schemas import SwarmFollowParams
from rosy_fleet.formation.assignment import GreedyDistanceAssigner, SlotAssigner
from rosy_fleet.formation.geometry import (
    DEFAULT_SPACING,
    Formation,
    SlotOffset,
    slot_world_position,
    slots,
)
from rosy_fleet.swarm.relay import Relay
from rosy_fleet.swarm.transport import RobotApiError, RobotClient

log = logging.getLogger(__name__)

#: 이 이벤트 중 하나가 어느 로봇에서든 오면 정책을 적용한다 (FOR-004).
TRIGGERS = frozenset({"nav.stuck", "nav.failed", "nav.blocked", "swarm.aborted", "safety.estop"})
#: 구독 필터. `swarm.hold` 는 정보이고 트리거가 아니지만 로그에 남기기 위해 받는다.
EVENT_TYPES = ("nav.*", "swarm.*", "safety.estop")

_BACKOFF_FIRST_S = 0.1
_BACKOFF_MAX_S = 2.0


class SessionState(str, Enum):
    IDLE = "IDLE"
    ARMING = "ARMING"
    RUNNING = "RUNNING"
    HOLDING = "HOLDING"
    STOPPED = "STOPPED"


class HoldPolicy(str, Enum):
    HOLD = "HOLD"      # 릴레이 pause + 리더 navigation/cancel. 팔로워 follow 세션은 산다.
    ABORT = "ABORT"    # 전 팔로워 swarm/cancel + 리더 navigation/cancel. 세션 종료.


@dataclass
class FormationSpec:
    formation: Formation
    spacing: float = DEFAULT_SPACING
    grid_cols: int = 2
    max_speed: float = 0.15
    stream_timeout_ms: int = 1000


class SessionError(Exception):
    pass


class ArmingFailed(SessionError):
    def __init__(self, robot_id: str, code: str, message: str = "") -> None:
        super().__init__(f"{robot_id} refused follow: {code} {message}".strip())
        self.robot_id = robot_id
        self.code = code


class MapMismatch(SessionError):
    def __init__(self, map_ids: dict[str, Optional[str]]) -> None:
        super().__init__(f"robots are not on one map: {map_ids}")
        self.map_ids = map_ids


class FormationSession:
    def __init__(self, leader: RobotClient, followers: Sequence[RobotClient],
                 spec: FormationSpec, *,
                 assigner: Optional[SlotAssigner] = None,
                 policy: HoldPolicy = HoldPolicy.HOLD,
                 relay_factory: Callable[..., Relay] = Relay,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._leader = leader
        self._followers = list(followers)
        self.spec = spec
        self._assigner = assigner or GreedyDistanceAssigner()
        self._policy = policy
        self._relay_factory = relay_factory
        self._sleep = sleep
        self.state = SessionState.IDLE
        #: `(사유, robot_id)`. HOLDING/STOPPED 의 이유.
        self.reason: Optional[tuple[str, Optional[str]]] = None
        self.assignment: dict[str, SlotOffset] = {}
        self.relay: Optional[Relay] = None
        self._watchers: list[asyncio.Task] = []
        self._by_id = {r.robot_id: r for r in [leader, *followers]}

    # --- 운영자 명령 --------------------------------------------------------------

    async def start(self) -> None:
        if self.state is not SessionState.IDLE:
            raise SessionError(f"cannot start from {self.state.value}")
        self.state = SessionState.ARMING
        try:
            self.assignment = await self._arm(self.spec)
        except SessionError as exc:
            self.state = SessionState.STOPPED
            self.reason = (f"arming_failed:{exc}", getattr(exc, "robot_id", None))
            raise
        self.relay = self._relay_factory(self._leader, self._followers)
        await self.relay.start()
        for robot in [self._leader, *self._followers]:
            self._watchers.append(asyncio.create_task(self._watch(robot)))
        self.state = SessionState.RUNNING
        self.reason = None

    async def reform(self, spec: FormationSpec) -> None:
        if self.state not in (SessionState.RUNNING, SessionState.HOLDING):
            raise SessionError(f"cannot reform from {self.state.value}")
        assert self.relay is not None
        self.relay.pause()
        try:
            self.assignment = await self._arm(spec)
        except SessionError as exc:
            # 정책과 무관하게 끝낸다. 재무장된 팔로워는 _arm 이 이미 풀었고 나머지는 옛
            # 오프셋의 follow 세션을 쥐고 있다 — 그 위에 스트림을 다시 켜면 대형이 둘로
            # 갈린다. HOLD 로 두면 resume 이 그것을 그대로 살린다.
            await self._abort(f"reform_failed:{exc}", getattr(exc, "robot_id", None))
            raise
        self.spec = spec
        self.relay.resume()
        self.state = SessionState.RUNNING
        self.reason = None

    async def resume(self) -> None:
        if self.state is not SessionState.HOLDING:
            return
        assert self.relay is not None
        self.relay.resume()
        self.state = SessionState.RUNNING
        self.reason = None

    async def stop(self) -> None:
        for task in self._watchers:
            task.cancel()
        for task in self._watchers:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._watchers.clear()
        if self.relay is not None:
            await self.relay.stop()
        for follower in self._followers:
            try:
                await follower.swarm_cancel()
            except Exception as exc:  # 한 대가 안 받아도 나머지는 푼다
                log.warning("%s: swarm/cancel failed on stop: %s", follower.robot_id, exc)
        self.state = SessionState.STOPPED

    # --- 무장 ---------------------------------------------------------------------

    async def _arm(self, spec: FormationSpec) -> dict[str, SlotOffset]:
        leader_state = await self._leader.state()
        states = {f.robot_id: await f.state() for f in self._followers}

        map_ids = {self._leader.robot_id: leader_state.get("map_id"),
                   **{rid: s.get("map_id") for rid, s in states.items()}}
        known = {m for m in map_ids.values() if m}
        if len(known) > 1:
            # 로봇 쪽도 프레임마다 검사하지만(map_mismatch HOLD), 시작 전에 알 수 있는
            # 것을 시작 뒤에 알게 하지 않는다. 값이 없는 로봇은 판단 대상이 아니다.
            raise MapMismatch(map_ids)

        offsets = slots(spec.formation, len(self._followers), spec.spacing, grid_cols=spec.grid_cols)
        pose = leader_state.get("pose") or {}
        lx, ly, lyaw = float(pose.get("x", 0.0)), float(pose.get("y", 0.0)), float(pose.get("yaw", 0.0))
        slot_points = [slot_world_position(o, lx, ly, lyaw) for o in offsets]
        robot_points = {
            rid: (float((s.get("pose") or {}).get("x", 0.0)), float((s.get("pose") or {}).get("y", 0.0)))
            for rid, s in states.items()
        }
        chosen = self._assigner.assign(robot_points, slot_points)
        assignment = {rid: offsets[j] for rid, j in chosen.items()}

        armed: list[RobotClient] = []
        for follower in self._followers:
            offset = assignment[follower.robot_id]
            params = SwarmFollowParams(
                target_robot_id=self._leader.robot_id,
                distance=offset.distance, lateral=offset.lateral,
                max_speed=spec.max_speed, stream_timeout_ms=spec.stream_timeout_ms,
            )
            try:
                await follower.follow(params)
            except RobotApiError as exc:
                await self._disarm(armed)
                raise ArmingFailed(exc.robot_id, exc.code, exc.message) from exc
            except Exception as exc:
                await self._disarm(armed)
                raise ArmingFailed(follower.robot_id, "TRANSPORT", str(exc)) from exc
            armed.append(follower)
        return assignment

    async def _disarm(self, armed: Sequence[RobotClient]) -> None:
        for follower in armed:
            try:
                await follower.swarm_cancel()
            except Exception as exc:
                log.warning("%s: swarm/cancel failed while disarming: %s", follower.robot_id, exc)

    # --- FOR-004 감시 ------------------------------------------------------------

    async def _watch(self, robot: RobotClient) -> None:
        backoff = _BACKOFF_FIRST_S
        first = True
        while True:
            if not first:
                await self._reconcile(robot)
            first = False
            try:
                async for event in robot.events(EVENT_TYPES):
                    backoff = _BACKOFF_FIRST_S
                    await self._handle_event(robot.robot_id, event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("%s: events socket error: %s", robot.robot_id, exc)
            await self._sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX_S)

    async def _reconcile(self, robot: RobotClient) -> None:
        """이벤트 소켓이 끊긴 동안의 이벤트는 놓쳤다. 팔로워가 대형을 떠났는지 직접 본다."""
        if self.state is not SessionState.RUNNING or robot is self._leader:
            return
        try:
            swarm_state = await robot.swarm_state()
        except Exception as exc:
            log.warning("%s: swarm/state unavailable after reconnect: %s", robot.robot_id, exc)
            return
        if not swarm_state.get("active"):
            await self._apply_policy("swarm.aborted", robot.robot_id)

    async def _handle_event(self, robot_id: str, event: dict) -> None:
        type_ = str(event.get("type", ""))
        if type_ == "swarm.hold":
            # 정보다. 릴레이가 멈춰 있으면 우리가 만든 것이고, 아니면 로봇 쪽이 이미 서 있다.
            log.info("%s: swarm.hold %s", robot_id, (event.get("data") or {}).get("reason"))
            return
        if self.state is not SessionState.RUNNING:
            return
        if type_ in TRIGGERS:
            await self._apply_policy(type_, robot_id)

    async def _apply_policy(self, reason: str, robot_id: Optional[str]) -> None:
        if self.state not in (SessionState.RUNNING, SessionState.HOLDING):
            return
        assert self.relay is not None
        if self._policy is HoldPolicy.HOLD:
            # 상태를 먼저 바꾼다 — 아래 await 사이에 들어오는 이벤트는 무시돼야 한다.
            self.relay.pause()
            self.state = SessionState.HOLDING
            self.reason = (reason, robot_id)
            await self._cancel_leader()
            return
        await self._abort(reason, robot_id)

    async def _abort(self, reason: str, robot_id: Optional[str]) -> None:
        """ABORT 정책, 그리고 reform 실패: 전 팔로워를 풀고 릴레이를 끝내고 리더를 세운다."""
        self.state = SessionState.STOPPED
        self.reason = (reason, robot_id)
        if self.relay is not None:
            await self.relay.stop()
        await self._disarm(self._followers)
        await self._cancel_leader()

    async def _cancel_leader(self) -> None:
        try:
            await self._leader.navigation_cancel()
        except Exception as exc:
            log.warning("%s: navigation/cancel failed: %s", self._leader.robot_id, exc)
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_session.py -v`
Expected: PASS (17 passed)

`test_each_for_004_trigger...` 가 `log.index(("rosy_01", "navigation_cancel"))` 에서
실패하면 FakeRobot 의 `_record` 가 `(robot_id, "navigation_cancel")` 을 남기는지 본다 —
Task 6 의 가짜가 그렇게 기록한다.

- [ ] **Step 5: 커밋**

```bash
git add src/rosy_fleet/rosy_fleet/swarm/session.py src/rosy_fleet/test/test_session.py
git commit -m "feat(fleet): arm the formation all-or-nothing, and hold it by withholding the stream

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: 경계 테스트 — `formation/` 은 전송을 모른다

**Files:**
- Create: `src/rosy_fleet/test/test_boundaries.py`

- [ ] **Step 1: 테스트 작성 (바로 통과해야 한다 — 회귀 방지용)**

`src/rosy_fleet/test/test_boundaries.py`:

```python
"""설계 §Architecture: `rosy_fleet.formation` 은 숫자만 다룬다. 전송·ROS·swarm 을
import 하면 순수 함수가 아니게 되고 Windows pytest 도 깨진다."""

import ast
from pathlib import Path

import pytest

FORMATION_DIR = Path(__file__).resolve().parents[1] / "rosy_fleet" / "formation"
FORBIDDEN = ("httpx", "websockets", "rclpy", "rosy_fleet.swarm", "asyncio")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("module", sorted(p.name for p in FORMATION_DIR.glob("*.py")))
def test_formation_modules_import_no_transport(module):
    names = _imports(FORMATION_DIR / module)
    for name in names:
        assert not name.startswith(FORBIDDEN), f"{module} imports {name}"
```

- [ ] **Step 2: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_boundaries.py -v`
Expected: PASS (3 passed — `__init__.py`, `assignment.py`, `geometry.py`)

- [ ] **Step 3: 전체 실행**

Run: `python -m pytest src/rosy_fleet/test -v`
Expected: 전부 PASS. flake8 도 확인한다:

Run: `python -m flake8 src/rosy_fleet/rosy_fleet --max-line-length=120`
Expected: 출력 없음. (flake8 이 없으면 `pip install flake8`.)

- [ ] **Step 4: 커밋**

```bash
git add src/rosy_fleet/test/test_boundaries.py
git commit -m "test(fleet): pin that the formation math never learns about sockets

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: CLI — `rosy_fleet relay` / `rosy_fleet formation`

**Files:**
- Create: `src/rosy_fleet/rosy_fleet/cli.py`
- Create: `src/rosy_fleet/test/test_cli.py`

CLI 는 얇다. 테스트는 인자 파싱과 `robots.yaml` → 리더/팔로워 분리, stdin 명령 한
줄 → 세션 메서드 매핑만 본다. 실제 소켓은 열지 않는다.

- [ ] **Step 1: 실패하는 테스트**

`src/rosy_fleet/test/test_cli.py`:

```python
"""CLI 는 파싱과 배선만 한다. 실제 로봇은 Task 14 의 시뮬 계측이 본다."""

import pytest
from fakes import FakeRobot, run

from rosy_fleet import cli
from rosy_fleet.formation.geometry import Formation
from rosy_fleet.swarm.robots import RobotEndpoint, write_robots
from rosy_fleet.swarm.session import FormationSpec, HoldPolicy


def _write(tmp_path):
    p = tmp_path / "robots.yaml"
    write_robots(p, [RobotEndpoint("rosy_01", "http://a:8080", "t1"),
                     RobotEndpoint("rosy_02", "http://b:8080", "t2"),
                     RobotEndpoint("rosy_03", "http://c:8080", "t3")])
    return p


def test_formation_args_build_a_spec_and_split_leader_from_followers(tmp_path):
    p = _write(tmp_path)
    args = cli.parse_args(["formation", "--robots", str(p), "--leader", "rosy_02",
                           "--formation", "V", "--spacing", "0.7", "--max-speed", "0.12",
                           "--policy", "ABORT", "--grid-cols", "3"])
    leader, followers = cli.split_robots(args)
    assert leader.robot_id == "rosy_02"
    assert [f.robot_id for f in followers] == ["rosy_01", "rosy_03"]
    spec = cli.spec_from(args)
    assert spec == FormationSpec(Formation.V, spacing=0.7, grid_cols=3, max_speed=0.12,
                                 stream_timeout_ms=1000)
    assert cli.policy_from(args) is HoldPolicy.ABORT


def test_an_unknown_leader_is_refused(tmp_path):
    p = _write(tmp_path)
    args = cli.parse_args(["formation", "--robots", str(p), "--leader", "rosy_09"])
    with pytest.raises(SystemExit):
        cli.split_robots(args)


def test_relay_defaults(tmp_path):
    p = _write(tmp_path)
    args = cli.parse_args(["relay", "--robots", str(p), "--leader", "rosy_01"])
    assert args.command == "relay"
    leader, followers = cli.split_robots(args)
    assert leader.robot_id == "rosy_01" and len(followers) == 2


def test_console_commands_map_to_session_methods():
    class Recorder:
        def __init__(self):
            self.calls = []
            self.state = type("S", (), {"value": "RUNNING"})()
            self.reason = None

        async def reform(self, spec):
            self.calls.append(("reform", spec))

        async def resume(self):
            self.calls.append(("resume",))

        async def stop(self):
            self.calls.append(("stop",))

    rec = Recorder()
    base = FormationSpec(Formation.COLUMN, spacing=0.6)
    assert run(cli.handle_command("reform LINE 0.8", rec, base)) is True
    assert run(cli.handle_command("resume", rec, base)) is True
    assert run(cli.handle_command("status", rec, base)) is True
    assert run(cli.handle_command("stop", rec, base)) is False
    assert rec.calls[0] == ("reform", FormationSpec(Formation.LINE, spacing=0.8))
    assert rec.calls[1:] == [("resume",), ("stop",)]


def test_a_bad_console_command_does_not_end_the_session():
    class Recorder:
        state = type("S", (), {"value": "RUNNING"})()
        reason = None

    base = FormationSpec(Formation.COLUMN, spacing=0.6)
    assert run(cli.handle_command("reform TRIANGLE", Recorder(), base)) is True
    assert run(cli.handle_command("dance", Recorder(), base)) is True
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'cli'`

- [ ] **Step 3: 구현**

`src/rosy_fleet/rosy_fleet/cli.py`:

```python
"""rosy_fleet CLI — Fleet 서버가 생기기 전까지 운영자가 대형을 여는 입구.

    rosy_fleet relay     --robots robots.yaml --leader rosy_01
    rosy_fleet formation --robots robots.yaml --leader rosy_01 --formation V --spacing 0.6

`formation` 은 세션을 열고 stdin 명령을 받는다: `reform <FORMATION> [spacing]`,
`resume`, `status`, `stop`. 1 s 마다 릴레이 통계와 세션 상태를 한 줄 찍는다.
SIGINT 는 `stop()` 이다 — 릴레이만 죽이고 팔로워를 무장 상태로 두지 않는다.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import stat
import sys
from pathlib import Path
from typing import Optional, Sequence

from rosy_fleet.formation.geometry import DEFAULT_SPACING, Formation, FormationError
from rosy_fleet.swarm.relay import Relay
from rosy_fleet.swarm.robots import RobotEndpoint, load_robots
from rosy_fleet.swarm.session import FormationSession, FormationSpec, HoldPolicy, SessionError
from rosy_fleet.swarm.transport import HttpRobotClient


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="rosy_fleet")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--robots", required=True, type=Path, help="robots.yaml")
        p.add_argument("--leader", required=True, help="리더 robot_id")

    relay = sub.add_parser("relay", help="리더 pose → 팔로워 reference 릴레이만")
    common(relay)

    formation = sub.add_parser("formation", help="대형 세션 (무장 + 릴레이 + FOR-004)")
    common(formation)
    formation.add_argument("--formation", default="COLUMN", choices=[f.value for f in Formation])
    formation.add_argument("--spacing", type=float, default=DEFAULT_SPACING)
    formation.add_argument("--grid-cols", type=int, default=2)
    formation.add_argument("--max-speed", type=float, default=0.15)
    formation.add_argument("--stream-timeout-ms", type=int, default=1000)
    formation.add_argument("--policy", default="HOLD", choices=[p.value for p in HoldPolicy])
    return parser.parse_args(argv)


def split_robots(args: argparse.Namespace) -> tuple[RobotEndpoint, list[RobotEndpoint]]:
    robots = load_robots(args.robots)
    _warn_if_world_readable(args.robots)
    leaders = [r for r in robots if r.robot_id == args.leader]
    if not leaders:
        sys.exit(f"leader {args.leader!r} is not in {args.robots}")
    return leaders[0], [r for r in robots if r.robot_id != args.leader]


def _warn_if_world_readable(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        if Path(path).stat().st_mode & stat.S_IROTH:
            print(f"warning: {path} is world-readable and holds operator tokens", file=sys.stderr)
    except OSError:
        pass


def spec_from(args: argparse.Namespace) -> FormationSpec:
    return FormationSpec(Formation(args.formation), spacing=args.spacing, grid_cols=args.grid_cols,
                         max_speed=args.max_speed, stream_timeout_ms=args.stream_timeout_ms)


def policy_from(args: argparse.Namespace) -> HoldPolicy:
    return HoldPolicy(args.policy)


async def handle_command(line: str, session, base: FormationSpec) -> bool:
    """stdin 한 줄. 세션을 계속 돌리면 True, 끝내면 False."""
    parts = line.strip().split()
    if not parts:
        return True
    cmd, rest = parts[0].lower(), parts[1:]
    try:
        if cmd == "reform" and rest:
            spacing = float(rest[1]) if len(rest) > 1 else base.spacing
            spec = FormationSpec(Formation(rest[0].upper()), spacing=spacing, grid_cols=base.grid_cols,
                                 max_speed=base.max_speed, stream_timeout_ms=base.stream_timeout_ms)
            await session.reform(spec)
        elif cmd == "resume":
            await session.resume()
        elif cmd == "status":
            print(f"state={session.state.value} reason={session.reason}")
        elif cmd == "stop":
            await session.stop()
            return False
        else:
            print("commands: reform <FORMATION> [spacing] | resume | status | stop")
    except (ValueError, FormationError, SessionError) as exc:
        print(f"refused: {exc}")
    return True


async def _read_stdin(queue: asyncio.Queue) -> None:
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            await queue.put("stop")
            return
        await queue.put(line)


def _stats_line(relay: Relay, session: Optional[FormationSession]) -> str:
    st = relay.stats()
    tx = " ".join(f"{rid}:{hz:.1f}Hz{'' if ok else '!'}"
                  for rid, hz in st.follower_tx_hz.items() for ok in [st.follower_connected[rid]])
    state = f" {session.state.value}" + (f" {session.reason}" if session and session.reason else "") if session else ""
    err = f" LEADER REFUSED: {st.leader_last_error}" if st.leader_last_error else ""
    return f"leader {st.leader_rx_hz:.1f}Hz drop={st.leader_dropped}{' PAUSED' if st.paused else ''}{err} | {tx}{state}"


async def run_relay(args: argparse.Namespace) -> None:
    leader_ep, follower_eps = split_robots(args)
    leader = HttpRobotClient(leader_ep)
    followers = [HttpRobotClient(ep) for ep in follower_eps]
    relay = Relay(leader, followers)
    await relay.start()
    try:
        while True:
            await asyncio.sleep(1.0)
            print(_stats_line(relay, None), flush=True)
    finally:
        await relay.stop()


async def run_formation(args: argparse.Namespace) -> None:
    leader_ep, follower_eps = split_robots(args)
    leader = HttpRobotClient(leader_ep)
    followers = [HttpRobotClient(ep) for ep in follower_eps]
    base = spec_from(args)
    session = FormationSession(leader, followers, base, policy=policy_from(args))
    try:
        await session.start()
    except SessionError as exc:
        sys.exit(f"could not arm the formation: {exc}")
    print(f"armed: {session.assignment}", flush=True)
    commands: asyncio.Queue = asyncio.Queue()
    reader = asyncio.create_task(_read_stdin(commands))
    try:
        while True:
            try:
                line = await asyncio.wait_for(commands.get(), timeout=1.0)
            except asyncio.TimeoutError:
                print(_stats_line(session.relay, session), flush=True)
                continue
            if not await handle_command(line, session, base):
                return
    finally:
        reader.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reader
        if session.state.value != "STOPPED":
            await session.stop()


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    runner = run_relay if args.command == "relay" else run_formation
    try:
        asyncio.run(runner(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 실행해서 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_cli.py -v`
Expected: PASS (5 passed)

Run: `python -m flake8 src/rosy_fleet/rosy_fleet --max-line-length=120`
Expected: 출력 없음.

- [ ] **Step 5: 커밋**

```bash
git add src/rosy_fleet/rosy_fleet/cli.py src/rosy_fleet/test/test_cli.py
git commit -m "feat(fleet): a console entry for the formation until a Fleet server exists

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: CI — `rosy_fleet` 테스트와 lint

**Files:**
- Modify: `.github/workflows/ci.yml` (Lint 스텝과 `Test (rosy_core protocol schemas, P1-19)` 스텝 사이)

- [ ] **Step 1: Lint 대상에 `rosy_fleet` 추가**

`.github/workflows/ci.yml` 의 Lint 스텝을 이렇게 바꾼다:

```yaml
      - name: Lint (flake8)
        run: |
          cd src
          flake8 rosy_core/rosy_core rosy_fleet/rosy_fleet rosy_gz_sim/launch --count --max-line-length=120 --show-source --statistics || true
```

- [ ] **Step 2: 테스트 스텝 추가**

`Test (rosy_core protocol schemas, P1-19)` 스텝 바로 뒤에 넣는다:

```yaml
      # rosy_fleet 은 ROS 를 import 하지 않는다. conftest 가 src/rosy_core 를 sys.path 에
      # 얹으므로 colcon 오버레이 없이도 돈다 — Windows 개발 환경과 같은 조건이다.
      - name: Test (rosy_fleet formation, relay, session)
        run: python3 -m pytest src/rosy_fleet/test/ -v
```

- [ ] **Step 3: 로컬에서 같은 명령으로 확인**

Run: `python -m pytest src/rosy_fleet/test/ -v`
Expected: 전부 PASS.

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run the rosy_fleet tests, which need no ROS overlay

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: `gz_multi.launch.py core:=true` — 로봇별 `rosy_core` 와 `robots.yaml`

**Files:**
- Modify: `src/rosy_gz_sim/launch/gz_multi.launch.py`
- Create: `src/rosy_gz_sim/test/test_gz_multi_core.py`

이 태스크는 ROS 환경(Linux/WSL, `source env.sh`, `colcon build`)이 필요하다. 테스트는
`launch` 가 없으면 skip 한다.

- [ ] **Step 1: 실패하는 테스트 — 순수 헬퍼 두 개와 `OpaqueFunction` 단위 실행**

`src/rosy_gz_sim/test/test_gz_multi_core.py`:

```python
"""gz_multi core:=true — 로봇별 rosy_core 가 서로 다른 포트·HOME·설정으로 뜬다.

런치 파일은 모듈이 아니라 경로로 import 한다. `launch` 가 없는 환경(Windows)은 skip.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

launch = pytest.importorskip("launch")
from launch import LaunchContext  # noqa: E402
from launch_ros.actions import Node  # noqa: E402

LAUNCH = Path(__file__).resolve().parents[1] / "launch" / "gz_multi.launch.py"


def _module():
    spec = importlib.util.spec_from_file_location("gz_multi_launch", LAUNCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_core_config_sets_identity_and_port():
    mod = _module()
    cfg = mod._core_config("rosy_02", 8081)
    assert cfg["robot"]["id"] == "rosy_02"
    assert cfg["robot"]["name"] == "Rosy 02"
    assert cfg["network"]["api_port"] == 8081


def test_robots_manifest_lists_every_core_with_the_dev_operator_token():
    mod = _module()
    rows = mod._robots_manifest(["rosy_01", "rosy_02"], 8080)
    assert rows == [
        {"robot_id": "rosy_01", "base_url": "http://127.0.0.1:8080", "token": "rosy-dev-operator"},
        {"robot_id": "rosy_02", "base_url": "http://127.0.0.1:8081", "token": "rosy-dev-operator"},
    ]


def _setup(mod, **overrides):
    context = LaunchContext()
    context.launch_configurations.update({
        "robots": "3", "prefix": "rosy", "world_name": "rosy_factory.world", "mode": "none",
        "headless": "true", "spawn_spacing": "1.5", "core": "true", "api_port_base": "8080",
        **overrides,
    })
    try:
        return mod._launch_setup(context), context
    except Exception as exc:  # ros_gz_sim 등 share 디렉터리가 없는 러너
        if "not found" in str(exc).lower() or "PackageNotFound" in type(exc).__name__:
            pytest.skip(f"package share missing: {exc}")
        raise


def _text(value, context) -> str:
    """launch 는 문자열을 Substitution 목록으로 정규화해 둔다. 어느 형태든 문자열로."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "".join(_text(v, context) for v in value)
    return value.perform(context)


def _core_nodes(actions, context):
    return [a for a in actions
            if isinstance(a, Node) and _text(a.node_package, context) == "rosy_core"]


def _env(node, context) -> dict:
    # Node → ExecuteLocal.process_description (launch.descriptions.Executable) .additional_env:
    # [(key_substitutions, value_substitutions), ...]
    return {_text(k, context): _text(v, context) for k, v in node.process_description.additional_env}


def test_core_true_adds_one_rosy_core_per_robot_with_distinct_ports_and_homes():
    mod = _module()
    actions, context = _setup(mod)
    cores = _core_nodes(actions, context)
    assert len(cores) == 3
    envs = [_env(a, context) for a in cores]
    assert [e["ROSY_NAMESPACE"] for e in envs] == ["rosy_01", "rosy_02", "rosy_03"]
    assert len({e["HOME"] for e in envs}) == 3
    ports = []
    for e in envs:
        import yaml
        with open(e["ROSY_CONFIG"], encoding="utf-8") as f:
            ports.append(yaml.safe_load(f)["network"]["api_port"])
    assert ports == [8080, 8081, 8082]
    # robots.yaml 은 설정 파일과 같은 임시 디렉터리에 쓰인다.
    manifest = os.path.join(os.path.dirname(envs[0]["ROSY_CONFIG"]), "robots.yaml")
    assert os.path.exists(manifest)


def test_core_false_adds_no_rosy_core():
    mod = _module()
    actions, context = _setup(mod, core="false")
    assert not _core_nodes(actions, context)
```

- [ ] **Step 2: 실행해서 실패 확인 (ROS 환경)**

Run: `source env.sh && python3 -m pytest src/rosy_gz_sim/test/test_gz_multi_core.py -v`
Expected: FAIL — `AttributeError: module 'gz_multi_launch' has no attribute '_core_config'`

Windows 에서는 `SKIPPED (could not import 'launch')` 가 정상이다.

- [ ] **Step 3: 런치 수정 — 헬퍼 두 개, 인자 두 개, 로봇별 노드**

`src/rosy_gz_sim/launch/gz_multi.launch.py` 를 다음과 같이 고친다.

(a) 모듈 상단 docstring 의 "사용 예" 아래에 한 줄 추가:

```python
  ros2 launch rosy_gz_sim gz_multi.launch.py robots:=3 mode:=nav core:=true   # 로봇별 rosy_core, 8080..8082
```

(b) `import yaml` 아래, `BRIDGE_TEMPLATE` 위에 헬퍼를 추가:

```python
#: 시뮬 로봇의 API 토큰. rosy_core 기본 설정(`config/rosy_default.yaml`)의 개발 토큰이다.
SIM_OPERATOR_TOKEN = "rosy-dev-operator"


def _core_config(ns: str, api_port: int) -> dict:
    """로봇별 rosy_core 오버라이드(ROSY_CONFIG). 기본 설정 위에 병합된다.

    frame_prefix 는 ROSY_NAMESPACE 환경변수가 넣으므로 여기 두지 않는다. capabilities 는
    기본 파일이 이미 swarm.follow/lead: true 라 그대로 쓴다.
    """
    number = ns.rsplit("_", 1)[-1]
    return {
        "robot": {"id": ns, "name": f"Rosy {number}"},
        "network": {"api_host": "0.0.0.0", "api_port": api_port},
    }


def _robots_manifest(namespaces: list, api_port_base: int) -> list:
    """rosy_fleet CLI 가 읽는 robots.yaml 의 `robots` 목록."""
    return [
        {"robot_id": ns, "base_url": f"http://127.0.0.1:{api_port_base + i}",
         "token": SIM_OPERATOR_TOKEN}
        for i, ns in enumerate(namespaces)
    ]
```

(c) `_launch_setup` 의 인자 읽는 부분(`spacing = ...` 다음)에 추가:

```python
    core = LaunchConfiguration("core").perform(context).lower() in ("true", "1")
    api_port_base = int(LaunchConfiguration("api_port_base").perform(context))
```

(d) `for i in range(1, robots + 1):` 루프 안, `# 4) Nav2 / SLAM (mode)` 블록 **뒤**,
`actions.extend(group_actions)` **앞**에 추가:

```python
        # 5) rosy_core (core:=true) — 로봇마다 포트·HOME·설정을 가른다.
        #    HOME 을 가르는 이유: waypoints.json 과 audit.jsonl 이 Path.home()/.rosy 에
        #    고정돼 있어, 같은 HOME 이면 N대가 한 파일을 쓴다.
        if core:
            core_home = os.path.join(bridge_dir, f"home_{ns}")
            os.makedirs(core_home, exist_ok=True)
            core_cfg = os.path.join(bridge_dir, f"rosy_{ns}.yaml")
            with open(core_cfg, "w") as f:
                yaml.safe_dump(_core_config(ns, api_port_base + i - 1), f)
            group_actions.append(
                Node(
                    package="rosy_core",
                    executable="rosy_core",
                    name="rosy_core",
                    namespace=ns,
                    output="screen",
                    parameters=[{"use_sim_time": True}],
                    additional_env={
                        "ROSY_NAMESPACE": ns,
                        "ROSY_CONFIG": core_cfg,
                        "HOME": core_home,
                    },
                )
            )
```

(e) 루프가 끝난 뒤, `return actions` **앞**에 robots.yaml 생성과 안내 로그를 추가:

```python
    if core:
        namespaces = [f"{prefix}_{i:02d}" for i in range(1, robots + 1)]
        manifest_path = os.path.join(bridge_dir, "robots.yaml")
        with open(manifest_path, "w") as f:
            yaml.safe_dump({"robots": _robots_manifest(namespaces, api_port_base)}, f, sort_keys=False)
        actions.append(LogInfo(msg=f"rosy_fleet robots.yaml: {manifest_path}"))
```

`LogInfo` 를 import 에 추가한다 (`from launch.actions import (... LogInfo, ...)`).

(f) `generate_launch_description` 의 `DeclareLaunchArgument` 목록에 두 개 추가
(`OpaqueFunction` 앞):

```python
        DeclareLaunchArgument("core", default_value="false",
                              description="로봇별 rosy_core 기동 (포트 api_port_base + i - 1)"),
        DeclareLaunchArgument("api_port_base", default_value="8080",
                              description="첫 로봇의 rosy_core API 포트"),
```

- [ ] **Step 4: 실행해서 통과 확인 (ROS 환경)**

Run: `source env.sh && cd src && colcon build --symlink-install --packages-select rosy_gz_sim rosy_fleet && cd .. && python3 -m pytest src/rosy_gz_sim/test/test_gz_multi_core.py -v`
Expected: PASS (4 passed). `ros_gz_sim` 이 없는 러너에서는 마지막 두 개가 SKIPPED.

Run: `python3 -m flake8 src/rosy_gz_sim/launch --max-line-length=120`
Expected: 출력 없음.

- [ ] **Step 5: 선행 관문 — `gz_multi` nav 모드가 실제로 도는지**

설계 §Risks 의 첫 항목이다. ROS + Gazebo 환경에서:

```bash
source env.sh
ros2 launch rosy_gz_sim gz_multi.launch.py robots:=2 mode:=nav core:=true headless:=true
```

다른 터미널에서 60 s 뒤:

```bash
ros2 topic list | grep -E "rosy_0[12]/(amcl_pose|cmd_vel|scan)$"
ros2 run tf2_ros tf2_echo map rosy_01/base_footprint    # TF 가 나오면 프레임 접두가 맞다
curl -s -H "Authorization: Bearer rosy-dev-viewer" http://127.0.0.1:8080/api/v1/robot/state | head -c 300
curl -s -H "Authorization: Bearer rosy-dev-viewer" http://127.0.0.1:8081/api/v1/robot/state | head -c 300
```

Expected: 두 로봇의 토픽, TF 조회 성공, 두 포트에서 각각 `"robot_id": "rosy_01"` / `"rosy_02"`
와 `pose` 가 0 이 아닌 값.

**여기서 막히면 이 슬라이스보다 그 수정이 먼저다.** 흔한 원인: `nav2_params.yaml` 의
프레임 이름이 `frame_prefix` 와 맞물리지 않음(계획서 P0-2/P0-3), AMCL 초기 pose 미설정
(`POST /api/v1/localization/initialpose` 로 스폰 좌표를 넣는다: 로봇 i 는
`x = (i-1) * spawn_spacing, y = 0, yaw = 0`). 발견한 것은 실행 계획서 §결과 에 적는다.

- [ ] **Step 6: 커밋**

```bash
git add src/rosy_gz_sim/launch/gz_multi.launch.py src/rosy_gz_sim/test/test_gz_multi_core.py
git commit -m "feat(sim): start one rosy_core per simulated robot, each on its own port and home

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: 시뮬 계측 스크립트 `swarm_bench.py`

**Files:**
- Create: `src/rosy_gz_sim/scripts/swarm_bench.py`
- Modify: `src/rosy_gz_sim/CMakeLists.txt` (`install(DIRECTORY ...)` 앞)
- Modify: `src/rosy_gz_sim/package.xml` (`<exec_depend>rosy_fleet</exec_depend>` 추가)

스크립트는 `rosy_fleet` 만 쓴다 — rclpy 없음. stuck 주입만 `gz service` 서브프로세스다.

- [ ] **Step 1: 스크립트 작성**

`src/rosy_gz_sim/scripts/swarm_bench.py`:

```python
#!/usr/bin/env python3
"""Swarm formation bench — 리더를 몰고 팔로워를 계측한다. rclpy 없이 rosy_fleet 만 쓴다.

시나리오:
  follow  3대 COLUMN, 리더가 waypoint 를 순회. slot_err_m 과 stream 주기.
  reform  주행 중 LINE → V. 재배정과 수렴.
  hold    릴레이 pause 주입 → 전원 holding 까지의 시간.
  stuck   팔로워 하나 앞에 장애물 스폰 → nav.stuck → 세션 HOLDING 까지의 시간.

CSV 열: t, scenario, robot_id, state, holding, stream_age_s, slot_err_m, relay_tx_hz

Design: docs/plans/2026-09-08-swarm-formation-slice-design.md §8.2
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import subprocess
import sys
import time
from pathlib import Path

from rosy_fleet.formation.geometry import Formation, slot_world_position
from rosy_fleet.swarm.robots import load_robots
from rosy_fleet.swarm.session import FormationSession, FormationSpec, SessionState
from rosy_fleet.swarm.transport import HttpRobotClient

OBSTACLE_SDF = """<sdf version='1.9'><model name='{name}'><static>true</static>
<link name='l'><collision name='c'><geometry><box><size>0.3 0.6 0.5</size></box></geometry></collision>
<visual name='v'><geometry><box><size>0.3 0.6 0.5</size></box></geometry></visual></link></model></sdf>"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="swarm_bench")
    p.add_argument("--robots", type=Path, required=True, help="gz_multi core:=true 가 쓴 robots.yaml")
    p.add_argument("--leader", default="rosy_01")
    p.add_argument("--scenario", choices=["follow", "reform", "hold", "stuck"], default="follow")
    p.add_argument("--formation", default="COLUMN", choices=[f.value for f in Formation])
    p.add_argument("--spacing", type=float, default=0.6)
    p.add_argument("--waypoints", default="1.5,0,0;1.5,1.0,1.57;0,1.0,3.14;0,0,0",
                   help="x,y,yaw;x,y,yaw;... (리더 목표 순서)")
    p.add_argument("--duration", type=float, default=90.0, help="계측 시간 (s)")
    p.add_argument("--inject-at", type=float, default=30.0, help="hold/stuck 주입 시각 (s)")
    p.add_argument("--world", default="rosy_factory")
    p.add_argument("--out", type=Path, default=Path("swarm_bench.csv"))
    return p.parse_args(argv)


def _parse_waypoints(text: str) -> list[tuple[float, float, float]]:
    out = []
    for chunk in text.split(";"):
        x, y, yaw = (float(v) for v in chunk.split(","))
        out.append((x, y, yaw))
    return out


async def _drive_leader(leader: HttpRobotClient, waypoints, stop: asyncio.Event) -> None:
    """리더에 목표를 차례로 건다. 다음 목표는 항법이 IDLE/ARRIVED 로 돌아오면."""
    i = 0
    while not stop.is_set():
        x, y, yaw = waypoints[i % len(waypoints)]
        try:
            await leader.navigation_goal(x, y, yaw)
        except Exception as exc:
            print(f"leader goal refused: {exc}", file=sys.stderr)
            await asyncio.sleep(2.0)
            continue
        await asyncio.sleep(2.0)
        while not stop.is_set():
            state = await leader.state()
            if state.get("navigation") in ("IDLE", "ARRIVED", "FAILED", "CANCELED", "BLOCKED"):
                break
            await asyncio.sleep(0.5)
        i += 1


def _spawn_obstacle(world: str, x: float, y: float, name: str) -> None:
    # SDF 템플릿은 홑따옴표만 쓰므로 protobuf 텍스트의 쌍따옴표 안에 그대로 들어간다.
    sdf = OBSTACLE_SDF.format(name=name).replace("\n", " ")
    req = f'sdf: "{sdf}" pose: {{position: {{x: {x}, y: {y}, z: 0.25}}}}'
    subprocess.run(["gz", "service", "-s", f"/world/{world}/create",
                    "--reqtype", "gz.msgs.EntityFactory", "--reptype", "gz.msgs.Boolean",
                    "--timeout", "2000", "--req", req], check=False)


async def main_async(args) -> int:
    robots = load_robots(args.robots)
    clients = {r.robot_id: HttpRobotClient(r) for r in robots}
    leader = clients[args.leader]
    followers = [c for rid, c in clients.items() if rid != args.leader]
    spec = FormationSpec(Formation(args.formation), spacing=args.spacing)
    session = FormationSession(leader, followers, spec)
    await session.start()
    print(f"armed: {session.assignment}")

    stop = asyncio.Event()
    driver = asyncio.create_task(_drive_leader(leader, _parse_waypoints(args.waypoints), stop))
    t0 = time.monotonic()
    injected = False
    inject_t = None
    reached_t = None

    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t", "scenario", "robot_id", "state", "holding", "stream_age_s", "slot_err_m", "relay_tx_hz"])
        try:
            while time.monotonic() - t0 < args.duration:
                t = time.monotonic() - t0
                if not injected and t >= args.inject_at and args.scenario in ("reform", "hold", "stuck"):
                    injected, inject_t = True, t
                    if args.scenario == "reform":
                        await session.reform(FormationSpec(Formation.V, spacing=args.spacing))
                    elif args.scenario == "hold":
                        session.relay.pause()
                    else:
                        victim = followers[0]
                        st = await victim.state()
                        pose = st.get("pose") or {}
                        yaw = float(pose.get("yaw", 0.0))
                        _spawn_obstacle(args.world, float(pose["x"]) + 0.5 * math.cos(yaw),
                                        float(pose["y"]) + 0.5 * math.sin(yaw), "bench_block")
                lstate = await leader.state()
                lp = lstate.get("pose") or {}
                stats = session.relay.stats()
                all_holding = True
                for f in followers:
                    sw = await f.swarm_state()
                    st = await f.state()
                    fp = st.get("pose") or {}
                    off = session.assignment.get(f.robot_id)
                    err = ""
                    if off is not None:
                        sx, sy = slot_world_position(off, float(lp.get("x", 0)), float(lp.get("y", 0)), float(lp.get("yaw", 0)))
                        err = f"{math.dist((sx, sy), (float(fp.get('x', 0)), float(fp.get('y', 0)))):.3f}"
                    holding = bool(sw.get("holding"))
                    all_holding = all_holding and holding
                    w.writerow([f"{t:.1f}", args.scenario, f.robot_id, session.state.value, holding,
                                sw.get("stream_age_s"), err, f"{stats.follower_tx_hz.get(f.robot_id, 0.0):.1f}"])
                fh.flush()
                if injected and reached_t is None:
                    if args.scenario == "hold" and all_holding:
                        reached_t = t
                        print(f"HOLD reached after {reached_t - inject_t:.2f} s")
                    if args.scenario == "stuck" and session.state is SessionState.HOLDING:
                        reached_t = t
                        print(f"FOR-004 HOLD after {reached_t - inject_t:.2f} s: {session.reason}")
                await asyncio.sleep(1.0)
        finally:
            stop.set()
            driver.cancel()
            await session.stop()
            for c in clients.values():
                await c.aclose()
    print(f"wrote {args.out}")
    return 0


def main(argv=None) -> int:
    return asyncio.run(main_async(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: CMake 설치와 의존 선언**

`src/rosy_gz_sim/CMakeLists.txt` 의 `install(DIRECTORY ...)` 블록 **앞**에:

```cmake
install(
  PROGRAMS
    scripts/swarm_bench.py
  DESTINATION lib/${PROJECT_NAME}
)
```

`src/rosy_gz_sim/package.xml` 의 `<depend>gz_ros2_control</depend>` 아래에:

```xml
  <!-- scripts/swarm_bench.py 가 rosy_fleet 를 import 한다. 런타임 의존이지 빌드 의존이 아니다. -->
  <exec_depend>rosy_fleet</exec_depend>
```

- [ ] **Step 3: 파싱만 로컬 확인 (Windows 가능)**

Run: `python -c "import sys; sys.path[:0]=['src/rosy_fleet','src/rosy_core']; sys.argv=['x','--robots','r.yaml','--scenario','stuck']; import importlib.util as u; s=u.spec_from_file_location('b','src/rosy_gz_sim/scripts/swarm_bench.py'); m=u.module_from_spec(s); s.loader.exec_module(m); a=m.parse_args(); print(a.scenario, m._parse_waypoints(a.waypoints)[1])"`
Expected: `stuck (1.5, 1.0, 1.57)`

Run: `python -m flake8 src/rosy_gz_sim/scripts --max-line-length=120`
Expected: 출력 없음.

- [ ] **Step 4: 커밋**

```bash
git add src/rosy_gz_sim/scripts/swarm_bench.py src/rosy_gz_sim/CMakeLists.txt src/rosy_gz_sim/package.xml
git commit -m "feat(sim): a bench that drives the leader and records what every follower did

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 14: 시뮬 계측 실행과 결과 기록

**Files:**
- Create: `docs/plans/2026-09-08-swarm-formation-slice-results.md`
- Modify: `docs/plans/AGENTS.md` (인덱스 행 추가)

ROS + Gazebo 환경. 각 시나리오는 별도 런치 세션에서 돈다 (stuck 의 장애물이 남기 때문).

- [ ] **Step 1: 3대 nav+core 기동**

```bash
source env.sh
ros2 launch rosy_gz_sim gz_multi.launch.py robots:=3 mode:=nav core:=true headless:=true
# 런치 로그에서 "rosy_fleet robots.yaml: /tmp/rosy_gz_multi_XXXX/robots.yaml" 을 찾는다.
export ROBOTS=/tmp/rosy_gz_multi_XXXX/robots.yaml
```

AMCL 초기 pose 가 필요하면 로봇 i 마다 (포트 8080+i−1):

```bash
curl -s -X POST -H "Authorization: Bearer rosy-dev-operator" -H "Content-Type: application/json" \
  -d '{"x": 0.0, "y": 0.0, "yaw": 0.0}' http://127.0.0.1:8080/api/v1/localization/initialpose
curl -s -X POST -H "Authorization: Bearer rosy-dev-operator" -H "Content-Type: application/json" \
  -d '{"x": 1.5, "y": 0.0, "yaw": 0.0}' http://127.0.0.1:8081/api/v1/localization/initialpose
curl -s -X POST -H "Authorization: Bearer rosy-dev-operator" -H "Content-Type: application/json" \
  -d '{"x": 3.0, "y": 0.0, "yaw": 0.0}' http://127.0.0.1:8082/api/v1/localization/initialpose
```

- [ ] **Step 2: 4개 시나리오**

```bash
ros2 run rosy_gz_sim swarm_bench.py --robots $ROBOTS --scenario follow --duration 90 --out follow.csv
ros2 run rosy_gz_sim swarm_bench.py --robots $ROBOTS --scenario reform --inject-at 30 --duration 90 --out reform.csv
ros2 run rosy_gz_sim swarm_bench.py --robots $ROBOTS --scenario hold   --inject-at 30 --duration 45 --out hold.csv
# 새 런치 세션에서:
ros2 run rosy_gz_sim swarm_bench.py --robots $ROBOTS --scenario stuck  --inject-at 30 --duration 120 --out stuck.csv
```

Expected: 각 실행이 `armed: {...}` 를 찍고 CSV 를 쓴다. hold 는 `HOLD reached after N s`,
stuck 은 `FOR-004 HOLD after N s: ('nav.stuck', 'rosy_02')` 를 찍는다.

- [ ] **Step 3: 결과 문서**

`docs/plans/2026-09-08-swarm-formation-slice-results.md` 를 아래 표로 쓴다. 숫자는
CSV 에서 읽은 **실측**이다 — 측정하지 못한 칸은 비우고 그 이유를 적는다. (이 저장소의
교훈: 확인하지 못한 것을 깨끗한 결과로 적지 않는다,
`docs/solutions/workflow-issues/inability-to-check-recorded-as-clean-result.md`.)

```markdown
# 군집 대형 슬라이스 — 시뮬 계측 결과

설계: `2026-09-08-swarm-formation-slice-design.md` §Testing Strategy.
환경: (ROS 배포판 / Gazebo 버전 / 호스트 / 날짜)

| 항목 | 기준 | 실측 | 판정 | 출처 |
|---|---|---|---|---|
| 스트림 | 팔로워별 `relay_tx_hz ≥ 10` | | | follow.csv |
| 추종 | 정상 주행 `slot_err_m` 중앙값 (기준값은 이 값이 정한다), holding 없음 | | | follow.csv |
| 재배정 | LINE → V 뒤 새 슬롯 수렴, 교차 없음 | | | reform.csv |
| HOLD | pause 뒤 전원 holding ≤ 1 s + 폴링 간격 1 s | | | hold.csv, 콘솔 |
| FOR-004 | stuck 뒤 전원 정지, 리더 nav.canceled | | | stuck.csv, 콘솔 |

## 선행 관문 (Task 12 Step 5) 에서 발견한 것

(gz_multi nav 모드가 그대로 돌았는지, 무엇을 고쳐야 했는지)

## 관찰

(2 Hz 목표 교체 때 Nav2 거동, 리더 회전 시 측방 슬롯 진동, 기타)

## D-35 등록 여부

HOLD ≤ 1 s 가 실측으로 보이면 ADR Log 에 D-35 를 올린다. 아니면 그 이유.
```

`docs/plans/AGENTS.md` 의 Key Files 표에서 `2026-09-08-swarm-formation-slice.md` 행을 이렇게 바꾼다:

```markdown
| `2026-09-08-swarm-formation-slice.md` (+ `-results`) | Execution plan for the Fleet-less formation slice, and the sim bench numbers it produced |
```

- [ ] **Step 4: 커밋**

```bash
git add docs/plans/2026-09-08-swarm-formation-slice-results.md docs/plans/AGENTS.md
git commit -m "docs(swarm): record what the sim bench measured, and what it could not

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 15: 마무리 — 패키지 인덱스, 전체 테스트, D-35 판단

**Files:**
- Create: `src/rosy_fleet/AGENTS.md`
- Modify: `src/AGENTS.md` (Subdirectories 표에 `rosy_fleet/` 행)
- Modify: `docs/plans/AGENTS.md` (Task 14 에서 행을 넣었으면 확인만)
- Modify (조건부): `docs/reference/ROSY ADR Log.md` — Task 14 결과가 HOLD ≤ 1 s 를 보였을 때만

- [ ] **Step 0: 패키지 인덱스** — Task 1 리뷰가 잡은 누락. 워크스페이스의 다른 11개 패키지는
  전부 `AGENTS.md` 를 갖고 `src/AGENTS.md` 표에 올라 있다. 패키지 내용이 다 갖춰진 지금 쓴다.

`src/rosy_fleet/AGENTS.md` — `src/rosy_core/AGENTS.md` 와 같은 골격(Purpose / Key Files /
Subdirectories / For AI Agents / Dependencies). 내용은 이 계획의 File Structure 표에서 가져온다:
Purpose 는 "Fleet 쪽 씨앗 — 대형 기하·슬롯 배정·참조 스트림 릴레이·FOR-004 세션·CLI. Fleet
서버 본체는 없다(Phase 4). 로봇 계약만 소비하고 `rosy_core` 는 스키마 재사용을 위해 import
한다(D-18)." Working-in-this-directory 규칙 세 줄: `formation/` 은 전송을 모른다(`test_boundaries.py`
가 지킨다); 릴레이는 프레임을 바꾸지 않는다; 로봇 쪽 `rosy_core` 를 여기서 고치지 않는다.
Testing: `python -m pytest src/rosy_fleet/test -v` (ROS 불필요).

`src/AGENTS.md` Subdirectories 표에 한 행:

```markdown
| `rosy_fleet/` | Fleet seed: formation geometry, slot assignment, reference-stream relay, FOR-004 session, CLI (see `rosy_fleet/AGENTS.md`) |
```

- [ ] **Step 1: 전체 호스트 테스트**

Run: `python -m pytest src/rosy_fleet/test src/rosy_core/test -q`
Expected: 전부 PASS. `rosy_core` 테스트에 변화가 없어야 한다 — 이 슬라이스는 로봇 쪽을 건드리지 않았다.

Run: `git diff main --stat -- src/rosy_core`
Expected: 출력 없음.

- [ ] **Step 2: D-35 (조건부)**

Task 14 의 HOLD 실측이 1 s + 폴링 간격 안이면 `docs/reference/ROSY ADR Log.md` 의 표에
행을 추가하고 본문 끝에 항목을 쓴다. 실측이 없거나 기준을 넘으면 이 스텝은 건너뛰고
결과 문서에 그 이유를 남긴다.

표 행 (D-34 행 아래):

```markdown
| D-35 | 대형 전체 HOLD 는 참조 스트림을 끊는 것으로 만든다 — 새 엔드포인트가 아니다 | Accepted |
```

본문 (D-34 항목 뒤):

```markdown
## D-35 대형 전체 HOLD 는 참조 스트림을 끊는 것으로 만든다

**Status:** Accepted (실측 날짜) — FOR-004 구현 결정

**Context:** FOR-004 는 한 대가 BLOCKED/FAILED/stuck 이면 "형성 중단 + 전체 HOLD" 를
요구한다. 로봇 API 에는 hold 엔드포인트가 없다. 추가하면 계약 개정이고, 이미 있는
SWM-004(스트림 단절 → 자리 유지)와 의미가 겹치는 두 번째 HOLD 경로가 생긴다.

**Decision:** 오케스트레이터(`rosy_fleet.swarm.session`)는 릴레이를 멈춰 참조 스트림을
끊는다. 팔로워 전원은 SWM-004 로 `stream_timeout_ms` 안에 자리를 지키고, 리더 항법만
`navigation/cancel` 한다. 팔로워의 follow 세션은 살아 있어 재개는 릴레이를 다시 켜는
것이며, 재개는 운영자 명령이다.

**Consequences:** 로봇 계약이 그대로다. HOLD 경로가 하나라 릴레이 장애와 의도된 HOLD 가
로봇에서 같은 코드를 밟는다. HOLD 진입에 `stream_timeout_ms`(기본 1 s) 가 걸린다 —
시뮬 실측 (값) s. 급한 정지는 HOLD 가 아니라 e-stop 이며 별도 경로다. 실측:
`docs/plans/2026-09-08-swarm-formation-slice-results.md`.
```

- [ ] **Step 3: 커밋**

```bash
git add src/rosy_fleet/AGENTS.md src/AGENTS.md docs/plans/AGENTS.md
git commit -m "docs(fleet): index the rosy_fleet package where the other eleven are indexed

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
# D-35 를 썼을 때만:
git add docs/reference/ROSY\ ADR\ Log.md
git commit -m "docs(adr): D-35 — the formation-wide HOLD is the stream going quiet, now measured

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 4: 다음 슬라이스 메모**

결과 문서 끝에 "다음 슬라이스" 절을 두 줄로 남긴다: 실물 2대 FAT-06 변형(릴레이 pause
주입), `deploy/robot/config/capabilities.hardware.yaml` 의 `swarm.follow/lead` 점등.
이 슬라이스에서는 켜지 않는다 (설계 Non-Goals).

---

## Self-Review

**Spec coverage.**
- §1 대형 기하 → Task 2. 6종, 하한, FOLLOW 1대, grid_cols, CIRCLE 현 길이, `slot_world_position` 전부 테스트.
- §2 슬롯 배정 → Task 3. 프로토콜, 그리디, 전단사·순서불변·비교차·개수 거절.
- §3 로봇 목록·전송 → Task 4, 5. robots.yaml, ws_url, RobotClient 8개 메서드, ERR-101 파싱, world-readable 경고(CLI, Task 10).
- §4 릴레이 → Task 7. 합성 없음, 소켓별 독립, 깊이 1, pause/resume, 계측(seq 갭), stop 이 sink 를 닫음.
- §5 세션 → Task 8. start(map 검사·배정·전부 아니면 전무·릴레이·감시), reform, resume, stop(리더 항법은 건드리지 않음).
  **설계 변경 하나:** reform 실패는 정책과 무관하게 세션을 끝낸다(STOPPED). 계획을 쓰다 보니
  HOLD 로 두면 재무장된 팔로워는 풀리고 나머지는 옛 오프셋을 쥔 절반 대형이 남아, resume 이
  그것을 그대로 살린다는 것이 드러났다. 설계 문서 §5·§9 를 같은 날 고쳤다.
- §6 FOR-004 → Task 8. 5개 트리거, 리더 이벤트 포함, swarm.hold 비트리거, HOLDING 중 무시, HOLD/ABORT 정책, 이벤트 소켓 재연결 후 reconcile.
- §7 CLI → Task 10. §8.1 런치 → Task 12 (HOME 분리, ROSY_CONFIG, 포트, robots.yaml). §8.2 bench → Task 13, 4 시나리오.
- §9 오류 처리 표 → Task 7/8/10 (SIGINT → stop). Testing Strategy 의 `test_boundaries` → Task 9. CI → Task 11. 계측 완료 기준 → Task 14. D-35 → Task 15.

**Placeholder scan.** 결과 문서(Task 14)의 빈 "실측" 칸은 의도된 것이다 — 측정 전에는
채울 수 없고, 채우지 않은 채 남기는 것이 이 저장소의 규칙이다. 그 외 TBD/TODO 없음.

**Type consistency.** `SlotOffset(distance, lateral)`, `slots(formation, followers, spacing, *, grid_cols)`,
`slot_world_position(offset, x, y, yaw)`, `SlotAssigner.assign(robots, slots) -> dict[str, int]`,
`RobotClient` 메서드 이름(`state`, `swarm_state`, `follow`, `swarm_cancel`, `navigation_cancel`,
`navigation_goal`, `pose_stream`, `open_reference_sink`, `events`), `Relay(leader, followers, *, clock, reconnect_max_s, sleep)`
와 `pause/resume/stats/is_connected`, `FormationSession(leader, followers, spec, *, assigner, policy, relay_factory, sleep)`
와 `state/reason/assignment/relay`, `FormationSpec(formation, spacing, grid_cols, max_speed, stream_timeout_ms)`,
`HoldPolicy.HOLD/ABORT`, `SessionState` 다섯 값 — Task 2~13 과 bench 가 같은 이름을 쓴다.
`FakeRelay(leader, followers, *, log, **_)` 는 `relay_factory(self._leader, self._followers)` 호출 형태와 맞는다.
