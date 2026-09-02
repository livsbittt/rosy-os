# Battery Integrity and Low-Battery Alert Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make state of charge correct on the real 2S pack, stop a motor-current sag from tripping SAF-005, show a persistent red alert when the robot is parked and draining, and shut the host down cleanly before the protection board cuts power.

**Architecture:** A ROS-independent `BatteryMonitor` in `rosy_core.power.battery` owns the voltage filter, the OCV curve, the level machine with hysteresis and dwell, the LED alert intent, and the shutdown sentinel. `ros_bridge` feeds it samples and reconciles `set_led` to its declared intent, the same shape as the existing `power/mode` and PWR-005 LiDAR paths. `SafetyManager` keeps SAF-005 thresholds and events and now receives filtered percent. A single host-side systemd unit watches the sentinel file and halts.

**Design:** [2026-09-02-battery-integrity-low-battery-alert-design.md](2026-09-02-battery-integrity-low-battery-alert-design.md)

**Tech Stack:** Python 3.12, ROS 2 `rclpy`, pytest, systemd

---

### Task 1: OCV curve and voltage filter

**Files:**
- Create: `src/rosy_core/rosy_core/power/battery.py`
- Create: `src/rosy_core/test/test_battery.py`

1. Write failing tests with an injected clock for: piecewise-linear
   interpolation across the 2S curve (8.40 V → 100%, 7.32 V → 10%, 6.40 V → 0%),
   exact-breakpoint hits, clamping above 8.40 V and below 6.40 V, monotonicity
   across a descending voltage sweep, fallback to the two-point
   `battery_full_voltage`/`battery_empty_voltage` span when no curve is
   configured, rejection of a non-monotonic or single-point curve at
   construction, and NaN/Inf samples leaving the filter untouched.
2. Add first-order low-pass tests: a step from 7.8 V settles toward the new
   value over `battery_filter_tau_s`, the first sample seeds the filter rather
   than ramping from zero, and a one-sample 400 mV dip moves the filtered
   value by a small fraction of its depth.
3. Run `python -m pytest test/test_battery.py -q` from `src/rosy_core` and
   confirm it fails because the module does not exist.
4. Implement `BatteryCurve`, `BatteryConfig`, and the filter portion of
   `BatteryMonitor`.
5. Run the focused test and confirm it passes.

### Task 2: Level machine with hysteresis and dwell

**Files:**
- Modify: `src/rosy_core/rosy_core/power/battery.py`
- Modify: `src/rosy_core/test/test_battery.py`

1. Write failing tests for the `ok / warning / critical / deep` machine:
   `enter_samples` consecutive samples required to descend a level,
   `exit_samples` plus `battery_hysteresis_percent` required to ascend,
   a pack oscillating on a threshold producing exactly one transition,
   a sustained decline visiting each level once in order, and `deep`
   additionally requiring `battery_deep_dwell_s` of held time before it is
   reported as armed.
2. Assert the ordering invariant directly: no transition may skip a level on
   the way down, and a jump straight from `ok` to `deep` in the input still
   emits `warning` then `critical` first.
3. Run the focused test and confirm the new expectations fail.
4. Implement the level machine and `BatteryStatus`.
5. Run the focused test and confirm it passes.

### Task 3: LED alert intent and priority

**Files:**
- Modify: `src/rosy_core/rosy_core/power/battery.py`
- Modify: `src/rosy_core/rosy_core/protocol/schemas.py`
- Modify: `src/rosy_core/rosy_core/state/manager.py`
- Modify: `src/rosy_core/test/test_battery.py`
- Modify: `src/rosy_core/test/test_protocol_schemas.py`

1. Write failing tests for the declared LED intent: `deep` yields red at 2 Hz,
   `critical` red at 1 Hz, `warning` solid amber, `ok` yields no intent, the
   blink phase is a pure function of the injected clock, and the intent is
   independent of power mode so `STANDBY` still alerts.
2. Write failing tests for the additive `BatteryStatus` field on
   `StateSnapshot` and for `StateManager.set_battery_status`, asserting the
   existing `battery.percent`/`battery.voltage` shape is unchanged so the
   dashboard and `/metrics` keep working.
3. Run the focused tests and confirm they fail.
4. Implement the intent property, the schema field, and the state setter.
5. Run `python -m pytest test -q` from `src/rosy_core` and confirm the whole
   suite passes.

### Task 4: Shutdown sentinel

**Files:**
- Modify: `src/rosy_core/rosy_core/power/battery.py`
- Modify: `src/rosy_core/test/test_battery.py`

1. Write failing tests using `tmp_path` for: no file written before the dwell
   elapses, the file appearing once the dwell is held, its JSON carrying
   `requested_at`, `reason`, `percent`, `voltage`, and `grace_seconds`,
   recovery before the dwell writing nothing, recovery after it removing the
   file, and a repeated `deep` tick not rewriting a file that already exists.
2. Write a failing test that the write is atomic: assert no temporary file
   remains afterwards, and that the published path never exists with partial
   content — write through a sibling temp file plus `os.replace`.
3. Write a failing test that a write failure (unwritable directory) is caught
   and reported rather than raised into the ROS callback.
4. Run the focused test and confirm the new expectations fail.
5. Implement the sentinel writer.
6. Run the focused test and confirm it passes.

### Task 5: Configuration and wiring

**Files:**
- Modify: `src/rosy_core/config/rosy_default.yaml`
- Modify: `src/rosy_core/rosy_core/services.py`
- Modify: `deploy/robot/config/rosy.pi5.example.yaml`
- Modify: `src/rosy_core/test/test_runtime_config.py`

1. Write a failing test asserting that the shipped default config parses into a
   `BatteryConfig` whose curve is the 2S table, and — the regression that
   motivated this work — that a 7.4 V sample against the shipped defaults
   yields a mid-range percent rather than 0.0.
