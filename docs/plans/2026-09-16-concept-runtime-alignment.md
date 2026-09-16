# Concept Runtime Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Map concept Node/Device/Component/Capability/Asset/Task onto the live CORE + D-62 stack: one identity plane, adapter manifests, inventory API, and a Control `cmd_vel` coexistence guard — without apt/`rosyctl`, Fleet server, or composite OMX.

**Architecture:** Keep D-1 (one CORE process) and D-38 (CORE owns `cmd_vel`). Add ROS-free `rosy_core.domain` types and YAML manifests beside existing adapters. Bind API `robot_id` to `ROSY_NAMESPACE`. D-62 slices remain the install model; this plan does not reimplement them.

**Tech Stack:** Python 3.12, PyYAML, FastAPI, existing host pytest. No rclpy in new tests.

**Design:** [2026-09-16-concept-runtime-alignment-design.md](2026-09-16-concept-runtime-alignment-design.md)

**Not this plan:** `rosyctl`, Debian `rosy-profile-*`, concept 05 ROS external API, compute/AI, MobileManipulator, Device ARTIFACT GO.

**Windows:** `python -m pytest` paths below from `Rosy OS/`.

**Prerequisite:** If `deploy/robot/config/board.yaml` has no `slices:` key, execute [2026-09-16-optional-runtime-slices.md](2026-09-16-optional-runtime-slices.md) Task 1 first (catalog only). Do not block identity/domain work on later D-62 image-split tasks.

---

### Task 1: Freeze terms (D-65 + glossary + concept map)

**Files:**
- Modify: `docs/reference/ROSY ADR Log.md`
- Modify: `CONCEPTS.md`
- Modify: `docs/concept/README.md`
- Modify: `docs/plans/AGENTS.md`
- Test: `test/test_harness_contracts.py` (only if it indexes ADR headings — otherwise skip extra test)

**Step 1: Write the ADR**

Append to the ADR table and a new `## D-65` section (D-61–D-64 already occupy earlier IDs):

- Status: Proposed
- Decision: v1 maps concept objects onto CORE + D-62 slices. Concept 15 apt/`rosyctl` and the control plane are later concept-13 phases. Concept 05 ROS topics are not the external API (CORE SRS §1.3).
- Alternatives: full apt rewrite; vocabulary-only patch.
- References: this design + concept 13.

**Step 2: Glossary**

Add to `CONCEPTS.md` after Robot commissioning (keep existing Runtime mode / Recovery hold):

- **Node** — the computer running CORE; not an rclpy node. Code: `RuntimeNode`.
- **Device** — the physical robot CORE manages (`device_id` = robot id). Avoid: treating Nav2 as a Device.
- **Component** — a functional part (drive, lidar, …) listed from profile/capabilities.
- **Capability** — advertised boolean/descriptor; not a scheduler. Avoid: `rosy-profile-*` as a capability.
- **Asset** — v1 is the single Device. Composite Pinky+OMX is not an Asset yet.
- **Task** — atomic REST action (`TaskKind`). Avoid: workflow/mission (Fleet, D-12).

Flag: “profile” still means Compose grouping or hardware YAML; runtime mode is the staged install preset.

**Step 3: Concept README**

Add a **Current mapping (2026-09-16)** table pointing at CORE SRS / D-62 / this design. Label docs 10–12, 09 composite, 15 apt as target-not-built.

**Step 4: Index**

Add both 2026-09-16 concept-runtime-alignment files to `docs/plans/AGENTS.md`.

**Step 5: Commit**

```bash
git add docs/reference/"ROSY ADR Log.md" CONCEPTS.md docs/concept/README.md docs/plans/AGENTS.md
git commit -m "docs: freeze concept terms onto CORE and D-62 (D-65)"
```

---

### Task 2: Persist robot number in the installer

**Files:**
- Modify: `deploy/robot/install-pi.sh` (`require_robot_identity`)
- Modify: `test/test_dds_identity_contracts.py`
- Modify: `test/test_device_readback.py` if it assumes the number is absent from `.env`

**Step 1: Failing test**

In `test/test_dds_identity_contracts.py`, add:

