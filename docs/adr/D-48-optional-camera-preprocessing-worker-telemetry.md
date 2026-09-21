## D-48 Optional camera preprocessing worker telemetry

**Status:** Accepted (2026-09-13). This is an observation and diagnostics
contract; camera output never replaces IR/LiDAR safety authority or grants
motion permission.

**Context:** The absorbed OpenCV path previously combined capture hygiene,
rotation, classification and ROS publication in one node. A bad frame size,
sequence gap or slow preprocessing could therefore be invisible to Device
readback and replay tests.

**Decision:** `rosy_control.sensing.camera_worker.CameraPreprocessWorker` owns
the ROS-free frame contract. It validates the fixed profile resolution and
quarter-turn rotation, counts missing and out-of-order frame IDs, applies a
processing latency budget, and emits secret-free telemetry containing profile
revision, frame ID, dimensions, drops, latency, capture age, CPU time, memory
high-water mark and quality reason. Invalid, stale-order or over-budget frames
are unavailable evidence. The existing `camera_detect_node` uses this worker
when its optional camera is running and publishes the telemetry on
`camera/telemetry`; semantic box/grasp detection remains out of scope.

**Consequences:** The same worker can be exercised with deterministic fixtures
without ROS or Picamera2. A Device profile must keep the camera disabled until
the resolution, latency and real sensor gates are accepted. `camera/telemetry`
is diagnostic evidence and must not be used as a second command authority.

**Validation / Transition:** Worker tests cover profile bounds, rotation,
resolution and corrupt-frame holds, sequence gaps, out-of-order frames,
latency-budget holds and JSON-safe telemetry. The full `rosy_control` suite is
the local software gate; Raspberry Pi camera timing and CSI access remain a
Device/FIELD gate.

**References:** [camera worker](../../src/rosy_control/rosy_control/sensing/camera_worker.py), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
