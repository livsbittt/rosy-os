## D-56 Odometry and IMU fusion is a measured optional profile

**Status:** Accepted (2026-09-17). Encoder baseline. Fusion profile unselected;
`rosy_imu_bno055` is not in the default image (D-84). Physical calibration
remains pending.

**Context:** Nav2 depends on a stable `map → odom → base` transform and fresh
odometry. The current bridge observes IMU data, but observation alone does not
make it a valid localization input. Uncalibrated or contradictory IMU data can
make AMCL and the costmaps appear healthy while the pose is wrong.

**Decision:** Keep encoder odometry as the baseline. Add wheel+IMU fusion only
as an explicitly selected Device profile after covariance, bias, timestamp,
frame-prefix, dropout and restart tests pass. Missing or stale fusion input
keeps navigation in HOLD; it never silently falls back to an unverified pose.

**Consequences:** The baseline remains deployable without the IMU WIP, while a
future fusion profile has a reproducible acceptance boundary and rollback path.

**Validation / Transition:** Run the optional BNO055 driver on ARM64, capture
stationary and repeated-turn data, compare encoder-only versus fused pose
error, then run the same Nav2 goal/cancel/recovery course on a Pi with wheels
lifted first.

**Implementation note (2026-09-13):** `rosy_imu_bno055` now has bounded,
stage-labelled chip/configuration/fusion startup, explicit `reset_on_start`
control (default `false`), signed unit decoding, invalid-sample rejection,
and transient `sensors/imu/status` health telemetry. The package includes an
opt-in launch/config path and injected-bus fault tests, but it is not loaded by
the default Rosy OS image and does not promote IMU data to localization.

**References:** [Pinky profile](../../src/rosy_core/config/profile.pinky_pro.yaml), [ROS bridge](../../src/rosy_core/rosy_core/bridge/ros_bridge.py), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
