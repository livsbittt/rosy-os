# Concept Runtime Alignment Design

작성일: 2026-09-16
상태: pending approval (설계). 코드·ADR 본문 반영은 실행 계획.

관련: D-1, D-2, D-11, D-12, D-17, D-22, D-33, D-38, D-57, D-62 ·
[concept 00–04, 06–08, 13, 15](../concept/README.md) ·
[CONCEPTS.md](../../CONCEPTS.md) ·
[선택 슬라이스](2026-09-16-optional-runtime-slices-design.md) ·
[Device 검증](2026-09-13-rosy-os-device-validation-implementation-plan.md)

## 1. Goal

Map the six concept domain objects and the adapter/capability/install ideas onto the **live Pinky CORE + Docker stack**, without rewriting ROSY as Debian `rosy-profile-*` packages or a control plane.

After this work, an engineer can point at running code and say: this host is a Node, this robot is a Device, these sensors are Components, these YAML flags are Capabilities, this unit is a single-device Asset, these REST actions are Tasks. Install modularity is D-62 slices. Identity is one plane.

## 2. Non-goals

Do **not** build in this pass:

- `rosyctl`, apt meta-packages, `/etc/rosy/node.yaml`, Ubuntu 24.04 as the install host
- Fleet server, task orchestrator, compute scheduler, model/policy manager
- Compute fabric, VLA, dataset pipeline (concept 10–12)
- Composite `Pinky + OMX = MobileManipulator` runtime (concept 09 / Phase 5)
- Concept 05 ROS topics (`/rosy/{device_id}/state`) as the external API
- Dynamic plugin discovery / entry-point loading
- Splitting `rosy_core` into `rosy-runtime-base` processes (D-1)

Device ARTIFACT/Pi GO is still the validation plan’s job. This design does not promote those gates.

## 3. Two documents, one mapping

| Source | Role after this design |
|---|---|
| `docs/spec/ROSY CORE SRS.md`, API ref, ADR log | Contract. Wins on API, modes, cmd_vel, identity. |
| `CONCEPTS.md` | Live glossary. Gains Node/Device/Component/Capability/Asset/Task mapped to code. |
| `docs/concept/` | Target OS. README gains an explicit **current mapping** table. Concept 15 apt path is deferred, not deleted. |
| D-62 slices | v1 realization of “install only what the node needs.” |

Proposed ADR **D-65**: concept OS is the target; v1 maps terms onto CORE + D-62; Debian profiles and the control plane stay later phases of concept 13. D-63 remains the modular-middleware goal; this freeze does not reuse that ID.

## 4. Install model

Concept 15’s *intent* (minimal node footprint, combinable roles) is already decided as D-62:

| Concept name | v1 name | Mechanism |
|---|---|---|
| `rosy-profile-pinky` | preset `hardware` | slices `{core, motor, io, nav}` |
| `rosy-runtime-base` | slice `core` | `rosy-core` image + `rosy_core` process |
| `rosy-adapter-pinky` | slice `motor` + `io` | `rosy_bringup` / LiDAR, not a new apt package |
| `rosy-adapter-omx` | slice `omx` | catalog only, default off, disabled YAML |
| `rosy-profile-gpu` / edge / rfid / control | — | not in v1 catalog |

Runtime mode `core|motor|hardware` remains the operator-facing preset name (`CONCEPTS.md`). Compose `profiles:` stay a Docker grouping word. Do not rename Compose keys in this pass (breakage with no gain). Product docs and CORE comments must say **runtime mode** or **slice**, not “profile”, for those presets.

**Prerequisite:** finish [optional-runtime-slices.md](2026-09-16-optional-runtime-slices.md) far enough that `board.yaml` has `slices` / `presets`. This design does not duplicate those tasks.

## 5. Identity — one plane

Today:

- Install derives `ROS_DOMAIN_ID` / `ROSY_NAMESPACE` from `ROSY_ROBOT_NUMBER` and does **not** persist the number (`install-pi.sh` `require_robot_identity`).
- CORE `RobotIdentity.from_config` defaults `robot_id` to `rosy_01`.
- `PUT /api/v1/system/info` can rewrite `robot.id` in the YAML overlay.

After:

1. Installer writes `ROSY_ROBOT_NUMBER` with `set_env_default` (first commission) and refuses mismatch the same way it refuses a domain/namespace clash. Template `.env.example` still has no identity values.
2. `load_config()`: if `ROSY_NAMESPACE` is set, `robot.id` becomes that namespace (no leading slash). If `ROSY_ROBOT_NUMBER` is also set, `rosy_%02d` must match the namespace or config load fails.
3. `RobotIdentity.info()` adds `robot_number`, `ros_domain_id`, `ros_namespace`, `runtime_mode` (mode already present).
4. `PUT /api/v1/system/info` may change `robot_name` only. Sending `robot_id` that is not the derived namespace is `409 IDENTITY_LOCKED`. Host tests without env keep using YAML `robot.id` so pytest does not need a number.

This is D-33 applied to the API plane. Display name stays human-editable.

## 6. Domain objects (data, not a new runtime)

ROS-free types in `src/rosy_core/rosy_core/domain/`. CORE process unchanged (D-1).

| Concept | v1 type | How it is filled |
|---|---|---|
| Node | `RuntimeNode` | hostname, arch, os, `software_version`, `runtime_mode`, active slices |
| Device | `Device` | `device_id` = `robot_id`, `device_type` = `mobile_base`, model from `RobotProfile` |
| Component | `Component` | drivetrain + sensors listed in the mounted profile/capabilities |
| Capability | existing `Capability` + `CapabilityDescriptor` | see §7 |
| Asset | `Asset` | one Device, `type=mobile_base`, `asset_id=robot_id`. No OMX composition. |
| Task | `TaskKind` enum | §9. No workflow engine (D-12: mission is Fleet). |

Inventory is additive: `GET /api/v1/system/inventory`. Existing `/state`, `/capabilities`, `/info` keep their schemas except the identity fields in §5.

## 7. Capabilities

Keep **CAP-001** dotted booleans as the API body of `GET /api/v1/system/capabilities` (D-11, D-32). Do not break callers.

Add a parallel descriptor list (concept 07 shape) used internally and included under `descriptors:` **only if** we can do it additively. Safer: new key on inventory, not on the existing capabilities document.

Descriptor ids for what Pinky actually has:

- `mobility.move` ← `teleop`
- `mobility.navigate` ← `navigation.goal_navigation`
- `mobility.follow` ← `swarm.follow`
- `mobility.lead` ← `swarm.lead`
- `mobility.dock` ← `docking.supported` (false on Pinky)
- `perception.localize` ← `slam` (false on hardware overlay)

Do **not** add `manipulate.pick`, `scan_rfid`, `infer`, `train` as advertised ids. Those stay concept-only until a slice exists.

A descriptor whose slice is off is omitted or `available: false`. D-32 still applies: advertising true and failing closed with 501 is required; advertising false and returning 200 is forbidden.

## 8. Adapters

Concept 04 package layout is approximated, not cloned into a new tree.

| Adapter | Package | Manifest | Code |
|---|---|---|---|
| Pinky | `rosy_bringup` | `src/rosy_bringup/config/adapter.manifest.yaml` | existing `PinkyProAdapter` |
| OMX | `rosy_omx_adapter` | `src/rosy_omx_adapter/config/adapter.manifest.yaml` | existing `OmxAdapterProfile` |

Manifest fields (concept 04 subset):

```yaml
id: rosy.device.pinky
version: 0.1.0
device_type: mobile_base
requires_slices: [core]
provides: [drive, battery, lidar, local_safety]
```

OMX manifest: `enabled` follows the profile YAML; shipped file stays disabled; `provides` is empty when disabled.

**Registry:** `rosy_core.domain.adapters.AdapterRegistry` loads **known paths** (config list / package share). No setuptools entry points. CORE still must not import OMX driver code (D-62): the registry reads YAML only.

Adapters still must not publish operational `cmd_vel` (D-38).

## 9. Lifecycle and heartbeat

Do not replace `RobotMode` (`IDLE|MANUAL|NAVIGATION|DOCKING|EMERGENCY`).

Add a **derived** `DeviceState` (concept 06) on inventory:

| RobotMode / health | DeviceState |
|---|---|
| starting, no snapshot yet | `BOOTING` |
| EMERGENCY or e-stop | `SAFE_STOP` |
| diagnostics ERROR | `FAULT` |
| NAVIGATION/DOCKING/MANUAL busy | `BUSY` |
| IDLE, health OK | `READY` |
| fleet/runtime degraded policies | `DEGRADED` |