2. Write a failing test that `battery_full_voltage` is 8.4 and
   `battery_empty_voltage` is 6.4 in the shipped default, so the fallback path
   is also correct for this hardware.
3. Run the focused test and confirm it fails.
4. Correct the two voltage constants, add the new `safety:` keys from the
   design, and construct `BatteryMonitor` in `services.py` alongside
   `PowerManager`.
5. Run `python -m pytest test -q` from `src/rosy_core` and confirm it passes.

### Task 6: LED arbitration in the policy layer

**Files:**
- Modify: `src/rosy_core/rosy_core/power/battery.py`
- Modify: `src/rosy_core/test/test_battery.py`

`ros_bridge.py` has no tests and cannot even be imported here — it pulls in
`rclpy`, which is absent on any machine without a ROS install. The original
plan said to extend its tests; there are none to extend. So the decision moves
to where it can be tested and where this codebase already puts decisions, and
the bridge keeps only the reconciliation, exactly as it does for `power/mode`
and the PWR-005 LiDAR intent.

1. Write failing tests for a pure `resolve_led(alert, info_visible,
   gauge_percent, now)` covering the design's priority table: an active alert
   outranks the info-window gauge; a blinking alert alternates fill and clear
   with the injected clock; the gauge shows only when the window is open and no
   alert is active; nothing shows otherwise; and a `None` gauge percent inside
   an open window clears rather than guessing a colour.
2. Write a failing test that the alert survives `info_visible` going false —
   the regression this whole spec exists for.
3. Move the `_LED_STEPS` gauge thresholds out of `ros_bridge` so one module
   decides LED colour, and test the three bands at their boundaries.
4. Run `python -m pytest test/test_battery.py -q` and confirm it passes.

### Task 6b: ros_bridge reconciliation

**Files:**
- Modify: `src/rosy_core/rosy_core/bridge/ros_bridge.py`

Not directly testable here; kept deliberately trivial so that inspection is
enough and the bench check in Task 8 carries the verification.

1. Route `_apply_voltage` through `BatteryMonitor`: feed it the raw sample, take
   filtered percent from it, and pass that to `state.set_battery`,
   `power.on_battery_alert`, and `safety.on_battery_percent`. Delete the inline
   `span`/`percent` computation and `_battery_alert_state`, whose thresholds now
   live in one place.
2. Replace the info-window-only LED call in `_tick_power` with a call to
   `resolve_led` plus a reconciler that only calls the service when the command
   changes, so a 2 Hz blink does not become a 5 Hz service call storm.
3. On the `deep` level, stop motion before the grace period by tripping E-Stop
   through the existing `safety.trigger_estop` path rather than introducing a
   second motor-stop route.
4. Byte-compile the module (`python -m py_compile`) since the suite cannot
   import it, and confirm no other call sites of the deleted helpers remain.

### Task 7: Host shutdown unit

**Files:**
- Create: `deploy/robot/rosy-lowbatt-shutdown.service`
- Create: `deploy/robot/rosy-lowbatt-shutdown.path`
- Modify: `deploy/robot/install-pi.sh`
- Modify: `test/test_robot_runtime.py`

1. Write failing tests that parse the two units and assert: the path unit
   watches `${ROSY_DATA_PATH}/battery-shutdown-request.json`, the service is
   `Type=oneshot`, it runs a freshness check before halting, and it is not
   `WantedBy` anything that would run it at boot independently of the path
   trigger.
2. Write a failing test that the service refuses to halt on a stale sentinel —
   `/var/lib/rosy` is persistent, so a file surviving an unclean shutdown must
   not halt the next boot.
3. Write a failing test that `install-pi.sh` installs and enables both units and
   that the existing `rosy-runtime.service` handling is unchanged.
4. Run `python -m pytest test/test_robot_runtime.py -q` and confirm it fails.
5. Implement the units and the installer change.
6. Run the focused test and confirm it passes.

### Task 8: ADR, contract correction, and docs

**Files:**
- Modify: `docs/reference/ROSY ADR Log.md`
- Modify: `docs/reference/rosy-host-agent-contract.md`
- Modify: `docs/spec/ROSY CORE SRS.md`
- Modify: `docs/deployment/pi5-acceptance-checklist.md`

1. Add **D-27** — low-battery shutdown is the one sanctioned `halt`, recording
   the interlocks from the design: reachable only from the battery policy and
   never from a dwell timer, requires the `deep` level held for
   `battery_deep_dwell_s`, cancelled by recovery, and motors stopped first. Add
   a pointer from D-25 to D-27 so the two are read together.
2. Correct the Host Agent contract status line — the implementation exists and
   is tested; what is missing is a launcher unit and a CORE-side client. Record
   that as outstanding rather than leaving `implementation pending (WP-4)`.
3. Extend SAF-005 in the SRS with the `deep` level, the sentinel behaviour, and
   the statement that reported percent is a filtered estimate with no current
   sensing behind it.
4. Add the bench items to the acceptance checklist: reported percent against a
   multimeter at several points down the discharge, a sag transient producing no
   E-Stop, the alert visible with nobody in front of the robot, and the host
   actually halting.

### Task 9: Full verification

**Files:**
- None (verification only)

1. Run `python -m pytest test -q` from `src/rosy_core`.
2. Run `python -m pytest test -q` from the repository root.
3. Run `cd src && colcon build --symlink-install` and confirm it succeeds.
4. Grep the diff for `TODO`, `FIXME`, `test.skip`, and `@pytest.mark.skip` and
   confirm none were introduced.
5. Confirm the SAF-005 regression is closed by asserting a 7.4 V sample against
   the shipped default config yields a plausible mid-range percent and no
   critical event.