```python
def test_installer_persists_the_robot_number_without_renumbering():
    text = _text(INSTALLER)
    body = text[
        text.index("require_robot_identity() {"): text.index("write_runtime_environment() {")
    ]
    assert "ROSY_ROBOT_NUMBER" in body
    assert 'set_env_default "$env_file" ROSY_ROBOT_NUMBER' in body
    assert 'set_env_value "$env_file" ROSY_ROBOT_NUMBER' not in text
    assert "already has ROSY_ROBOT_NUMBER" in body or "already has $key=" in body
```

Keep the existing loop that forbids `set_env_value` on `ROS_DOMAIN_ID` / `ROSY_NAMESPACE`. Do **not** add `ROSY_ROBOT_NUMBER` to `IDENTITY_KEYS` if that loop would then forbid `set_env_default` incorrectly — only `set_env_value` is forbidden.

**Step 2:** `python -m pytest test/test_dds_identity_contracts.py::test_installer_persists_the_robot_number_without_renumbering -v`

Expected: FAIL (number not written).

**Step 3: Implementation**

Inside `require_robot_identity`, after deriving domain/namespace and before the write loop:

- Include `ROSY_ROBOT_NUMBER` in `derived` (the original decimal string, not zero-padded).
- Clash check for all three keys.
- `set_env_default "$env_file" ROSY_ROBOT_NUMBER "$number"` alongside domain/namespace.

**Step 4:** Re-run the identity contract file. Also `python -m pytest test/test_device_readback.py test/test_dds_identity_contracts.py -q`.

Expected: PASS. Readback should now be able to see the number when `.env` is produced by the installer function.

**Step 5: Commit**

```bash
git add deploy/robot/install-pi.sh test/test_dds_identity_contracts.py
git commit -m "fix(deploy): persist ROSY_ROBOT_NUMBER at commission"
```

---

### Task 3: Bind CORE robot_id to namespace

**Files:**
- Modify: `src/rosy_core/rosy_core/config.py`
- Modify: `src/rosy_core/rosy_core/identity.py`
- Modify: `src/rosy_core/test/test_runtime_config.py`
- Modify: `src/rosy_core/rosy_core/api/v1/system.py`
- Modify: `src/rosy_core/test/test_api.py` (`test_admin_can_update_robot_identity`)

**Step 1: Failing tests**

`src/rosy_core/test/test_runtime_config.py`:

```python
def test_namespace_env_sets_robot_id(tmp_path, monkeypatch):
    config_path = tmp_path / "rosy.yaml"
    config_path.write_text("robot:\n  id: rosy_01\n  name: Keep Me\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("ROSY_CONFIG", raising=False)
    monkeypatch.delenv("ROSY_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("ROSY_NAMESPACE", "rosy_03")
    monkeypatch.setenv("ROSY_ROBOT_NUMBER", "3")

    config = config_module.load_config(str(config_path))

    assert config["robot"]["id"] == "rosy_03"
    assert config["robot"]["name"] == "Keep Me"
    assert config["robot"]["number"] == 3


def test_robot_number_must_match_namespace(tmp_path, monkeypatch):
    config_path = tmp_path / "rosy.yaml"
    config_path.write_text("robot:\n  id: rosy_01\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("ROSY_CONFIG", raising=False)
    monkeypatch.setenv("ROSY_NAMESPACE", "rosy_03")
    monkeypatch.setenv("ROSY_ROBOT_NUMBER", "4")
    try:
        config_module.load_config(str(config_path))
    except ValueError as exc:
        assert "ROSY_ROBOT_NUMBER" in str(exc)
    else:
        raise AssertionError("mismatched number and namespace must not boot")
```

`src/rosy_core/test/test_api.py` — replace id rewrite success with:

```python
def test_admin_can_rename_robot_but_not_rebind_id(client, tmp_path, monkeypatch):
    # existing overlay fixture...
    renamed = tc.put("/api/v1/system/info", json={"robot_name": "Bay 7"}, headers=ADMIN)
    assert renamed.status_code == 200
    assert renamed.json()["robot_name"] == "Bay 7"
    locked = tc.put("/api/v1/system/info", json={"robot_id": "rosy_07"}, headers=ADMIN)
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "IDENTITY_LOCKED"
```

