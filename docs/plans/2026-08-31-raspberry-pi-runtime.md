# Raspberry Pi Runtime Isolation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run Rosy on Raspberry Pi OS with separate `rosy-core` and hardware-privileged `rosy-io` containers, while ensuring stale motor commands stop independently of `rosy_core`.

**Architecture:** Keep the accepted FastAPI/rclpy core and ROS Driver Adapter boundary. Build both services from the official ROS 2 Jazzy arm64-capable base, give device access only to `rosy-io`, and connect them over the host ROS domain. Add a deadman in the motor driver so loss of core, DDS, or the API cannot leave the last RPM active.

**Tech Stack:** ROS 2 Jazzy, Python 3.12, FastAPI/Uvicorn, Docker Compose, systemd, pytest.

---

### Task 1: Add the motor command deadman

**Files:**
- Create: `src/rosy_bringup/test/test_command_deadman.py`
- Create: `src/rosy_bringup/rosy_bringup/command_deadman.py`
- Modify: `src/rosy_bringup/rosy_bringup/bringup.py`
- Modify: `src/rosy_bringup/launch/bringup_robot.launch.py`
- Modify: `src/rosy_bringup/config/rosy_params.yaml`

**Steps:**
1. Write pure-Python tests for unarmed, armed, expired-once, and re-armed behavior.
2. Run `python -m pytest src/rosy_bringup/test/test_command_deadman.py -q` and confirm failure because the module does not exist.
3. Implement `CommandDeadman` with an injected monotonic clock.
4. Run the focused tests and confirm they pass.
5. Integrate it into the motor node with a configurable 500 ms timeout and zero-RPM action.
6. Re-run the focused and existing unit tests.

### Task 2: Define the two-service robot runtime

**Files:**
- Create: `test/test_robot_runtime.py`
- Create: `deploy/robot/Dockerfile`
- Create: `deploy/robot/compose.yaml`
- Create: `deploy/robot/entrypoint.sh`
- Create: `deploy/robot/.env.example`
- Create: `deploy/robot/rosy-runtime.service`

**Steps:**
1. Write manifest tests asserting two services, host networking, no privileged containers, device access only on `rosy-io`, bounded logs, and separate build targets.
2. Run the focused test and confirm failure because the runtime files do not exist.
3. Add a multi-stage Dockerfile with shared Jazzy base and `core`/`io` targets.
4. Add Compose configuration with explicit device mappings and restart/logging policies.
5. Add a systemd unit that delegates restart ownership to Compose and starts the hardware profile.
6. Run the manifest tests and `docker compose config` when Docker is available.

### Task 3: Document installation and physical acceptance

**Files:**
- Create: `docs/deployment/raspberry-pi-runtime.md`
- Modify: `README.md`
- Modify: `docs/reference/ROSY ADR Log.md`

**Steps:**
1. Document Pi OS Lite 64-bit prerequisites, device-tree setup, Docker installation boundary, environment values, build/start/stop commands, and recovery.
2. Document explicit acceptance gates for deadman, device removal, core kill, I/O kill, DDS loss, boot recovery, CPU/memory/temperature, and SD-card log growth.
3. State that container/static checks do not establish physical motor safety.

### Task 4: Verify and package the change

**Files:**
- Review all changed files.

**Steps:**
1. Run the deadman tests and runtime manifest tests.
2. Run all repository Python tests with concise output.
3. Run `git diff --check` and inspect `git status`.
4. If Docker is reachable, run Compose validation and build the `core` target; report unavailable hardware/driver build gates separately.
5. Commit the isolated feature branch only after the fresh verification evidence is recorded.
