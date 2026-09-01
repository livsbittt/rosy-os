# Rosy Motor Control Contracts Design

## Objective

Make motor behavior explicit and testable without weakening the existing UART,
DYNAMIXEL torque, or deadman safeguards. A command must have one visible result:
`APPLIED`, `LIMITED`, `REJECTED`, or `DRIVER_ERROR`.

## Architecture

Add a ROS-independent motor-control module between `cmd_vel` and the DYNAMIXEL
driver. It owns differential-drive conversion, input validation, configured
linear/angular limits, wheel-RPM limiting, and structured outcomes. The ROS node
continues to own subscriptions and logging, while the DYNAMIXEL driver remains
the final hardware boundary and independently rejects malformed or excessive
RPM values.

The command path is:

`Twist -> MotorController.command_twist() -> MotorCommandPlan -> set_double_rpm()`

The controller preserves curvature when wheel RPM would exceed the configured
maximum by scaling both wheels together. Invalid numbers never reach the UART.
If the driver rejects a command, the outcome is `DRIVER_ERROR`; the ROS node
immediately attempts zero RPM and leaves the deadman armed when zero cannot be
confirmed.

## Feedback and odometry

Add pure helpers for signed 32-bit DYNAMIXEL values and encoder rollover deltas.
The driver must verify every bulk-read registration and return an unavailable
feedback tuple on any incomplete transaction. The ROS node uses rollover-safe
deltas so crossing `0x7fffffff`/`0x80000000` cannot create a false odometry jump.

## Safety boundary

- Exactly two distinct motor IDs are required.
- Geometry and all limits must be positive finite numbers.
- NaN, infinity, non-numeric commands, and out-of-range direct RPM are rejected.
- A stop is a first-class function and is confirmed only after the driver
  accepts zero RPM.
- Existing zero-before-torque startup, fail-to-torque-off cleanup, UI hold-to-
  drive behavior, and 0.5 second driver deadman remain authoritative.
- Distance/angle motion is not added until physical encoder direction and wheel
  calibration are accepted on the lifted-wheel bench.

## Verification

Pure unit tests cover conversion, limiting, invalid inputs, structured outcomes,
direct-driver barriers, bulk-read setup failures, signed decoding, and rollover.
Existing startup, probe, deployment, dashboard, and deadman suites must remain
green. Physical wheel motion remains a separate Raspberry Pi acceptance gate.
