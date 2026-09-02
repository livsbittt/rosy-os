# Docking Station Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the DNC stub into a working dock: a state machine that drives the robot in, a charge signal that is real, a return policy that fires at 20%, and an interlock that stops a charging robot from shutting itself down on the charger.

**Architecture:** A ROS-independent `DockingManager` owns the state machine, retries and policy, with an injected clock, a `DockDetector` behind a protocol boundary, a `DockAgent` HTTP client for the dock's status, and a motion executor. `ros_bridge` supplies the real implementations and reconciles, as it does for `PowerManager` and `BatteryMonitor`. Detection itself is deferred to the camera spec; a `SimulatedDetector` carries the tests.

**Design:** [2026-09-02-docking-station-design.md](2026-09-02-docking-station-design.md)

**Depends on:** [battery integrity](2026-09-02-battery-integrity-low-battery-alert.md) — landed.

**Tech Stack:** Python 3.12, ROS 2 `rclpy`, FastAPI, pytest, ESP32 (dock firmware)

---

### Task 1: Dock database

**Files:**
- Create: `src/rosy_core/rosy_core/docking/__init__.py`
- Create: `src/rosy_core/rosy_core/docking/database.py`
- Create: `src/rosy_core/test/test_docking.py`

1. Write failing tests for `DockType` and `DockInstance`: an instance carries
   id, type, map pose, `map_id`, agent address and staging offset; the staging
   pose is derived from the dock pose and offset rather than stored (a taught
   dock pose must not leave a stale staging pose behind); a dock whose `map_id`
   differs from the current map is rejected the way `resolve_goal` rejects a
   waypoint (MAP-002); and the store round-trips through JSON beside
   `waypoints.json`.
2. Write failing tests that the collection is keyed by id and that types are
   separate from instances, so two docks of one type share one detector config.
3. Run `python -m pytest test/test_docking.py -q` from `src/rosy_core` and
   confirm it fails because the module does not exist.
4. Implement `DockType`, `DockInstance`, `DockDatabase`.
5. Run the focused test and confirm it passes.

### Task 2: Detector boundary and simulated detector

**Files:**
- Create: `src/rosy_core/rosy_core/docking/detector.py`
- Modify: `src/rosy_core/test/test_docking.py`

1. Write failing tests for `DockObservation` (relative pose in `base_link`, plus
   a timestamp and a confidence) and for `SimulatedDetector`: it replays a
   scripted sequence of observations, can be told to lose the dock, and reports
   `None` before `start` and after `stop`.
2. Write a failing test that an observation older than a staleness bound is not
   returned as current — a detector that keeps handing back its last sighting
   turns a lost dock into a confident wrong pose.
3. Run the focused test and confirm the new expectations fail.
4. Implement the `DockDetector` protocol, `DockObservation` and
   `SimulatedDetector`.
5. Run the focused test and confirm it passes.

### Task 3: Dock agent client

**Files:**
- Create: `src/rosy_core/rosy_core/docking/agent.py`
- Modify: `src/rosy_core/test/test_docking.py`

1. Write failing tests against a stub HTTP server for the happy path and for
   every way it goes wrong: unreachable host, connect timeout, read timeout,
   non-200, malformed JSON, missing fields, and a fault list. None may raise;
   each maps to a distinct outcome so the state machine can tell "the dock says
   no current" from "the dock did not answer".
2. Write a failing test that `load_present` and `charging` stay independent —
   contacts engaged with no current is a real and different situation from no
   contact.
3. Write a failing test that the client never blocks longer than its timeout,
   so a hung dock cannot stall the tick that polls it.
4. Run the focused test and confirm it fails.
5. Implement `DockAgent` and `DockStatus`.
6. Run the focused test and confirm it passes.

### Task 4: Charging confirmation

**Files:**
- Create: `src/rosy_core/rosy_core/docking/charging.py`
- Modify: `src/rosy_core/test/test_docking.py`