Keep the 400 for `NOPE` and 403 for operator.

**Step 2:** Run those tests. Expected: FAIL.

**Step 3: Implementation**

`load_config()` after namespace/frame_prefix:

```python
robot = config.setdefault("robot", {})
if namespace:
    robot["id"] = namespace
number_env = os.environ.get("ROSY_ROBOT_NUMBER", "").strip()
if number_env:
    if not re.fullmatch(r"0|[1-9][0-9]*", number_env):
        raise ValueError(f"ROSY_ROBOT_NUMBER must be a decimal integer with no leading zero, got {number_env!r}")
    number = int(number_env)
    expected = f"rosy_{number:02d}"
    if namespace and namespace != expected:
        raise ValueError(
            f"ROSY_ROBOT_NUMBER={number} derives {expected}, not ROSY_NAMESPACE={namespace}"
        )
    robot["number"] = number
    if not namespace:
        robot["id"] = expected
```

`RobotIdentity.from_config`: read `robot.number`; default id remains only when neither env nor yaml id exists (host tests). `info()` includes `robot_number`.

`update_system_info`: if `body.robot_id` is not None and not equal to `svc.identity.robot_id`, raise `ApiError("IDENTITY_LOCKED", 409, "robot_id is derived from the robot number")`. Name updates unchanged.

**Step 4:** `python -m pytest src/rosy_core/test/test_runtime_config.py src/rosy_core/test/test_api.py -q`

Expected: PASS. Fix any snapshot tests that assumed PUT changes id.

**Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/config.py src/rosy_core/rosy_core/identity.py src/rosy_core/rosy_core/api/v1/system.py src/rosy_core/test
git commit -m "fix(core): bind robot_id to namespace and lock PUT rebind"
```

---

### Task 4: Domain inventory types

**Files:**
- Create: `src/rosy_core/rosy_core/domain/__init__.py`
- Create: `src/rosy_core/rosy_core/domain/model.py`
- Create: `src/rosy_core/test/test_domain_model.py`
- Modify: `src/rosy_core/rosy_core/services.py`
- Modify: `src/rosy_core/rosy_core/api/v1/system.py`
- Modify: `src/rosy_core/test/test_api.py`

**Step 1: Failing test** (`src/rosy_core/test/test_domain_model.py`)

```python
from rosy_core.domain.model import Asset, Component, Device, DeviceState, RuntimeNode, inventory_from_config
from rosy_core.command.arbitration import Mode


def test_inventory_is_a_single_mobile_base_asset():
    data = inventory_from_config(
        {
            "robot": {"id": "rosy_03", "name": "Bay 3", "number": 3},
            "runtime": {"mode": "hardware"},
        },
        profile_model="Pinky Pro",
        sensors=["lidar", "encoder"],
        slices=["core", "motor", "io", "nav"],
        mode=Mode.IDLE,
        health_error=False,
        estop=False,
    )
    assert isinstance(data["node"], RuntimeNode)
    assert data["node"].runtime_mode == "hardware"
    assert data["node"].slices == ("core", "motor", "io", "nav")
    device = data["device"]
    assert isinstance(device, Device)
    assert device.device_id == "rosy_03"
    assert device.device_type == "mobile_base"
    assert {c.name for c in data["components"]} >= {"drive", "lidar", "encoder"}
    asset = data["asset"]
    assert isinstance(asset, Asset)
    assert asset.asset_id == "rosy_03"
    assert asset.type == "mobile_base"
    assert asset.devices == ("rosy_03",)
    assert "omx" not in asset.devices
    assert data["device_state"] is DeviceState.READY


def test_estop_maps_to_safe_stop():
    data = inventory_from_config(
        {"robot": {"id": "rosy_01"}, "runtime": {"mode": "core"}},
        profile_model="Pinky Pro",
        sensors=[],
        slices=["core"],
        mode=Mode.EMERGENCY,
        health_error=False,
        estop=True,
    )
    assert data["device_state"] is DeviceState.SAFE_STOP
