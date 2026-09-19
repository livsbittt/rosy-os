<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-14 -->

# src

## Purpose

ROS 2 colcon workspace. Build with `colcon build --symlink-install` from this directory (or `source env.sh && colcon build --base-paths src` from repo root). Mix of ament_python (`core`, `bringup`, `emotion`, `led`, `omx_adapter`) and ament_cmake (description, gz_sim, navigation, C++ drivers, interfaces).

## Key Files

No files at this level. Each child is a ROS 2 package with its own `package.xml`.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `core/` | Middleware: identity, state, command mux, safety, power, docking, FastAPI/WS, dashboard (see `core/AGENTS.md`) |
| `bringup/` | Physical motors, odometry, LiDAR, battery publisher, cmd_vel deadman (see `bringup/AGENTS.md`) |
| `navigation/` | Nav2/SLAM launch, maps, params; hardware navigation graph (see `navigation/AGENTS.md`) |
| `description/` | URDF/xacro, meshes, RViz view (see `description/AGENTS.md`) |
| `gz_sim/` | Gazebo worlds, multi-robot launch, lamp plugin; CMake no-ops on aarch64 (see `gz_sim/AGENTS.md`) |
| `interfaces/` | Custom services: Emotion, SetBrightness, SetLamp, SetLed (see `interfaces/AGENTS.md`) |
| `sensor_adc/` | C++ I2C ADC: IR, ultrasonic, battery — aarch64 only (see `sensor_adc/AGENTS.md`) |
| `imu_bno055/` | C++ BNO055 IMU driver — aarch64/wiringPi only (see `imu_bno055/AGENTS.md`) |
| `led/` | Python LED service (`set_led`, `set_brightness`) (see `led/AGENTS.md`) |
| `emotion/` | LCD GIF emotions + info-screen renderer (see `emotion/AGENTS.md`) |
| `lamp_control/` | C++ WS2811 lamp + SetLamp service — aarch64 only (see `lamp_control/AGENTS.md`) |
| `control/` | Absorbed Pinky sensing, camera/OpenCV, calibration, planning, safety-policy, and navigation-session code; final external API and motor command ownership remain in `core` (see `control/AGENTS.md`) |
| `omx_adapter/` | Disabled-by-default OMX model profile and ROS-native ros2_control/MoveIt contract boundary (see `omx_adapter/AGENTS.md`) |
| `site/` | Fleet seed: formation geometry, slot assignment, reference-stream relay, FOR-004 session, CLI (see `site/AGENTS.md`) |
| `games/` | Laptop game host (D-90). Soccer referee/policy. Not a CORE slice. No ROS, no cmd_vel (see `games/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Package names are grouped by domain (e.g. `core/`, `hardware/`). Do not reintroduce `pinky_*`.
- After editing `package.xml` / `setup.py` / `CMakeLists.txt`, rebuild with colcon.
- `resource/<pkg>` is an ament index marker — do not delete; no need for AGENTS.md there.
- Do not check in `src/build`, `src/install`, `src/log`.

### Testing Requirements

```bash
cd src && colcon build --symlink-install --event-handlers console_direct+
python3 -m pytest core/test/ control/test/ site/test omx_adapter/test games/test -q
# ament linters live in each Python package's test/ (copyright, flake8, pep257)
```

### Common Patterns

- Relative topics + namespace/`frame_prefix` (D-4). Avoid hardcoded `/cmd_vel`.
- Python drivers that must run without ROS in unit tests keep kinematics/policy ROS-free.

## Dependencies

### Internal

- Almost every hardware/UI package depends on `interfaces`.
- `bringup` launch includes `description`.
- `gz_sim` includes `description` and `navigation` launches.

### External

- ROS 2 Jazzy overlay (`/opt/ros/jazzy`)
- colcon, ament_cmake / ament_python

<!-- MANUAL: -->
