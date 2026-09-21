# Pinky Pro Integrated Gazebo Acceptance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce a fresh, reproducible, run-bound ROS-SIM artifact proving Pinky-sized mapping, safe traversal, camera semantics, Nav2 navigation, single command authority, and final stop in the measured map.

**Architecture:** Compose the existing semantic Gazebo graph and scan-safe route with live SLAM. End the mapping process before starting Nav2, run one bounded action goal, and let one collector audit map, perception, trajectory geometry, graph ownership, and final velocity.

**Tech Stack:** ROS 2 Jazzy, Gazebo Harmonic, slam_toolbox, Nav2, rclpy, Python, pytest, launch/launch_ros.

---

### Task 1: Restore CORE startup

**Files:**
- Modify: `src/core/core/core/services.py`
- Modify: `src/core/core/test/test_fleet_agent.py`

1. Add a focused test that builds `CoreServices` and requires a disabled `FleetAgent` when no hub credentials exist.
2. Run it and retain the `NameError` RED result.
3. Import `FleetAgent` explicitly from its owning module.
4. Run the focused Fleet/Core tests GREEN.

### Task 2: Make mapping traversal a clean sequential phase

**Files:**
- Modify: `src/sim/gz_sim/scripts/map_v2_runner.py`
- Modify: `src/sim/gz_sim/test/test_map_v2_traversal.py`

1. Test a configurable route start index and terminal-exit contract.
2. Add parameters that permit route index 0 and exit only after a final-zero dwell.
3. Preserve default behavior for existing callers.
4. Run traversal tests GREEN.

### Task 3: Add a Nav2 acceptance probe

**Files:**
- Create: `src/sim/gz_sim/scripts/pinky_nav2_probe.py`
- Create: `src/sim/gz_sim/test/test_pinky_nav2_probe.py`
- Modify: `src/sim/gz_sim/CMakeLists.txt`
- Modify: `src/sim/gz_sim/package.xml`

1. Test pure goal-distance and terminal-result rules.
2. Implement a thin `NavigateToPose` action client that waits for Nav2, sends a bounded goal, publishes structured status, and emits no velocity command.
3. Install the script and declare runtime dependencies.
4. Run the probe contracts GREEN.

### Task 4: Add the run-bound evidence collector

**Files:**
- Create: `src/sim/gz_sim/scripts/pinky_acceptance.py`
- Create: `src/sim/gz_sim/test/test_pinky_acceptance.py`
- Modify: `src/sim/gz_sim/CMakeLists.txt`
- Modify: `src/sim/gz_sim/package.xml`

1. Test wall clearance, reachable-map metrics, semantic accumulation, gate failures, publisher ownership, and final-zero dwell as ROS-free logic.
2. Implement subscriptions for odometry, map, camera, line/road observations, mapping status, Nav2 status, and final velocity.
3. Write an atomic result JSON on success or timeout, preserving every individual gate.
4. Run collector tests GREEN.

### Task 5: Compose the integrated launch

**Files:**
- Create: `src/sim/gz_sim/launch/pinky_integrated_acceptance.launch.py`
- Modify: `src/sim/gz_sim/test/test_gz_package_contract.py`
- Modify: `src/sim/gz_sim/CMakeLists.txt`

1. Test that the launch uses the traffic-enhanced measured world, accepted geometry, actual camera, delayed traversal, process-exit Nav2 transition, CORE, and collector.
2. Generate root SLAM/Nav2 parameters from the checked-in defaults while enforcing `0.086 m` radius, `0.010 m` padding, and simulation time.
3. Start Nav2 and the probe only after the mapping runner exits.
4. Shut down only after the collector writes a terminal result.

### Task 6: Execute and verify

**Files:**
- Create: `docs/validation/pinky-integrated-gazebo-2026-09-22/README.md`
- Create: `docs/validation/pinky-integrated-gazebo-2026-09-22/result.json`

1. Run focused host tests, then the full relevant CORE/control/simulation suites.
2. Build the ROS packages in WSL Jazzy with a temporary build/install/log root.
3. Launch headless with a fresh ROS domain and run ID until the collector exits.
4. Inspect the JSON, logs, graph ownership, map metrics, and final-zero evidence.
5. Record exact PASS/HOLD boundaries, including the separate physical-device gate.
6. Re-run tests and `git diff --check`, commit coherent units, refresh main ancestry, and integrate without touching unrelated WIP.
