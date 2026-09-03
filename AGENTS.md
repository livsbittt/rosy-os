<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# ROSY

## Purpose

ROSY is a robot middleware and fleet-control platform (ROS 2 Jazzy, first hardware Pinky Pro). This repository is the robot-side workspace: `rosy_core` is the only external API gateway (FastAPI + rclpy in one process), plus hardware bringup, Nav2/SLAM, Gazebo, Raspberry Pi 5 deploy/release tooling, and charging-dock ESP32 firmware. Fleet server is specified but not implemented here. Upstream was pinky_pro; the tree was fully renamed (ADR D-16). License: Apache-2.0.

## Key Files

| File | Description |
|------|-------------|
| `README.md` | Repo overview, colcon/sim launch, Pi 5 runtime, phase roadmap |
| `LICENSE` | Apache License 2.0 |
| `env.sh` | Dev env: source ROS 2 Jazzy then workspace `install/setup.bash` |
| `.gitignore` | Ignores colcon `build/` `install/` `log/`, `__pycache__`, `.omc/` |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | ROS 2 colcon workspace (see `src/AGENTS.md`) |
| `docs/` | Governance docs: spec, API contract, ADR, plans (see `docs/AGENTS.md`) |
| `deploy/` | Image build, signed release, Pi 5 Docker/systemd runtime (see `deploy/AGENTS.md`) |
| `dock/` | Charging-dock firmware and ROSY-DOCK-001 contract (see `dock/AGENTS.md`) |
| `test/` | Host pytest for deploy/release/motor contracts (see `test/AGENTS.md`) |
| `doc/` | Architecture images and ARM64 notes (see `doc/AGENTS.md`) |
| `reference/` | Frozen upstream pinky_pro zip (see `reference/AGENTS.md`) |
| `.github/` | CI workflow (see `.github/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Treat `docs/spec/ROSY CORE SRS.md`, `docs/reference/ROSY API & Protocol Reference.md`, and `docs/reference/ROSY ADR Log.md` as contracts. Do not invent REST paths, modes, or protocol fields that are not in the API ref or `rosy_core.protocol.schemas`.
- External clients must not speak ROS. `rosy_core` is the only gateway (CORE SRS §1.3). Command Manager is the only `cmd_vel` publisher (D-2).
- Single process: main thread rclpy `MultiThreadedExecutor`, worker thread uvicorn+FastAPI (D-1). Do not split into two processes.
- `slam_toolbox` is optional. `ros_bridge` must import it inside try/except, never at module top (`package.xml` comment). CI boots the node without it.
- Config merge order: `config/rosy_default.yaml` → `~/.rosy/rosy.yaml` → `ROSY_CONFIG`.
- Do not commit colcon `build/`, `install/`, `log/`, or `__pycache__/`.
- Hardware profile is YAML. In-tree Pinky full spec is `src/rosy_core/config/profile.pinky_pro.yaml`. The robot advertises `deploy/robot/config/{profile,capabilities}.${ROSY_RUNTIME_MODE}.yaml` (`core` / `motor` / `hardware`).

### Testing Requirements

```bash
# ROS 2 overlay (Linux / Pi). On Windows, run Python tests that do not need rclpy.
source env.sh
cd src && colcon build --symlink-install

# rosy_core unit tests (no live ROS required for most)
python3 -m pytest src/rosy_core/test/ -v

# Deploy, release, motor, Wi-Fi, host-agent contracts
python3 -m pytest test/ -v

# CI also: flake8 rosy_core (max 120), boot smoke without slam_toolbox
```

CI (`.github/workflows/ci.yml`) on `main` / PRs: colcon build in `ros:jazzy-ros-base`, pytest both trees, `ros2 run rosy_core rosy_core` boot smoke, SaveMap type guard.

### Common Patterns

- Requirement IDs (`CORE-001`, `SAF-005`, `PWR-001`) not section numbers (D-17).
- Python packages: ament_python (`setup.py` + `package.xml`). C++/URDF/Nav2/interfaces: ament_cmake.
- Namespaces + `frame_prefix` for multi-robot (D-4). Default robot id `rosy_01`.
- Dashboard is FastAPI static files under `rosy_core/web/`, not a Node server (D-23). D-7 (React+Vite) is not the current dashboard.

## Dependencies

### Internal

- `src/rosy_core` depends on `src/rosy_interfaces` and (at runtime) bringup/Nav2 topics.
- `deploy/` consumes `src/` via `deploy/robot/Dockerfile`.
- `test/` imports `deploy/release` via `test/conftest.py` `sys.path`.

### External

- ROS 2 Jazzy, rclpy/rclcpp, Nav2, CycloneDDS
- FastAPI, uvicorn, pydantic, PyYAML, httpx, websockets
- Optional: slam_toolbox, sllidar_ros2, Gazebo (ros_gz), wiringPi I2C, ws2811, Dynamixel SDK

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