1. Write failing tests for the two-source rule: charging is confirmed only when
   the dock reports current **and** the filtered pack voltage is not falling
   across a confirmation window. Cover a dock claiming current while voltage
   falls (rejected), a dock claiming current with voltage flat or rising
   (accepted), an unreachable dock (not confirmed, not an error), and confirmation
   surviving a single noisy voltage sample.
2. Write a failing test naming the reason: a device on the LAN asserting
   `charging: true` must not be able to disable a safety path on its own.
3. Run the focused test and confirm it fails.
4. Implement `ChargingConfirmation` against the existing `BatteryMonitor`
   filtered voltage.
5. Run the focused test and confirm it passes.

### Task 5: Docking state machine

**Files:**
- Create: `src/rosy_core/rosy_core/docking/manager.py`
- Modify: `src/rosy_core/rosy_core/protocol/schemas.py`
- Modify: `src/rosy_core/test/test_docking.py`
- Modify: `src/rosy_core/test/test_protocol_schemas.py`

1. Write failing tests for the `DockState` enum and its additive appearance on
   `StateSnapshot`, asserting existing snapshot fields are untouched.
2. Write failing tests for the phase sequence
   `STAGING → ACQUIRING → APPROACHING → SETTLING → DOCKED → CHARGING` with a
   `SimulatedDetector`, and for each failure route: detector never acquires,
   detector lost during approach, approach times out, and settle produces no
   current.
3. Write failing tests for retries: a failure backs off, re-stages and retries;
   `max_retries` exhausted lands in `DOCK_FAILED`; `DOCK_FAILED` is terminal and
   does not retry on its own; and a settle failure re-seats rather than
   re-staging, because arriving without current is a different fault from not
   arriving.
4. Write failing tests for `UNDOCKING`: it runs on odometry for a configured
   distance with the detector stopped, and does not consult the detector or Nav2
   until clear.
5. Write failing tests for the interlocks: docking refused without
   `capability.docking.supported`; entered only from `IDLE`; E-Stop at each
   phase aborts to `DOCK_FAILED` and releases the mode; the costmap exemption is
   requested only during `APPROACHING` and always released.
6. Run the focused tests and confirm they fail.
7. Implement `DockingManager`.
8. Run `python -m pytest test -q` from `src/rosy_core` and confirm the suite
   passes.

### Task 6: Charging suppresses the deep shutdown

**Files:**
- Modify: `src/rosy_core/rosy_core/power/battery.py`
- Modify: `src/rosy_core/test/test_battery.py`

The defect this prevents: a robot that reaches a dock at 4% is still at `deep`
for some minutes, halts on the charger, and — per D-25 — has no wake source to
come back from.

1. Write failing tests that a confirmed-charging input prevents the shutdown
   from arming, withdraws an already-written sentinel, and that withdrawing the
   suppression re-arms only after the full dwell rather than instantly.
2. Write a failing test that suppression requires *confirmed* charging, so the
   dock's word alone cannot disable it.
3. Write a failing test that the `deep` LED alert is unaffected — the robot
   should still be visibly flat while it charges.
4. Run the focused test and confirm it fails.
5. Implement `BatteryMonitor.set_charging(confirmed)`.
6. Run `python -m pytest test/test_battery.py -q` and confirm it passes.

### Task 7: Return to dock at the warning level

**Files:**
- Modify: `src/rosy_core/rosy_core/docking/manager.py`
- Modify: `src/rosy_core/rosy_core/services.py`
- Modify: `src/rosy_core/config/rosy_default.yaml`
- Modify: `src/rosy_core/test/test_docking.py`

1. Write failing tests that reaching the warning level with a configured dock
   starts a return, that it does not start when no dock is configured, that it
   does not restart while already docking, and that it does not fire on a robot
   already `DOCKED` or `CHARGING`.
2. Write failing tests for precedence: an active manual session (priority 3)
   defers the return and it is retried afterwards; E-Stop blocks it; an active
   navigation goal is cancelled and reported.
3. Write a failing test that the existing SAF-005 critical row is unchanged —
   `RETURN_HOME`/`STOP` remains the fallback for a robot with no dock.
4. Run the focused test and confirm it fails.
5. Implement the policy, add `docking:` configuration, and wire `DockingManager`
   into `CoreServices`.
