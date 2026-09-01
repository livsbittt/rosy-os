# Proximity Wake and Sensor Standby Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Duty cycle the ADC sensors and the LCD while Rosy is parked, and wake the robot into a battery/status info display when a person approaches or touches it.

**Architecture:** A ROS-independent `PowerManager` owns the `ACTIVE/IDLE/STANDBY` machine and ultrasonic presence debouncing. `ros_bridge` feeds it range, activity, and battery signals and fans the resulting mode out to `rosy_sensor_adc`, `rosy_emotion`, and `rosy_led`. Motion safety paths are untouched.

**Tech Stack:** Python 3.12, ROS 2 `rclpy`/`rclcpp`, FastAPI, pytest

---

### Task 1: Presence detection and power mode machine

**Files:**
- Create: `src/rosy_core/rosy_core/power/__init__.py`
- Create: `src/rosy_core/rosy_core/power/manager.py`
- Create: `src/rosy_core/test/test_power.py`

1. Write failing tests with an injected clock for: `ACTIVE -> IDLE -> STANDBY`
   dwell transitions, `detect_samples` debounce, `release_samples` plus
   `hysteresis_m` release, rejection of NaN and out-of-range samples, wake
   reasons (`proximity`, `contact`, `activity`, `api`, `battery`), rate mapping
   per mode, and `enabled: false` pinning `ACTIVE`.
2. Run `python -m pytest test/test_power.py -q` from `src/rosy_core` and confirm
   the import fails because the module does not exist.
3. Implement `PowerMode`, `PresenceState`, `PresenceConfig`, `PowerConfig`,
   `PresenceDetector`, and `PowerManager`.
4. Run the focused test and confirm it passes.

### Task 2: Events, snapshot, and safety interlocks

**Files:**
- Modify: `src/rosy_core/rosy_core/power/manager.py`
- Modify: `src/rosy_core/rosy_core/protocol/schemas.py`
- Modify: `src/rosy_core/rosy_core/state/manager.py`
- Modify: `src/rosy_core/test/test_power.py`

1. Write failing tests for `power.mode_changed`, `presence.detected`,
   `presence.cleared`, and `power.wake` emission (including no duplicate events
   on unchanged state), for `PowerStatus` appearing in `StateSnapshot`, and for
   the interlocks that force `ACTIVE` on activity and on a non-`IDLE` robot mode.
2. Run the focused test and confirm the new expectations fail.
3. Implement event emission through the existing `EventBus`, add the additive
   `PowerStatus` snapshot field, and add `StateManager.set_power`.
4. Run `python -m pytest test -q` and confirm the whole suite passes.

### Task 3: REST surface

**Files:**
- Modify: `src/rosy_core/rosy_core/api/v1/routes.py`
- Modify: `src/rosy_core/rosy_core/api/app.py`
- Modify: `src/rosy_core/rosy_core/services.py`
- Modify: `src/rosy_core/config/rosy_default.yaml`
- Modify: `src/rosy_core/test/test_power.py`

1. Write failing tests for `GET /api/v1/power`, `POST /api/v1/power/wake`, and
   `POST /api/v1/power/mode`, including viewer-versus-operator role checks and
   rejection of an unknown mode.
2. Run the focused test and confirm the routes are missing.
3. Add the `power` config block, build `PowerManager` in `CoreServices.build`,
   add `power_router`, and register it in `create_app`.
4. Run the full `rosy_core` suite and confirm it passes.

### Task 4: ROS bridge fan-out

**Files:**
- Modify: `src/rosy_core/rosy_core/bridge/ros_bridge.py`

1. Subscribe to `us_sensor/range` and `batt_state`, storing both in the sensor
   snapshot store alongside the existing lidar and IMU entries.
2. Feed each valid range sample to `PowerManager`, and mark activity from
   `cmd_vel` output, navigation state changes, and battery threshold crossings.
3. Publish `power/mode` on change and at 1 Hz, publish `display/info` while the
   info window is open, and drive the LED ring through an async `set_led` client.
4. Confirm the module still imports under the ROS-free test path and that no new
   dependency leaks into pure logic.

### Task 5: ADC duty cycling

**Files:**
- Modify: `src/rosy_sensor_adc/src/main_node.cpp`
- Modify: `src/rosy_sensor_adc/CMakeLists.txt`

1. Declare `rate_active`, `rate_idle`, and `rate_standby` parameters defaulting
   to 20/5/2 Hz, keeping the existing `rate` parameter as the startup value.
2. Subscribe to `power/mode` and reset the wall timer when the requested rate
   changes; ignore unknown mode strings and keep the current rate.
3. In `standby`, read only the ultrasonic and battery channels so the cycle costs
   two round trips instead of five, and skip the IR publish for that cycle.
4. Build the package with `colcon build --packages-select rosy_sensor_adc` and
   confirm it compiles.

### Task 6: LCD backlight and info screen

**Files:**
- Modify: `src/rosy_emotion/rosy_emotion/rosy_lcd.py`
- Modify: `src/rosy_emotion/rosy_emotion/emotion_server.py`

1. Add `LCD.set_backlight(percent)` and `LCD.sleep()`/`LCD.wake()` around the
   ILI9341 sleep commands, clamping input and leaving `lcd_init` behavior intact.
2. Subscribe `emotion_server` to `power/mode`: dim on `idle`, blank and stop the
   animation timer on `standby`, restore on `active`.
3. Subscribe to `display/info`, render a battery/mode/IP card with PIL, and show
   it until the payload's hold expires, then return to the cached emotion GIF.
4. Confirm the node still runs headless-safe: any LCD failure logs and degrades
   instead of killing the node.

### Task 7: Documentation

**Files:**
- Modify: `docs/reference/ROSY API & Protocol Reference.md`
- Modify: `docs/reference/ROSY ADR Log.md`
- Modify: `src/rosy_core/config/rosy_default.yaml`

1. Add the `power.*` events and the `/api/v1/power` routes to the API reference
   and bump its version table with an additive entry.
2. Record the duty-cycle-not-shutdown decision as a new ADR.
3. Confirm every configuration key used by the implementation is documented in
   `rosy_default.yaml` with its unit.