```

**Step 2:** `python -m pytest src/rosy_core/test/test_domain_model.py -v` FAIL (module missing).

**Step 3: Implementation**

`model.py`: dataclasses + `DeviceState` enum (`BOOTING READY BUSY DEGRADED FAULT SAFE_STOP OFFLINE UPDATING` — implement the rows in the design §9; unused values may exist but must not be assigned incorrectly). `inventory_from_config` is pure.

Wire `CoreServices.inventory()` using config, profile model, capability sensors, runtime mode, mode machine, safety.estop, diagnostics. No ROS.

`GET /api/v1/system/inventory` returns JSON via `dataclasses.asdict` (convert enums to `.value`). Viewer auth.

API test: authenticated GET returns `device.device_type == "mobile_base"` and no `pick`/`rfid` keys.

**Step 4:** `python -m pytest src/rosy_core/test/test_domain_model.py src/rosy_core/test/test_api.py -q` PASS.

**Step 5: Commit**

```bash
git add src/rosy_core/rosy_core/domain src/rosy_core/rosy_core/services.py src/rosy_core/rosy_core/api/v1/system.py src/rosy_core/test/test_domain_model.py src/rosy_core/test/test_api.py
git commit -m "feat(core): expose concept inventory as a derived snapshot"
```

---

### Task 5: Capability descriptors (additive)

**Files:**
- Create: `src/rosy_core/rosy_core/domain/capabilities.py`
- Create: `src/rosy_core/test/test_capability_descriptors.py`
- Modify: `src/rosy_core/rosy_core/capability.py` only if a tiny helper is needed
- Modify: inventory JSON to include `capability_ids`

**Step 1: Failing test**

```python
from rosy_core.domain.capabilities import descriptors_from_cap001

def test_pinky_hardware_flags_map_to_mobility_ids():
    ids = {d.id for d in descriptors_from_cap001({
        "navigation": {"goal_navigation": True, "return_home": True},
        "teleop": True,
        "slam": False,
        "swarm": {"follow": False, "lead": False},
        "docking": {"supported": False},
    })}
    assert "mobility.navigate" in ids
    assert "mobility.move" in ids
    assert "mobility.dock" not in ids
    assert "manipulate.pick" not in ids
    assert "scan_rfid" not in ids
    assert "infer" not in ids


def test_core_slice_has_no_motion_descriptors():
    ids = {d.id for d in descriptors_from_cap001({
        "navigation": {"goal_navigation": False, "return_home": False},
        "teleop": False,
        "slam": False,
        "swarm": {"follow": False, "lead": False},
        "docking": {"supported": False},
    })}
    assert ids == set()
```

**Step 2:** FAIL.

**Step 3:** Implement mapping table from design §7. Attach the list to inventory only. **Do not** change `GET /api/v1/system/capabilities` body.

**Step 4:** `python -m pytest src/rosy_core/test/test_capability_descriptors.py src/rosy_core/test/test_api.py src/rosy_core/test/test_protocol_schemas.py -q` PASS.

**Step 5: Commit** `feat(core): map CAP-001 flags to concept capability ids`

---

### Task 6: Adapter manifests + YAML-only registry

**Files:**
- Create: `src/rosy_bringup/config/adapter.manifest.yaml`
- Create: `src/rosy_omx_adapter/config/adapter.manifest.yaml`
- Create: `src/rosy_core/rosy_core/domain/adapters.py`
- Create: `src/rosy_core/test/test_adapter_registry.py`
- Create: `src/rosy_bringup/test/test_adapter_manifest.py`
- Create: `src/rosy_omx_adapter/test/test_adapter_manifest.py`
- Modify: `src/rosy_bringup/setup.py` / `src/rosy_omx_adapter/setup.py` to install the yaml if other config is already installed the same way
- Modify: `test/test_runtime_slices.py` or `test/test_site_fabric_roles.py` only if an import-guard file already lists CORE imports

**Step 1: Failing tests**

Pinky:

```python
import yaml
from pathlib import Path

