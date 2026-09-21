# 2026-09-21 Interface Philosophy Refinements: Core State Abstraction & Fallback Patterns

## 1. Context and Problem Statement

`16_ROSY_Interface_Design_Principles.md` successfully establishes a rigorous foundation for ROSY OS interfaces. By banning monolithic "one-size-fits-all" UI libraries and defining strict rules around Evidence States (Law 0) and Surface Grammars, it ensures safety and domain accuracy.

However, as the platform scales toward a "Distributed Robotics Runtime," three critical gaps have emerged in the current design philosophy:

1. **Frontend Maintenance & Law 0 Enforcement (The DX Gap):** Prohibiting a shared UI component library entirely (to preserve surface-specific grammars) risks massive code duplication. Developers implementing the Device Runtime and the Robot Console must independently re-implement the complex logic for tracking `fresh/delayed/disconnected` states. If one implementation has a bug, Law 0 is violated.
2. **Distributed AI Degradation (The Edge Gap):** `00_ROSY_OS_Vision_and_Definition.md` introduces distinct compute profiles (e.g., Pinky vs. RTX 5080 Node). If Pinky loses network connection to its designated RTX 5080 Node, the current capability model only supports `constrained` or `blocked`. It lacks a semantic state for "falling back to local, lower-fidelity logic" (e.g., switching from Cloud VLM to local LiDAR obstacle avoidance).
3. **Cross-Surface Human-in-the-Loop (The HITL Gap):** When an autonomous robot encounters a situation it cannot resolve, it needs human intervention. Currently, there is no unified protocol for how an "Assistance Required" state is projected simultaneously across all four surfaces (Face, Console, Runtime, Fleet) in a consistent manner.

## 2. Proposed Decisions

### Decision 1: Introduce "Headless State Primitives" (Layer 1.5)

To resolve the tension between strict surface grammars and code duplication, we introduce a new architectural layer between **L1 (Law)** and **L2 (Grammar)**: **L1.5 (Headless State Primitives)**.

*   **Concept:** Instead of sharing visual UI components (buttons, cards), ROSY OS will provide a shared **Headless Logic Library** (e.g., pure state machines, React Hooks, or RxJS observables).
*   **Implementation:** This library will solely handle the mathematical and temporal logic of Law 0 (Evidence States). It will process incoming ROS 2 topics, track timestamps, compute staleness against `hold_s` thresholds, and emit `fresh`, `delayed`, or `disconnected` states.
*   **Result:** Surface developers consume these primitives to build their unique UIs. This guarantees that a 500ms delay is evaluated identically on the Fleet and Console surfaces, without forcing them to look the same visually.

### Decision 2: Add `degraded_fallback` to Capability Presentation States

We expand the Presentation State model in Interface Principle §8 to properly handle distributed physical AI architectures.

| State | Meaning | UI Expectation |
|---|---|---|
| `available` | Fully usable with primary systems. | Standard rendering. |
| `constrained` | Usable within stated limits (e.g., low battery, speed capped). | Standard rendering + limit notification. |
| **`degraded_fallback`** | **Primary capability (e.g., Remote AI) failed; system fell back to local/basic capability.** | **Visual indicator of lower fidelity (e.g., striped pattern or specific warning icon), but action is not blocked.** |
| `blocked` | Not usable now (needs reason). | Action impossible, reason explicitly stated. |
| `not_provided` | Capability not installed on this profile. | Omitted. |

### Decision 3: Standardize the "HITL Assistance" Cross-Surface Escalation

We define a universal escalation protocol for Human-in-the-Loop (HITL) requests. When a module emits a `Requiring_Assistance` state, it automatically triggers a predefined grammar response across all surfaces:

1.  **Robot Face (Bystander):** Intent grammar shifts to a standardized "Waiting / Help" expression to signal to humans nearby that the robot is halted intentionally, not broken.
2.  **Robot Console (Field Operator):** Spatial grammar automatically expands the "Act" region, pre-loading manual teleop or override controls.
3.  **Fleet (Dispatcher):** Exception grammar immediately surfaces the robot to the top of the queue with an explicit "Assistance Requested" token, distinct from a hardware fault.
4.  **Device Runtime (Installer):** Procedural grammar logs the exact module and inference confidence score that triggered the handoff.

## 3. Consequences

*   **Positive:** UI development becomes safer and faster because state logic is centralized (Headless Primitives) while visual freedom is preserved. AI edge node disconnections are handled gracefully without completely blocking operations. HITL workflows become predictable.
*   **Negative:** Requires refactoring existing UI implementations (`core_api_web`, `control/web`) to strip out bespoke state-evaluation logic and route it through the new headless primitive library.
*   **Next Steps:** Draft a technical implementation plan for the Headless State Primitives package in `src/core/core_ui_logic/` (or similar) and update CAP-001 definitions.
