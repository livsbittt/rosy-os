# Optional Runtime Slices Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** CORE는 항상 설치하고, motor/io/nav/vision/omx/ai는 카탈로그에서 골라 설치할 수 있게 한다. 동작은 지금 `core|motor|hardware` preset과 같게 두고, OMX/AI/비전 실기는 켜지 않는다.

**Architecture:** `board.yaml`에 `slices.required/available`와 `presets`를 둔다. `install-pi.sh`와 `runtime-mode.sh`는 preset을 슬라이스 집합으로 푼다. CORE 이미지는 omx/vision/ai 패키지를 빌드하지 않는다. 설계: `docs/plans/2026-09-16-optional-runtime-slices-design.md` (D-62).

**Tech Stack:** 기존 compose, board.yaml, install-pi.sh, host pytest. 새 런타임 데몬 없음.

**이 계획이 아닌 것:** CORE 프로세스 분해, 로봇 브로커, OMX/카메라 실기 기동, Device ARTIFACT GO, `rosy_core` Python을 메시지마다 쪼개기.

**Windows:** `python -m pytest test/test_robot_runtime.py` 등 ROS 없는 계약 시험.

---

### Task 1: 슬라이스 카탈로그를 board.yaml에 고정

**Files:**
- Modify: `deploy/robot/config/board.yaml`
- Create: `test/test_runtime_slices.py`

- [ ] **Step 1: 실패하는 테스트**

`test/test_runtime_slices.py`:

```python
"""D-62: CORE is required; other slices are opt-in presets."""

from robot_contracts import DEPLOY
import yaml

def board():
    return yaml.safe_load((DEPLOY / "config" / "board.yaml").read_text(encoding="utf-8"))


def test_core_is_the_only_required_slice():
    data = board()
    assert data["slices"]["required"] == ["core"]
    available = set(data["slices"]["available"])
    assert available >= {"motor", "io", "nav", "vision", "omx", "ai"}
    assert "core" not in available


def test_presets_match_current_runtime_modes():
    presets = board()["presets"]
    assert presets["core"] == ["core"]
    assert presets["motor"] == ["core", "motor"]
    assert presets["hardware"] == ["core", "motor", "io", "nav"]
    for extra in ("vision", "omx", "ai"):
        assert extra not in presets["core"]
        assert extra not in presets["motor"]
        assert extra not in presets["hardware"]
```

- [ ] **Step 2:** `python -m pytest test/test_runtime_slices.py -v` FAIL (`slices` 없음)

- [ ] **Step 3:** `board.yaml`에 설계 §4의 `slices` / `presets`를 추가한다. 기존 `modes:` 는 유지하되, 각 mode가 같은 preset을 가리키게 한 줄을 덧붙인다. `pi5-lite` alias는 그대로 hardware.

예:

```yaml
slices:
  required: [core]
  available: [motor, io, nav, vision, omx, ai]
presets:
  core: [core]
  motor: [core, motor]
  hardware: [core, motor, io, nav]
```

- [ ] **Step 4:** 테스트 PASS. `test_robot_runtime.py`도 통과하는지 확인.

- [ ] **Step 5:** Commit `feat(deploy): catalog optional runtime slices on the board`

---

### Task 2: capability는 꺼진 슬라이스를 광고하지 않는다

**Files:**
- Modify: `deploy/robot/config/capabilities.core.yaml` (키가 없으면 추가하되 값은 false)
- Modify: `test/test_runtime_slices.py`

- [ ] **Step 1:** 테스트 추가

```python
from robot_contracts import board_caps

def test_core_capabilities_do_not_advertise_optional_slices():
    caps = board_caps("core")
    assert caps["navigation"]["goal_navigation"] is False
    assert caps["swarm"]["follow"] is False
    vision = caps.get("vision") or {}
    omx = caps.get("omx") or {}
    ai = caps.get("ai") or {}
    assert vision.get("enabled", False) is False
    assert omx.get("enabled", False) is False
    assert ai.get("enabled", False) is False
```

capability 스키마에 `vision`/`omx`/`ai` 객체가 아직 없으면, 테스트는 `get(..., False)`로 통과할 수 있다. 없으면 명시적으로 넣는 편이 카탈로그와 맞다:

```yaml
vision:
  enabled: false
omx:
  enabled: false
ai:
  enabled: false
```

hardware overlay에도 `enabled: false`로 둔다. 켜는 것은 이후 슬라이스 overlay.