def test_pinky_manifest_declares_mobile_base():
    data = yaml.safe_load((Path(__file__).parents[1] / "config" / "adapter.manifest.yaml").read_text(encoding="utf-8"))
    assert data["id"] == "rosy.device.pinky"
    assert data["device_type"] == "mobile_base"
    assert "drive" in data["provides"]
    assert "cmd_vel" not in data.get("provides", [])
```

OMX:

```python
def test_disabled_omx_manifest_provides_nothing():
    data = yaml.safe_load(Path(__file__).parents[1].joinpath("config/adapter.manifest.yaml").read_text(encoding="utf-8"))
    assert data["id"] == "rosy.device.omx"
    assert data["enabled"] is False
    assert data["provides"] == []
```

Registry (CORE, YAML paths injected — no package import of OMX Python):

```python
from rosy_core.domain.adapters import AdapterRegistry

def test_registry_skips_disabled_omx(tmp_path):
    pinky = tmp_path / "pinky.yaml"
    omx = tmp_path / "omx.yaml"
    pinky.write_text("id: rosy.device.pinky\nversion: 0.1.0\ndevice_type: mobile_base\nenabled: true\nprovides: [drive]\n", encoding="utf-8")
    omx.write_text("id: rosy.device.omx\nversion: 0.1.0\ndevice_type: manipulator\nenabled: false\nprovides: []\n", encoding="utf-8")
    loaded = AdapterRegistry.from_paths([pinky, omx]).enabled()
    assert [item.id for item in loaded] == ["rosy.device.pinky"]
```

**Step 2:** FAIL.

**Step 3:** Write manifests. Registry parses YAML into a frozen dataclass. Reject unknown keys? No — ignore extras. Reject missing `id`. CORE inventory lists `adapters: [rosy.device.pinky]` when only Pinky is enabled.

Confirm `rosy_core` source still has no `import rosy_omx_adapter`.

**Step 4:** `python -m pytest src/rosy_core/test/test_adapter_registry.py src/rosy_bringup/test/test_adapter_manifest.py src/rosy_omx_adapter/test/test_adapter_manifest.py -q` PASS.

**Step 5: Commit** `feat: add static Pinky and OMX adapter manifests`

---

### Task 7: TaskKind capability gate

**Files:**
- Create: `src/rosy_core/rosy_core/domain/tasks.py`
- Create: `src/rosy_core/test/test_task_kinds.py`
- Modify: `src/rosy_core/rosy_core/api/v1/control.py`
- Modify: `src/rosy_core/rosy_core/api/v1/navigation.py`
- Modify: `src/rosy_core/rosy_core/api/v1/docking.py` (if it already calls `capability.supports`)

**Step 1: Failing test**

```python
from rosy_core.capability import Capability, CapabilityError
from rosy_core.domain.tasks import TaskKind

def test_navigate_requires_goal_navigation():
    cap = Capability({"navigation": {"goal_navigation": False}, "teleop": True, "docking": {"supported": False}})
    try:
        TaskKind.NAVIGATE.require(cap)
    except CapabilityError as exc:
        assert exc.feature == "navigation.goal_navigation"
    else:
        raise AssertionError("NAVIGATE must fail closed")

def test_move_requires_teleop():
    cap = Capability({"teleop": True, "navigation": {"goal_navigation": False}})
    TaskKind.MOVE.require(cap)
```

**Step 2:** FAIL.

**Step 3:** Enum + `require()`. Routes that already call `capability.require(...)` should call `TaskKind.*.require(svc.capability)` instead so the dotted path lives in one table. Do not add a workflow store.

**Step 4:** `python -m pytest src/rosy_core/test/test_task_kinds.py src/rosy_core/test/test_api.py -q` PASS.

**Step 5: Commit** `feat(core): bind atomic actions to TaskKind capability ids`

---

### Task 8: Control launch must not sit beside CORE

**Files:**
- Modify: `test/test_control_absorption_package.py` (or create `test/test_control_launch_boundary.py`)
- Modify: `src/rosy_control/launch/robot.launch.py` only if the test requires an explicit comment/allow-list marker — prefer asserting compose/launch **non-inclusion** first
- Modify: `deploy/robot/compose.yaml` only if a stray include exists (it should not)

**Step 1: Failing test**

```python
from pathlib import Path
from robot_contracts import DEPLOY, ROOT

