## D-58 Hardware motion requires an authoritative readiness gate

**Status:** Accepted (2026-09-13). This closes the software-side gate; ROS
graph, ARM64 image and physical stop-latency evidence remain required.

**Context:** A lifecycle manager or a discovered motor node can exist while
localization, Nav2 controllers, costmaps or the final motor transport is
still inactive. Treating node discovery or a REST `accepted` response as
readiness can therefore pass a velocity candidate into an incomplete graph.

**Decision:** Hardware mode requires active lifecycle transitions from AMCL,
map server, controller server and both costmaps, plus a refreshed latched
`motor/ready` adapter lease. The ROS-free
`NavigationReadinessGate` is the single decision used by navigation requests,
the command mux and the final CORE publisher. Until every required component
is active and fresh, CORE reports `navigation_readiness=ERROR`, refuses new
navigation/teleop requests with `HARDWARE_NOT_READY`, and publishes zero at
the normal 50 Hz cadence. Core/simulation profiles keep the gate disabled
unless explicitly opted in.

**Consequences:** Lifecycle state is no longer inferred from node discovery;
the motor adapter must publish a transient-local ready signal and refresh it
while its transport is alive. This software gate supplements, and never
replaces, the driver deadman and physical E-stop. A missing transition or
expired lease leaves the runtime in HOLD without creating a competing
`cmd_vel` publisher.

**Validation / Transition:** Host tests cover all component combinations,
lease expiry, API/command rejection and zero output. The bridge registration
contract covers the six readiness subscriptions, and bringup tests cover the
latched adapter signal. Repeat lifecycle, restart, UART-loss and stop-latency
measurements on the signed ARM64 image with lifted wheels before promoting
hardware motion.

**References:** [readiness gate](../../src/rosy_core/rosy_core/navigation/readiness.py), [ROS bridge](../../src/rosy_core/rosy_core/bridge/ros_bridge.py), [Pinky bringup](../../src/rosy_bringup/rosy_bringup/bringup.py), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