Concept heartbeat = existing 10 Hz `StateSnapshot` (CORE-001) and WS `HeartbeatPayload`. Do not add a second timer.

## 10. Tasks

D-12 stands: the robot exposes atomic actions, not missions.

`TaskKind` maps REST actions to required capability ids:

| TaskKind | API | Requires |
|---|---|---|
| `MOVE` | `POST /api/v1/teleop` | `teleop` / `mobility.move` |
| `NAVIGATE` | `POST /api/v1/navigation/goal` | `navigation.goal_navigation` |
| `RETURN_HOME` | `POST /api/v1/navigation/home` | `navigation.return_home` |
| `FOLLOW` | swarm follow | `swarm.follow` |
| `DOCK` | docking start | `docking.supported` |

No PENDING→SUCCEEDED workflow object. Existing managers already own those state machines. `TaskKind.require(capability)` is a single helper the routes can share so new actions cannot skip CAP-003.

## 11. Control cmd_vel coexistence

Invariant stays: `RosBridge` is the only operational `cmd_vel` publisher.

Add a **source contract** so the leftover Control stack cannot sit beside CORE by accident:

- Operational compose / hardware launch must not include `rosy_control/launch/robot.launch.py`.
- `SafetyNode` constructed by CORE remains `sensor_only=True` (already true).
- Static test: `robot.launch.py` either passes `sensor_only: True` into `safety_node` **or** is referenced from a file named `legacy` and listed in an allow-list that compose is asserted not to include.

Do not change legacy Control unit tests that still exercise the old publisher; they are parity for the archived stack. Change the OS graph contracts.

## 12. Current module classification (concept 13)

| Current | Target mapping | Action |
|---|---|---|
| `rosy_core` | Node runtime + API + command authority | KEEP, add `domain/` |
| `rosy_core.bridge` | fabric (ROS I/O) | KEEP in-process (D-1) |
| `rosy_core.command` | local task execution | KEEP |
| `rosy_bringup` | Pinky adapter | REFACTOR: add manifest, keep UART node |
| `rosy_omx_adapter` | OMX adapter | KEEP disabled + manifest |
| `rosy_control` | sensor evidence worker | KEEP sensor-only path; DEPRECATE full `robot.launch.py` beside CORE |
| `rosy_navigation` | nav slice | KEEP; D-62 catalog |
| `rosy_fleet` | formation seed, not control plane | KEEP; do not rename to rosy-control |
| `deploy/robot` | install + slices | REFACTOR via D-62 |
| `deploy/release` | update agent | KEEP (not rosyctl) |
| `rosy_gz_sim` / description / aux drivers | slices / components | KEEP |

## 13. Acceptance (testable)

1. `CONCEPTS.md` defines the six objects with a “code meaning” line each; concept README has the current-mapping table.
2. Installer `.env` contains `ROSY_ROBOT_NUMBER` after first commission; readback reports it; clash still fails.
3. With `ROSY_NAMESPACE=rosy_03`, `GET /api/v1/system/info` `robot_id` is `rosy_03`. `PUT` of `robot_id=rosy_01` returns 409.
4. `GET /api/v1/system/inventory` returns node, device, components, asset, task kinds; no pick/place/rfid/infer ids.
5. Pinky and OMX adapter manifests parse; OMX disabled ⇒ empty provides; CORE tests load them as YAML without importing MoveIt/Dynamixel.
6. `GET /api/v1/system/capabilities` body is still the CAP-001 dict (existing tests pass).
7. Compose still does not start `robot.launch.py`; a host test fails if that include appears.
8. Host pytest on Windows for all new modules (no rclpy). Device GO is not claimed.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Dual identity leftover in tests that PUT `robot_id` | Rewrite `test_admin_can_update_robot_identity` to name-only + 409 on id |
| CAP-001 clients break if capabilities YAML grows descriptors | Descriptors live on inventory, not the capabilities document |
| Adapter registry imports OMX runtime | YAML-only loader; D-62 import guard test extended |
| “Profile” confusion continues in compose | Docs/glossary only this pass; Compose keys stay |
| Scope creeps into rosyctl | Non-goals above; reject PRs that add apt packaging |
