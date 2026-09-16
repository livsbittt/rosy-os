# CORE rosy_control import 경계 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `rosy_core` 생산 코드에서 `rosy_control` import는 `bridge/control_sensor_adapter.py`만 허용한다. SafetyManager는 정책을 duck-type으로 받는다.

**Architecture:** D-63 목표의 2단계(D-64). 어댑터가 CommandPolicy를 만들고 `bind_control_policy`에 넘긴다. safety는 rosy_control 타입을 import하지 않는다.

**이 계획이 아닌 것:** CORE 이미지에서 rosy_control COPY 제거, 카메라 실기, 매핑 분리.

---

### Task 1: 가드 시험 — 어댑터만 rosy_control을 import한다

**Files:** Modify `test/test_runtime_slices.py`

기존 `test_core_package_does_not_import_optional_slice_code` 옆에:

```python
ALLOWED_ROSY_CONTROL = {"control_sensor_adapter.py"}


def test_only_control_sensor_adapter_imports_rosy_control():
    for path in CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
                names.update(f"{node.module}.{a.name}" for a in node.names)
        hits = [n for n in names if n == "rosy_control" or n.startswith("rosy_control.")]
        if hits and path.name not in ALLOWED_ROSY_CONTROL:
            raise AssertionError(f"{path.relative_to(CORE)} imports {hits}")
```

TDD: 지금 `safety/manager.py` 때문에 FAIL.

Commit after Task 2 green, or commit failing test first then fix.

Preferred: add test (FAIL), then Task 2 fix, one or two commits as the plan steps say.

---

### Task 2: SafetyManager에서 rosy_control import 제거

**Files:** `src/rosy_core/rosy_core/safety/manager.py`

`bind_control_policy` / `bind_simulation_actuation`에서 `from rosy_control...` 를 지운다. duck-type:

- policy: `callable(getattr(policy, "evaluate", None))` and `isinstance(policy.revision, str)` and non-empty
- actuation: `revision` 속성, `bind_simulation_actuation`의 기존 env 가드는 유지

`isinstance(policy, CommandPolicy)` 대신 위 검사. 오류 메시지는 기존 ValueError 의미를 유지.

기존 `test_control_policy_link.py`가 PASS해야 한다.

---

### Task 3: 회귀

```
python -m pytest test/test_runtime_slices.py src/rosy_core/test/test_control_policy_link.py src/rosy_core/test/test_control_sensor_adapter.py -q
```

`safety/manager.py`에 `rosy_control` 문자열이 import로 없어야 한다 (주석에 일반 명사로 남는 것은 AST 가드가 무시).
