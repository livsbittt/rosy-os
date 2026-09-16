# ROSY OS Architecture Documentation v0.1

ROSY OS is a **Distributed Robotics & Physical AI Operating Platform** built initially for **Ubuntu + ROS 2**.

## Core Principles

1. ROSY OS is not a replacement for Ubuntu.
2. ROSY OS is a distributed runtime and orchestration layer above Ubuntu + ROS 2.
3. Every node installs only the ROSY components it actually needs.
4. Device, Edge, Compute, AI, and Control roles are separated through installable profiles.
5. ROSY must continue safe local operation even when the central control plane is unavailable.
6. Existing ROS 2 and vendor drivers should be wrapped and standardized rather than rewritten unnecessarily.

## Initial Platform

- Ubuntu 24.04 LTS
- ROS 2 Jazzy
- x86_64 / ARM64
- NVIDIA CUDA / TensorRT where required
- Intel OpenVINO where required

## Primary Profiles

- `rosy-profile-control`
- `rosy-profile-pinky`
- `rosy-profile-omx`
- `rosy-profile-edge`
- `rosy-profile-gpu`
- `rosy-profile-vision`
- `rosy-profile-rfid`
- `rosy-profile-dev`

Profiles may be combined on one node.

## Core Domain Model

ROSY OS uses six primary domain objects:

1. Node
2. Device
3. Component
4. Capability
5. Asset
6. Task

## Document Index

| No. | Document | Purpose |
|---|---|---|
| 00 | ROSY OS Vision & Definition | Product and technical definition |
| 01 | Target Architecture | Overall target architecture |
| 02 | Domain Model | Node / Device / Capability model |
| 03 | Runtime Architecture | Common runtime architecture |
| 04 | Device Adapter Specification | Device adapter/plugin model |
| 05 | ROS 2 Interface Specification | Topic/Service/Action conventions |
| 06 | Device State & Lifecycle | Standard states and lifecycle |
| 07 | Capability Model | Capability abstraction |
| 08 | Task & Workflow | Task and workflow orchestration |
| 09 | Composite Robot | Pinky + OMX and composite assets |
| 10 | Compute Fabric | Gram + RTX cluster architecture |
| 11 | AI & Physical AI | AI/VLA/policy architecture |
| 12 | Dataset & Learning Pipeline | Teach-Record-Train-Deploy loop |
| 13 | Current-to-Target Migration | Refactoring plan |
| 14 | Verification & Acceptance | v1 validation criteria |
| 15 | Ubuntu Modular Installation | Package/profile installation design |

## Current mapping (2026-09-16)

`docs/concept` is the **target** distributed OS. v1 maps those terms onto the live Pinky CORE + D-62 slices stack (D-65). Contract documents win on API, modes, `cmd_vel`, and identity: [CORE SRS](../spec/ROSY%20CORE%20SRS.md) §1.3, [ADR log](../reference/ROSY%20ADR%20Log.md) (D-62 slices), [this design](../plans/2026-09-16-concept-runtime-alignment-design.md). Live glossary: [CONCEPTS.md](../../CONCEPTS.md).

| Concept | v1 mapping | Status |
|---|---|---|
| 00 Vision & definition | CORE SRS product scope | live contract |
| 01 Target architecture | ADR log + this design | target; v1 is CORE + slices |
| 02 Domain model | CONCEPTS.md Node / Device / Component / Capability / Asset / Task | glossary frozen (D-65) |
| 03 Runtime architecture | `rosy_core` process (D-1) | live |
| 04 Device adapter | `rosy_bringup` (Pinky), `rosy_omx_adapter` (disabled) | live adapters; manifests later |
| 05 ROS 2 interface | CORE SRS §1.3 — REST/WS is the external API | concept `/rosy/{device_id}/…` topics are **not** the API |
| 06 Device state & lifecycle | existing `RobotMode`; inventory `device_state` including BOOTING | live |
| 07 Capability | CAP-001 YAML booleans (D-11, D-32); inventory `descriptors[].available` follows DeviceState (concept 07 §5) | live |
| 08 Task & workflow | atomic REST actions; missions stay Fleet (D-12) | live actions; workflow **target-not-built** |
| 09 Composite robot | — | **target-not-built** |
| 10 Compute fabric | — | **target-not-built** |
| 11 AI & Physical AI | — | **target-not-built** |
| 12 Dataset & learning | — | **target-not-built** |
| 13 Current-to-target | this design (Phase 0 = freeze terms) | in progress |
| 14 Verification | Device validation plan | Device GO not claimed |
| 15 Ubuntu modular install | D-62 slices via runtime-mode presets core/motor/hardware (hardware → core+motor+io+nav), not apt/`rosyctl` | apt path **target-not-built** |

## First Refactoring Priority

Start with:

1. `00_ROSY_OS_Vision_and_Definition.md`
2. `01_ROSY_OS_Target_Architecture.md`
3. `02_ROSY_Domain_Model.md`
4. `13_ROSY_Current_to_Target_Migration.md`
5. `15_ROSY_Ubuntu_Modular_Installation.md`

These five documents should be treated as the initial architecture baseline.
