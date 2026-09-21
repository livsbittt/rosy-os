## D-47 CORE sensor adapter calibration binding

**Status:** Accepted (2026-09-13). This is a software startup contract; physical sensor and motion acceptance remain separate Device/FIELD gates.

**Context:** The absorbed `rosy_control` sensor worker must use the calibration record belonging to the mounted Rosy OS data generation. A ROS parameter readback alone cannot prove that the correct record was used, and silently combining explicit parameters with a record can create an unsafe split profile.

**Decision:** When `control.sensor_adapter.enabled` and `control.sensor_adapter.calibration.required` are both true, CORE loads the snapshot before constructing the worker. The loader requires the exact device, hardware, geometry, sensor, and data-generation context, validates the digest and generation-bound path, and accepts only the seven measured SafetyNode parameters. Explicit parameter values must match the snapshot; conflicts fail closed. The worker remains `sensor_only`, and the existing CORE policy remains the only command authority. The packaged default keeps both switches disabled.

**Consequences:** The Device runtime supplies `ROSY_DATA_GENERATION` and `ROSY_DATA_PATH`; a stale, missing, malformed, or cross-device record prevents worker startup before any ROS node is created. CORE exposes the loaded record's revision and digest for diagnostics, while the worker's applied policy revision continues to label observations. Calibration loading is not an acknowledgement of motor policy adoption.

**Validation / Transition:** Unit tests cover pre-construction loading, parameter conflict, generation mismatch, disabled-path non-access, and default YAML opt-in. Device commissioning must still capture the JSON readback, verify the immutable ARM64 manifest, and complete the stationary sensor and motion gates before enabling the switches.

**References:** [calibration binding plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md), [control absorption results](../plans/2026-09-12-control-absorption-results.md), [Device readback contract](../deployment/raspberry-pi-runtime.md).

---
