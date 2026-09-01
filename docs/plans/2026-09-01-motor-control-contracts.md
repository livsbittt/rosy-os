# Motor Control Contracts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a typed, bounded, testable motor command layer and harden DYNAMIXEL feedback handling.

**Architecture:** A ROS-independent `MotorController` plans differential-drive wheel RPM and returns structured outcomes. The DYNAMIXEL driver independently validates direct RPM calls and exposes pure signed/rollover helpers used by the ROS bringup node.

**Tech Stack:** Python 3.12, ROS 2 `rclpy`, DYNAMIXEL SDK Protocol 2.0, pytest

---

### Task 1: Define command planning contracts

**Files:**
- Create: `src/rosy_bringup/rosy_bringup/motor_control.py`
- Create: `test/test_motor_control.py`

1. Write failing tests for straight, rotation, combined motion, configured
   linear/angular limits, curvature-preserving wheel limit, and invalid values.
2. Run `python -m pytest test/test_motor_control.py -q` and confirm imports fail
   because the new module does not exist.
3. Implement `DriveGeometry`, `DriveLimits`, `MotorCommandPlan`, and
   `plan_twist()` with finite-value validation.
4. Run the focused test and confirm it passes.

### Task 2: Define execution outcomes and stop behavior

**Files:**
- Modify: `src/rosy_bringup/rosy_bringup/motor_control.py`
- Modify: `test/test_motor_control.py`

1. Write failing tests for `APPLIED`, `LIMITED`, `REJECTED`, `DRIVER_ERROR`, and
   explicit `stop()` results using a small recording sink.
2. Run the focused test and confirm missing symbols/behavior fail.
3. Implement `CommandStatus`, `MotorCommandOutcome`, and `MotorController`.
4. Run the focused test and confirm it passes.

### Task 3: Harden the DYNAMIXEL boundary

**Files:**
- Modify: `src/rosy_bringup/rosy_bringup/dynamixel_driver.py`
- Modify: `test/test_dynamixel_driver_safety.py`
- Modify: `test/test_dynamixel_probe.py`

1. Write failing tests for two-ID validation, finite/max RPM validation,
   signed-32 decoding, rollover deltas, and failed bulk-read registration.
2. Run the tests and confirm each new expectation fails for the intended reason.
3. Implement the validation and pure conversion helpers, retaining the existing
   Boolean driver compatibility contract.
4. Run startup/probe/driver tests and confirm they pass.

### Task 4: Integrate the explicit controller into ROS bringup

**Files:**
- Modify: `src/rosy_bringup/rosy_bringup/bringup.py`
- Modify: `src/rosy_bringup/launch/bringup_robot.launch.py`
- Modify: `deploy/robot/compose.yaml`
- Modify: `deploy/robot/.env.example`
- Modify: `test/test_robot_runtime.py`

1. Write failing source/launch/runtime contract tests for the controller and
   speed-limit parameters.
2. Run focused tests and confirm failure.
3. Replace inline conversion with `MotorController`, add parameters, structured
   logging, immediate safe-stop on rejection, and rollover-safe odometry.
4. Run focused and existing deadman tests and confirm they pass.

### Task 5: Document, verify, review, and integrate

**Files:**
- Modify: `docs/deployment/raspberry-pi-runtime.md`
- Modify: `docs/deployment/raspberry-pi-wifi-image.md`
- Modify: `README.md`

1. Document the function contract, defaults, environment overrides, and physical
   acceptance boundary.
2. Run root, bringup, full FastAPI, syntax, ShellCheck, and Compose checks.
3. Request an independent code review and resolve Critical/Important findings.
4. Commit explicit paths and locally fast-forward `main` only if the user's
   pre-existing working changes are still preserved and non-overlapping.
