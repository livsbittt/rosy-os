## D-57 ROS-native first; board and vendor differences stay in adapters

**Status:** Accepted (2026-09-13). This establishes a development direction;
it does not certify a physical device.

**Context:** Rosy OS already uses ROS 2 messages and Nav2, but the Pinky motor
path is a custom Python driver and the OMX path is not implemented. Replacing
those paths with more bespoke middleware would duplicate lifecycle, parameter,
diagnostic and action contracts that ROS already provides.

**Decision:** Prefer ROS 2 standard interfaces and runtime facilities in this
order: launch parameters and YAML profiles, lifecycle and diagnostics, Nav2
actions/costmaps, `sensor_msgs`/`image_transport`, `robot_localization`,
`ros2_control`, and MoveIt 2. Pinky Pro transport/kinematics and OMX vendor
transport/model details are adapter responsibilities. Adapters may translate
hardware and expose standard ROS interfaces, but they must not bypass CORE
safety or publish the final base `cmd_vel`. Unknown or unmeasured hardware
stays disabled and fails closed.

**Consequences:** The current `rosy_bringup` driver remains the baseline while
a measured `ros2_control` replacement is proven. `rosy_bringup.pinky_pro_adapter`
now validates parameters before SDK construction. `rosy_omx_adapter` provides a
disabled-by-default, model-neutral controller contract; it does not pretend a
vendor driver exists, and the Device `io` image ships its profile validator
without activating hardware. ROS-native packages can be selected without
changing the external CORE API.

**Validation / Transition:** Keep parameter and adapter tests ROS-free, then
run launch/graph tests in the Jazzy overlay. On Pi, compare the future
`ros2_control` base adapter with the current driver for encoder sign, odometry,
command limits, deadman, torque-off and restart. Select an OMX model only after
driver, joint limits, MoveIt collision scene, hand-eye, power and payload tests
pass.

**References:** [Pinky adapter](../../src/rosy_bringup/rosy_bringup/pinky_pro_adapter.py), [OMX adapter](../../src/rosy_omx_adapter/rosy_omx_adapter/profile.py), [ROS-native implementation checkpoint](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
