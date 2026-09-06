# Runtime maintainability rules

**Goal:** Keep Pinky runtime slices (core / motor / hardware) and Nav2 wiring in named modules so a later change does not copy YAML, fork launch XML, or hide policy next to ROS launch files.

**Sibling:** Python subpackage cuts inside `rosy_core` are governed by [2026-09-06-module-split-criteria.md](2026-09-06-module-split-criteria.md). This document's unit is a launch file, a ROS package or an overlay YAML; that one's is a Python subpackage. They do not overlap.

## What was not modular

- `hardware.launch.py` mixed motor arg forwarding, Nav2 include, and D-4 YAML rewrite; the rewrite lived in `launch/` behind a `sys.path` insert.
- `bringup_launch.xml` and `gz_bringup_launch.xml` were copies. Gazebo only needed `use_sim_time:=true`.
- `capabilities.pi5-lite.yaml` / `profile.pi5-lite.yaml` duplicated hardware. `board.yaml` already called them an alias.
- `test/test_robot_runtime.py` mixed compose isolation, overlay catalog, Nav2 contracts, and D-27.

## Rules

1. **Catalog owns modes.** `deploy/robot/config/board.yaml` lists real modes and aliases. Overlay YAML exists only for catalog modes (`core`, `motor`, `hardware`). Aliases resolve in `resolve-mode.sh`, never as copied YAML.
2. **Launch files compose.** A launch file includes other launches and forwards arguments. It does not rewrite params or invent TF policy.
3. **Policy is a Python module.** D-4 frame prefixing and the temp params file live in `rosy_navigation.frame_prefix` / `rosy_navigation.params_rewrite`. Import them. Do not `sys.path.insert` the launch directory.
4. **Gazebo does not fork robot Nav2.** `gz_bringup_launch.xml` includes `bringup_launch.xml` and overrides `use_sim_time`. D-2 remaps and composition FQN stay in one XML tree.
5. **Advertise only what that mode launches.** Hardware may set `goal_navigation` only because `hardware.launch.py` starts Nav2. Motor/core stay false. `slam` stays false until a launch actually starts slam_toolbox.
6. **Host tests follow the same cuts.** Compose/D-22/D-27 stay in `test/test_robot_runtime.py`. Nav2 hardware contracts stay in `test/test_nav2_hardware_slice.py`. Shared paths live in `test/robot_contracts.py`.

## Allowed dependencies

```
board.yaml  -->  resolve-mode.sh  -->  runtime-mode.sh / verify-pi.sh
hardware.launch.py  -->  rosy_bringup bringup_robot + rosy_navigation bringup_launch.xml
hardware.launch.py  -->  rosy_navigation.params_rewrite  -->  frame_prefix
gz_bringup_launch.xml  -->  bringup_launch.xml
bringup_launch.xml  -->  localization_launch.xml + navigation_launch.xml
```

CORE still has no `/dev`. IMU/ADC/LED/lamp/emotion stay out of the io image. `BUILD_GO` and `MOTOR_HOLD` stay HOLD.

## Non-goals

Do not rewrite `navigation_launch.xml` composition vs isolated trees into one generator. Do not add a new ROS package *(ROS packages — not Python subpackages inside `rosy_core`, which are governed by the sibling document above)*. Do not invent a kernel or fleet server.