- [ ] **Step 2–4:** FAIL 후 YAML, PASS

- [ ] **Step 5:** Commit `feat(deploy): keep vision omx ai dark on core capabilities`

---

### Task 3: CORE 소스는 omx/vision 패키지를 import하지 않는다

**Files:**
- Create 또는 확장: `test/test_runtime_slices.py`

```python
import ast
from pathlib import Path
from robot_contracts import ROOT

CORE = ROOT / "src" / "rosy_core" / "rosy_core"
FORBIDDEN = ("rosy_omx_adapter", "rosy_control.camera", "moveit")


def test_core_package_does_not_import_optional_slice_code():
    for path in CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        for name in names:
            for banned in FORBIDDEN:
                assert name != banned and not name.startswith(banned + "."), f"{path.name} imports {name}"
```

`rosy_control` 흡수 어댑터가 이미 CORE에 있으면, `rosy_control.camera`만 금하고 센서 adapter 경로는 허용한다. 카메라 노드를 CORE가 import하면 FAIL — 그게 이 가드의 목적이다.

- [ ] Run: `python -m pytest test/test_runtime_slices.py -v`

- [ ] Commit `test(core): forbid optional slice packages inside rosy_core`

---

### Task 4: install-pi.sh가 preset/slices를 받는다

**Files:**
- Modify: `deploy/robot/install-pi.sh`
- Modify: `test/` 기존 installer 계약 (`test_dds_identity_contracts.py` 또는 `test_pi_wifi_deployment.py` 패턴 — 스크립트를 bash로 구동하는 기존 방식)

설치 스크립트에:

```bash
# --preset core|motor|hardware  (default hardware for Pi first-boot today)
# --slices core,motor  (optional override; must include core)
```

`resolve-mode.sh`가 preset → 기존 `ROSY_RUNTIME_MODE`로 매핑하면 compose는 당장 안 바뀐다.

- [ ] 테스트: `--preset core` 이면 runtime mode `core`. `--slices motor`만 주면 실패(core 없음). `--slices core,omx`는 아직 이미지가 없으므로 **설치를 거절**하거나 mode는 core로 두고 omx는 “not installed”로 기록. 거절이 더 안전하다 — 없는 슬라이스를 조용히 무시하지 마라.

권장: available에 있고 preset에 없는 슬라이스(vision/omx/ai)를 CLI로 고르면 exit ≠ 0, 메시지 `slice not installable yet`.

- [ ] Commit `feat(deploy): resolve install presets to existing runtime modes`

---

### Task 5: Dockerfile 주석과 CORE 타깃 경계

**Files:**
- Modify: `deploy/robot/Dockerfile` (주석만 또는 COPY 목록 핀)
- Modify: `test/test_release_layout.py` 또는 `test_image_pipeline.py`가 Dockerfile COPY를 보면 거기에 핀.

CORE 빌드가 `rosy_omx_adapter`를 COPY하지 않는지 문자열 가드:

```python
def test_core_dockerfile_does_not_copy_omx_or_imu():
    text = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    core = text.split("FROM runtime-common AS io-runtime")[0]
    assert "rosy_omx_adapter" not in core
    assert "rosy_imu_bno055" not in core
```

`rosy_control`은 지금 COPY된다. 이 Task에서 빼지 마라 (흡수 부채, 별도 슬라이스).

- [ ] Commit `test(deploy): keep omx and imu out of the core image stage`

---

### Task 6: 문서

**Files:**
- Modify: `deploy/robot/AGENTS.md`, `deploy/robot/config/AGENTS.md`
- Modify: `docs/plans/2026-09-16-optional-runtime-slices-design.md` 상태 한 줄

슬라이스 표와 “CORE 필수, 나머지 선택. vision/omx/ai는 카탈로그만”을 적는다.

- [ ] Commit `docs(deploy): describe optional runtime slices`

---

### Task 7: 회귀

```
python -m pytest test/test_runtime_slices.py test/test_robot_runtime.py test/test_release_boundary_guards.py -q
```

compose 서비스 집합 `{rosy-core, rosy-motor, rosy-io}` 유지.

---

## 후속 (이 슬라이스 밖)

1. vision/omx compose overlay — D-52, D-55 실측 후
2. CORE 이미지에서 OpenCV/`rosy_control` 축출
3. 슬라이스별 ARM64 digest (Device ARTIFACT)
4. 관제 PC fleet-relay 슬라이스 (D-59 listen)
