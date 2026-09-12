<!-- Generated: 2026-09-06 | Updated: 2026-09-06 -->

# rosy_control (absorbed into Rosy OS)

## Purpose
ROS 2 Jazzy package absorbed into the **Rosy OS** workspace for the Pinky Pro desk-maze robot (~11 cm; RPi, RPLidar C1, US-016, 3× IR cliff, BNO055 IMU, OV5647). It provides reusable sensing, camera/OpenCV, calibration, planning, safety-policy, and navigation-session behavior. During absorption its legacy node entry points remain available for parity tests, but `rosy_core` owns the final external API and motor command path in the target runtime.

## Key Files
| File | Description |
|------|-------------|
| `CLAUDE.md` | Deep architecture guide (command chain, lidar trap, parameters) — read first |
| `STEPS.txt` | Korean operator runbook: bringup order, tuning log, LCD/web notes |
| `package.xml` / `setup.py` | ament_python package manifest and entry points |
| `resource/rosy_control` | ament resource marker (generated, do not edit) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `rosy_control/` | Python package: ROS nodes + pure-logic subjects (see `rosy_control/AGENTS.md`) |
| `config/` | Shared and per-node ROS parameters (see `config/AGENTS.md`) |
| `launch/` | Launch files; bringup order matters (see `launch/AGENTS.md`) |
| `test/` | Pure-logic unittest suite, no ROS needed (see `test/AGENTS.md`) |
| `tools/` | Offline ASCII simulator (see `tools/AGENTS.md`) |
| `web/` | web_node dashboard UI — served from share/rosy_control/web (see `web/AGENTS.md`) |
| `map/` | Gazebo world asset for the desk maze |

## For AI Agents

### Working In This Directory
- Treat this directory as part of Rosy OS. The original checkout is archived for provenance; no runtime, build, or test may require it.
- Preserve pure-logic behavior and its tests before changing ROS wiring. The target runtime must not activate this package's legacy final `/cmd_vel` publisher beside `rosy_core`.
- Keep new **decision logic in the pure-logic subjects** (`rosy_control/control/`, `rosy_control/planning/`, `rosy_control/sensing/`, `rosy_control/watch.py`) — no ROS imports there, that is what the tests cover.
- `config/robot.yaml` is the single shared parameter source; per-node yamls override after it.
- The lidar is mounted rotated: **scan 0° = rear, nose ≈ 190°**. Every heading goes through `robot_yaw()` / `wrap_pi()`.
- Docs/STEPS.txt are Korean; code comments and logs are English. Comments explain *why* against measured hardware limits (lidar 5 cm min, US 2 cm blind zone, IR 4095 = ADC saturation, never a cliff).
- Commits: short imperative behavioral summaries.

### Testing Requirements
- `python3 -m pytest test/ -q` from repo root (75 tests; needs `python3-numpy`/`python3-opencv`, no ROS).
- Keep the suite green before committing; add tests for new pure-logic decisions.

### Common Patterns
- Subject mixins: each node = `rclpy.Node` + one-concern mixins (wander = Senses/Judge/Contact/Motion; safety = Bumper/Hazard/Gate/Scale).
- Legacy comparison chain: wander → raw command → safety_node → motors. The OS target owns final command selection in CORE and publication in RosBridge (D-38); do not start both final publishers.
- One fused status label (`control/modes.pick_mode`) on `/robot/mode`; `/safety/mode` is a deprecated same-value alias.

## Dependencies

### External
- ROS 2 Jazzy (`rclpy`, `std_msgs`, `geometry_msgs`, `nav_msgs`, `sensor_msgs`, `tf_transformations`), `slam_toolbox` for mapping.

<!-- MANUAL: -->
