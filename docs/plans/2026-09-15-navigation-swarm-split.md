# Navigation / Swarm Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 로봇 쪽 추종(SWM)을 `rosy_core.navigation`에서 `rosy_core.swarm`으로 옮겨, 항법은 목표 실행만 하고 추종은 따라갈 점만 넣게 한다. 동작은 바꾸지 않는다.

**Architecture:** `poses.py`는 참조 표본과 오프셋, `manager.py`는 세션이다. 의존은 swarm → navigation만. `navigation/swarm.py`는 삭제하고 이중 경로는 두지 않는다. 설계: `docs/plans/2026-09-15-navigation-swarm-split-design.md` (D-60).

**Tech Stack:** Python 3.12, 기존 ROS-free pytest. 새 의존성 없음.

**이 계획이 아닌 것:** mapping 패키지, Hub listen, FleetAgent outbound, 추종 동작 변경, 새 ROS 패키지.

**Windows:** `Rosy OS` 루트. `src/rosy_core/test/conftest.py`가 패키지를 잡는다. 필요하면 `$env:PYTHONPATH="src/rosy_core"`.

**커밋:** `type(scope): 무엇을 왜`

---

## File Structure (목표)

| 파일 | 책임 |
|---|---|
| `src/rosy_core/rosy_core/swarm/poses.py` | `ReferencePose`, `follow_goal` |
| `src/rosy_core/rosy_core/swarm/manager.py` | `SwarmManager`, `SwarmError`, `MAX_GOAL_RATE_HZ` |
| `src/rosy_core/rosy_core/swarm/__init__.py` | 위 심볼 재수출 |
| `src/rosy_core/rosy_core/swarm/AGENTS.md` | SWM만 주장 |
| `src/rosy_core/test/test_navigation_swarm_boundary.py` | navigation 트리가 swarm을 import하지 않음 |
| 삭제 | `src/rosy_core/rosy_core/navigation/swarm.py` |

Import를 바꿀 생산 코드: `services.py`, `api/v1/swarm.py`, `api/ws.py`.  
시험: `test_swarm.py`, `test_swarm_api.py`, `test_swarm_stream.py`, `test_swarm_integration.py`.  
Fleet: `src/rosy_fleet/test/test_geometry.py`, `formation/geometry.py` 주석, `formation/AGENTS.md`.

---

### Task 1: `follow_goal`을 `rosy_core.swarm.poses`로

**Files:**
- Create: `src/rosy_core/rosy_core/swarm/__init__.py`
- Create: `src/rosy_core/rosy_core/swarm/poses.py`
- Modify: `src/rosy_core/test/test_swarm.py` — `follow_goal` / `ReferencePose` import만 새 경로. `SwarmManager`는 아직 옛 경로.

- [ ] **Step 1: 실패하는 테스트**

`test_swarm.py`의 `follow_goal` 세 테스트가 쓰는 import를 먼저 바꾼다:

```python
from rosy_core.swarm.poses import ReferencePose, follow_goal
from rosy_core.navigation.swarm import (
    MAX_GOAL_RATE_HZ,
    SwarmError,
    SwarmManager,
)
```

