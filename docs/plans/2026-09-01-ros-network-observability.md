# ROS Network Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a lightweight FastAPI dashboard panel for ROS domain isolation, graph topology, collision indicators, and host network throughput.

**Architecture:** A new cached `RosGraphMonitor` reads rclpy graph metadata and attaches to the existing `HostRuntimeProbe`. The runtime endpoint returns the combined read-only snapshot; local HTML/CSS/JavaScript renders sparklines and an SVG topology without external dependencies.

**Tech Stack:** Python 3, rclpy graph APIs, FastAPI runtime endpoint, vanilla HTML/CSS/JavaScript, pytest, Docker Compose.

---

### Task 1: Define the ROS graph snapshot contract

**Files:**
- Create: `src/rosy_core/test/test_ros_graph_monitor.py`
- Create: `src/rosy_core/rosy_core/system/ros_graph.py`

1. Write failing tests for valid/invalid domain IDs, namespace normalization,
   duplicate node warnings, foreign namespace warnings, topic endpoint edges,
   loopback isolation detection, and collection limits.
2. Run `python -m pytest test/test_ros_graph_monitor.py -q` from
   `src/rosy_core` and confirm the missing-module failure.
3. Implement immutable snapshot construction and a one-second cached monitor.
4. Re-run the focused tests and refactor only while green.

### Task 2: Add bandwidth sampling to the runtime snapshot

**Files:**
- Modify: `src/rosy_core/test/test_host_runtime.py`
- Modify: `src/rosy_core/rosy_core/system/runtime.py`
- Modify: `src/rosy_core/rosy_core/node.py`
- Modify: `deploy/robot/compose.yaml`
- Modify: `test/test_robot_runtime.py`

1. Write failing tests for `/proc/net/dev` parsing, rate calculation, graph
   provider attachment, missing counters, and the read-only host mount.
2. Run the focused tests and confirm the assertions fail for absent fields.
3. Add monotonic sampling, interface summaries, and an optional graph provider.
4. Attach `RosGraphMonitor` after `CoreServices` construction and mount
   `/proc/net/dev` into the core container.
5. Re-run focused tests.

### Task 3: Render the compact dashboard panel

**Files:**
- Modify: `src/rosy_core/test/test_dashboard.py`
- Modify: `src/rosy_core/rosy_core/web/index.html`
- Modify: `src/rosy_core/rosy_core/web/app.js`
- Modify: `src/rosy_core/rosy_core/web/styles.css`

1. Write failing structure tests for domain, isolation, RX/TX chart, collision
   warning list, node/topic counts, and SVG topology hooks.
2. Run the dashboard tests and confirm the new selectors are absent.
3. Add an industrial read-only network panel, bounded history, SVG sparklines,
   and a deterministic two-column node/topic graph renderer.
4. Re-run dashboard and optional browser tests; preserve graceful handling of
   an absent `runtime.ros` object.

### Task 4: Document and verify deployment behavior

**Files:**
- Modify: `docs/deployment/raspberry-pi-runtime.md`
- Modify: `docs/deployment/raspberry-pi-wifi-image.md`

1. Document that DDNS and DDS domains solve different problems.
2. Document per-robot domain/namespace allocation and collision response.
3. Run focused tests, both Python suites, Compose validation, static checks, and
   a Raspberry Pi core image build.
4. Commit only intended files and integrate with `main` after confirming the
   user's existing dirty `rosy_core` work is preserved.