def test_operational_compose_does_not_launch_legacy_control_stack():
    text = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
    assert "robot.launch.py" not in text
    assert "rosy_control/launch" not in text


def test_hardware_launch_does_not_start_safety_as_final_publisher():
    nav = ROOT / "src" / "rosy_navigation" / "launch" / "hardware.launch.py"
    text = nav.read_text(encoding="utf-8")
    assert "robot.launch.py" not in text
    assert "safety_node" not in text
```

Optional source marker on `robot.launch.py`: first docstring line contains `LEGACY_FULL_STACK` so grep stays stable.

**Step 2:** Run. If compose already complies, the test PASSES immediately — keep it as a regression lock (do not skip). If `hardware.launch.py` mentions `safety_node` for a different reason, tighten the assertion to `rosy_control` package launch includes only.

**Step 3:** Only change launch files if a test fails. Do not flip Control `cmd_out` default (legacy unit tests).

**Step 4:** `python -m pytest test/test_control_absorption_package.py test/test_control_launch_boundary.py -q` PASS.

**Step 5: Commit** `test: lock CORE compose against legacy Control cmd_vel launch`

---

### Task 9: Wire inventory into CoreServices and host regression

**Files:**
- Modify: `src/rosy_core/rosy_core/services.py` `CoreServices.build` to construct registry from optional config paths (default: empty list on host; device overlay later)
- Modify: `src/rosy_core/config/rosy_default.yaml` with

```yaml
adapters:
  manifests: []
```

Device overlay can list `/etc/rosy/adapters/*.yaml` in a later deploy task — **not required** to ship files into the image this pass.

- Run full host subset:

```powershell
python -m pytest src/rosy_core/test src/rosy_bringup/test/test_adapter_manifest.py src/rosy_omx_adapter/test/test_adapter_manifest.py src/rosy_omx_adapter/test/test_omx_profile.py test/test_dds_identity_contracts.py test/test_control_absorption_package.py -q
```

Expected: PASS. Record skip counts; do not treat skips as GO.

**Commit** if wiring diffs remain: `feat(core): default empty adapter manifest list on host`

---

### Task 10: Docs close-out

**Files:**
- Modify: `src/rosy_core/AGENTS.md` (inventory endpoint, identity lock)
- Modify: `src/rosy_core/rosy_core/AGENTS.md` if it lists modules
- Modify: `docs/concept/13_ROSY_Current_to_Target_Migration.md` — mark Phase 0 done-in-glossary, Phase 1 identity+inventory done, Phase 2 manifests-not-move, Phases 3–5 still later
- Append `src/rosy_core/logs.md` / `docs/logs.md` per harness if you touch those modules
- `python tools/harness/rosy_harness.py generate` from `Rosy OS` if D-61 is in use

**Commit** `docs: record concept alignment Phase 0-2 on CORE`

---

## Verification (orchestrator)

Before claiming the plan executed:

1. ADR D-65 exists; CONCEPTS.md has the six objects; concept README has the mapping table. D-63 remains the modular-middleware goal.
2. Identity tests in `test/test_dds_identity_contracts.py` and `src/rosy_core/test/test_runtime_config.py` pass.
3. `PUT /api/v1/system/info` cannot rebind `robot_id` (`test_api.py`).
4. `GET /api/v1/system/inventory` exists; capabilities GET is unchanged.
5. Adapter manifests parse; OMX disabled provides `[]`.
6. Compose/hardware launch still omit `robot.launch.py`.
7. No new `rosyctl`, no apt packaging, no `manipulate.pick` advertisement.

## Risks during execution

- `test_api.py` has many identity assumptions — run the whole file after Task 3, not one test.
- Do not persist `ROSY_ROBOT_NUMBER` with `set_env_value` (renumber footgun; existing contract).
- Do not import `rosy_omx_adapter` from `rosy_core`.
- Do not start D-62 image splits or vision/omx compose services as part of this plan.