6. Run `python -m pytest test -q` from `src/rosy_core` and confirm it passes.

### Task 8: API surface

**Files:**
- Modify: `src/rosy_core/rosy_core/api/v1/routes.py`
- Modify: `src/rosy_core/rosy_core/capability.py`
- Modify: `src/rosy_core/test/test_api.py`

`routes.py` is being edited by a concurrent session; re-read it immediately
before editing and keep the change confined to new docking routes.

1. Write failing tests that `POST /api/v1/docking/dock` and `/undock` still
   return `501` when `docking.supported` is false — the existing DNC-003
   contract must not regress — and that with the capability enabled they accept
   a dock id, reject an unknown id, and reject a dock on another map.
2. Write failing tests for `GET /api/v1/docking/status`, for the dock CRUD and
   teach endpoints, and for role gating (Operator for commands, Viewer for
   status).
3. Run the focused test and confirm it fails.
4. Implement the routes.
5. Run `python -m pytest test -q` from `src/rosy_core` and confirm it passes.

### Task 9: ros_bridge reconciliation

**Files:**
- Modify: `src/rosy_core/rosy_core/bridge/ros_bridge.py`

Not testable here — the module imports `rclpy`, which is absent. Kept trivial so
inspection suffices; the bench check in Task 11 carries the verification.

1. Supply the real motion executor (`cmd_vel` through the existing mux at
   `docking` priority, and `NavigateToPose` for the staging leg) and the real
   detector selected by dock type.
2. Feed `DockAgent` status and `BatteryMonitor` voltage into
   `ChargingConfirmation`, and pass the result to `BatteryMonitor.set_charging`.
3. Publish `DockState` into the snapshot each tick.
4. Byte-compile with `python -m py_compile` and confirm no other call sites
   changed.

### Task 10: Dock firmware and its contract

**Files:**
- Create: `dock/README.md`
- Create: `dock/firmware/` (ESP32 sketch)
- Create: `test/test_dock_contract.py`

1. Write failing tests that the documented status schema matches what
   `DockAgent` parses — one schema, two readers, and they must not drift.
2. Document and test the safety rule that gives the dock its controller: output
   is energised only when a load is detected and de-energised on removal or
   fault. Exposed permanently-live DC contacts on a floor are the hazard this
   exists to prevent.
3. Implement the firmware and the contract document.
4. Run the focused test and confirm it passes.

### Task 11: Contracts, ADR amendment, and checklist

**Files:**
- Modify: `docs/spec/ROSY CORE SRS.md`
- Modify: `docs/reference/ROSY API & Protocol Reference.md`
- Modify: `docs/reference/ROSY ADR Log.md`
- Modify: `docs/deployment/pi5-acceptance-checklist.md`

1. Rewrite DNC-001~003 from stub to implemented, and add the state set, the
   dock database, the teach flow and the 20% return policy.
2. Update the API Reference: new `DockState` values (additive, PRT-006 MINOR
   bump), the docking routes, and the dock agent contract.
3. Add **D-28** for the docking architecture — the decisions worth a record are
   that the docking action owns its Nav2 leg rather than the mode table gaining
   an edge, that the robot polls the dock rather than being pushed to, and that
   charging needs two independent sources. Amend **D-27** with the charging
   suppression interlock.
4. Add a `DOCK_GO` section to the acceptance checklist: capture envelope from a
   spread of starting poses, contact resistance across repeated cycles, the
   costmap exemption actually clearing, a robot docking at 4% charging rather
   than halting, and a spoofed dock failing to suppress the shutdown.

### Task 12: Full verification

**Files:**
- None (verification only)

1. Run `python -m pytest test -q` from `src/rosy_core` and from the repository
   root.
2. Run `cd src && colcon build --symlink-install` where ROS is available.
3. Grep the diff for `TODO`, `FIXME`, `test.skip` and `@pytest.mark.skip`.
4. Confirm `docking.supported=false` robots still get `501` on both endpoints,
   so the stub contract survives the feature that replaces it.