(`ReferencePose`를 옛 모듈에서 지우면 SwarmManager 테스트가 깨지므로, Step 3에서 옛 `swarm.py`가 `poses`를 re-export하거나 같은 클래스를 쓰게 한다. 최종 Task 2에서 옛 파일을 지운다.)

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_core/test/test_swarm.py::test_follow_goal_behind_the_leader -v`  
(테스트 이름이 다르면 `test_swarm.py`에서 `follow_goal(` 호출이 있는 첫 함수.)

Expected: FAIL — `ModuleNotFoundError: rosy_core.swarm`

- [ ] **Step 3: poses.py**

`src/rosy_core/rosy_core/swarm/poses.py` — `navigation/swarm.py`의 `ReferencePose`와 `follow_goal`을 **그대로** 옮긴다 (`NavGoalSpec` import 유지).

`src/rosy_core/rosy_core/swarm/__init__.py`:

```python
"""Robot-side follow (SWM-001~007). Navigation executes goals; this package only aims."""

from rosy_core.swarm.poses import ReferencePose, follow_goal

__all__ = ["ReferencePose", "follow_goal"]
```

`navigation/swarm.py` 상단의 `ReferencePose` / `follow_goal` 정의를 지우고 대신:

```python
from rosy_core.swarm.poses import ReferencePose, follow_goal
```

이 한 줄은 Task 2에서 파일과 함께 사라진다. 지금은 중복 클래스 두 개를 만들지 않기 위한 임시 의존이다.

- [ ] **Step 4: 통과**

Run: `python -m pytest src/rosy_core/test/test_swarm.py -q`

Expected: PASS (기존과 같은 수)

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/swarm src/rosy_core/rosy_core/navigation/swarm.py src/rosy_core/test/test_swarm.py
git commit -m "refactor(swarm): extract follow_goal poses out of navigation"
```

---

### Task 2: SwarmManager를 `rosy_core.swarm.manager`로 옮기고 옛 파일 삭제

**Files:**
- Create: `src/rosy_core/rosy_core/swarm/manager.py`
- Delete: `src/rosy_core/rosy_core/navigation/swarm.py`
- Modify imports in:
  - `src/rosy_core/rosy_core/services.py`
  - `src/rosy_core/rosy_core/api/v1/swarm.py`
  - `src/rosy_core/rosy_core/api/ws.py`
  - `src/rosy_core/test/test_swarm.py`
  - `src/rosy_core/test/test_swarm_api.py` (SwarmError 경로)
  - `src/rosy_core/test/test_swarm_stream.py`
  - `src/rosy_core/test/test_swarm_integration.py`

- [ ] **Step 1: 실패하는 테스트**

`test_swarm.py`에서 `SwarmManager` / `SwarmError` / `MAX_GOAL_RATE_HZ` import를 `rosy_core.swarm`으로 바꾼다.

```python
from rosy_core.swarm import (
    MAX_GOAL_RATE_HZ,
    ReferencePose,
    SwarmError,
    SwarmManager,
    follow_goal,
)
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_core/test/test_swarm.py::test_follow_starts_a_moving_session -v`  
(함수명이 다르면 `SwarmManager(`를 쓰는 첫 테스트.)

Expected: FAIL — `cannot import name SwarmManager from rosy_core.swarm`

- [ ] **Step 3: 이동**

`navigation/swarm.py`의 `SwarmError`, `MAX_GOAL_RATE_HZ`, `_MIN_GOAL_INTERVAL_S`, `SwarmManager`를 `swarm/manager.py`로 옮긴다. 모듈 docstring은 `rosy_core.swarm.manager`로 바꾼다. `follow_goal` / `ReferencePose`는 `from rosy_core.swarm.poses import ...`.

`swarm/__init__.py`:

```python
from rosy_core.swarm.manager import MAX_GOAL_RATE_HZ, SwarmError, SwarmManager
from rosy_core.swarm.poses import ReferencePose, follow_goal

__all__ = [
    "MAX_GOAL_RATE_HZ",
    "ReferencePose",
    "SwarmError",
    "SwarmManager",
    "follow_goal",
]
```

생산·시험 import를 모두 `rosy_core.swarm`으로 바꾼다. `navigation/swarm.py`를 **삭제**한다. `from rosy_core.navigation.swarm import`가 트리에 남아 있으면 안 된다.

- [ ] **Step 4: 통과**

```
python -m pytest src/rosy_core/test/test_swarm.py src/rosy_core/test/test_swarm_api.py src/rosy_core/test/test_swarm_stream.py src/rosy_core/test/test_swarm_integration.py -q
```

Expected: PASS. 실패하면 빠진 import 경로를 고친다. 동작을 바꾸지 마라.

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/swarm src/rosy_core/rosy_core/navigation src/rosy_core/rosy_core/services.py src/rosy_core/rosy_core/api src/rosy_core/test
git commit -m "refactor(swarm): move SwarmManager out of navigation"
```

---

### Task 3: navigation은 swarm을 import하지 않는다

**Files:**
- Create: `src/rosy_core/test/test_navigation_swarm_boundary.py`

- [ ] **Step 1: 실패하는 테스트 (이미 초록일 수 있음 — 그때는 잠금으로 둔다)**

```python
"""D-60: navigation does not import swarm. Swarm aims; navigation executes."""

from pathlib import Path

NAV = Path(__file__).resolve().parents[1] / "rosy_core" / "navigation"
FORBIDDEN = ("rosy_core.swarm", "navigation.swarm")


def test_navigation_tree_has_no_swarm_module():
    assert not (NAV / "swarm.py").exists()


def test_navigation_sources_do_not_import_swarm():
    for path in NAV.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{path.name} mentions {token}"
```

`manager.py` docstring의 `SWM-001`은 남아 있으면 이 테스트와 무관하다. `swarm` 부분 문자열이 `FORBIDDEN`에 있으므로 **주석의 `swarm follow`도 실패**한다. 그건 Task 4에서 고친다. 이 Task의 테스트가 주석 때문에 빨강이면, FORBIDDEN을 import 구문으로 좁힌다:

```python
import ast

def test_navigation_sources_do_not_import_swarm():
    for path in NAV.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert "swarm" not in name.split("."), path.name
```

import AST 가드를 써라. 문자열 `"swarm"` 주석은 Task 4 몫이다.

- [ ] **Step 2–4:** 실행. Task 2가 끝났으면 PASS. 실패면 남은 import를 고친다.

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/test/test_navigation_swarm_boundary.py
git commit -m "test(nav): forbid navigation from importing swarm"
```

---

### Task 4: 항법은 군집 이름을 쓰지 않는다

**Files:**
- Modify: `src/rosy_core/rosy_core/navigation/manager.py` (오류 문구 두 곳, `moving_goal` 기본 `source`)
- Modify: `src/rosy_core/test/test_swarm_integration.py` — `"swarm follow session"` 단언을 `"moving-goal session"`으로

- [ ] **Step 1: 실패하는 테스트**

`test_swarm_integration.py`의 두 assert를 바꾼다:

```python
assert "moving-goal session" in str(raised.value)
```

- [ ] **Step 2:** pytest 해당 테스트 FAIL (`swarm follow session`이 아직 본문)

- [ ] **Step 3:**

`manager.py`:
- `"a swarm follow session owns the goal — cancel it first"` → `"a moving-goal session owns the goal — cancel it first"` (두 곳)
- `def moving_goal(self, spec: NavGoalSpec, source: str = "swarm",` → `source: str = "moving"`
- docstring에서 “군집 추종은 정반대로”는 “moving-goal 호출자는 정반대로” 정도로만 고친다. SWM 요구사항 ID를 항법 파일에 새로 넣지 마라.

`SwarmManager`가 `moving_goal(..., source="swarm")`를 **명시적으로** 넘기는지 확인한다. 넘기지 않으면 기본값이 `"moving"`이 된다. 이벤트 `by` 필드가 `"swarm"`이어야 하는 시험이 있으면 manager 쪽에서 source를 넘겨라. 항법 기본값에 `"swarm"`을 다시 넣지 마라.

- [ ] **Step 4:**

```
python -m pytest src/rosy_core/test/test_swarm_integration.py src/rosy_core/test/test_swarm.py src/rosy_core/test/test_navigation_swarm_boundary.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/navigation/manager.py src/rosy_core/test/test_swarm_integration.py src/rosy_core/rosy_core/swarm/manager.py
git commit -m "refactor(nav): speak of moving-goal sessions, not swarm"
```

---

### Task 5: Fleet 기하 대조의 import와 주석

**Files:**
- Modify: `src/rosy_fleet/test/test_geometry.py`
- Modify: `src/rosy_fleet/rosy_fleet/formation/geometry.py` (모듈 docstring 경로)
- Modify: `src/rosy_fleet/rosy_fleet/formation/AGENTS.md`

- [ ] **Step 1:** `test_geometry.py`의

```python
from rosy_core.navigation.swarm import ReferencePose, follow_goal
```

를 `from rosy_core.swarm import ReferencePose, follow_goal`로 바꾼다. (이미 Task 2에서 고쳤으면 이 Task는 주석만.)

- [ ] **Step 2:** `python -m pytest src/rosy_fleet/test/test_geometry.py -q` — Task 2 미완료면 FAIL.

- [ ] **Step 3:** 주석 `rosy_core.navigation.swarm.follow_goal` → `rosy_core.swarm.follow_goal`. Fleet 패키지가 `SwarmManager`를 import하지 않는지 확인 (`test_boundaries.py`의 rclpy 가드와 별개). `from rosy_core.swarm`은 스키마가 아니라 follow_goal 대조라서 **시험 파일만** 허용한다. `formation/geometry.py`는 계속 CORE를 import하지 않는다.

- [ ] **Step 4:** `python -m pytest src/rosy_fleet/test/test_geometry.py src/rosy_fleet/test/test_boundaries.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/rosy_fleet/test/test_geometry.py src/rosy_fleet/rosy_fleet/formation
git commit -m "docs(fleet): point follow_goal contract at rosy_core.swarm"
```

---

### Task 6: AGENTS와 split 기준 표

**Files:**
- Create: `src/rosy_core/rosy_core/swarm/AGENTS.md`
- Modify: `src/rosy_core/rosy_core/navigation/AGENTS.md` — Purpose에서 SWM 삭제, Key Files에서 swarm.py 삭제
- Modify: `src/rosy_core/rosy_core/AGENTS.md` — Subdirectories에 `swarm/`
- Modify: `src/rosy_core/test/AGENTS.md` — test_swarm import 경로 한 줄, boundary 시험 행
- Modify: `docs/plans/2026-09-06-module-split-criteria.md` — navigation 행의 `nav, swarm`을 `nav`만. swarm 패키지 행 추가: field `swarm`

`swarm/AGENTS.md`:

```markdown
<!-- Parent: ../AGENTS.md -->
# swarm

## Purpose

SWM-001~007 robot-side follow. ROS-free. Aims via NavigationManager moving-goal
sessions. Does not own Nav2, sockets, or formation geometry.

## Key Files

| File | Description |
|---|---|
| `poses.py` | `ReferencePose`, `follow_goal` |
| `manager.py` | `SwarmManager` session, 2 Hz, HOLD |

## Testing Requirements

`test_swarm.py`, `test_swarm_api.py`, `test_swarm_stream.py`, `test_swarm_integration.py`, `test_navigation_swarm_boundary.py`
```

- [ ] **Step 1–4:** 문서만. pytest 없음. `navigation/AGENTS.md`가 다시 SWM을 주장하면 안 된다.

- [ ] **Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/swarm/AGENTS.md src/rosy_core/rosy_core/navigation/AGENTS.md src/rosy_core/rosy_core/AGENTS.md src/rosy_core/test/AGENTS.md docs/plans/2026-09-06-module-split-criteria.md
git commit -m "docs(swarm): claim SWM in swarm package, not navigation"
```

---

### Task 7: 회귀

**Files:** 없음 (명령만)

- [ ] **Step 1:**

```
python -m pytest src/rosy_core/test/test_swarm.py src/rosy_core/test/test_swarm_api.py src/rosy_core/test/test_swarm_stream.py src/rosy_core/test/test_swarm_integration.py src/rosy_core/test/test_navigation_swarm_boundary.py src/rosy_core/test/test_module_criteria.py src/rosy_fleet/test -q
```

Expected: PASS. `from rosy_core.navigation.swarm` grep이 소스에서 0건 (docs/plans 역사 문서는 제외).

```
# from Rosy OS, over src only
```

PowerShell:

```
python -c "from pathlib import Path; hits=[p for p in Path('src').rglob('*.py') if 'navigation.swarm' in p.read_text(encoding='utf-8')]; print(hits); assert hits==[]"
```

- [ ] **Step 2:** 설계 문서 상태를 “코드 이동 완료, 동작 불변”으로 한 줄 갱신. 실행 계획 체크박스 반영은 선택.

- [ ] **Step 3: Commit** (설계 상태 줄만 바뀌었으면)

```bash
git add docs/plans/2026-09-15-navigation-swarm-split-design.md
git commit -m "docs(swarm): mark D-60 split implemented in source"
```

변경이 없으면 커밋하지 마라.

---

## 완료 판정

- `rosy_core.swarm`이 SWM을 소유한다.
- `navigation/`에 `swarm.py`가 없고 swarm을 import하지 않는다.
- 기존 swarm 호스트 시험이 통과한다.
- Hub·FleetAgent·compose·mapping은 그대로다.
