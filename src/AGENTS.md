<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-14 -->

# src

## Purpose

ROS 2 colcon workspace. Build with `colcon build --symlink-install` from this directory (or `source env.sh && colcon build --base-paths src` from repo root). Mix of ament_python (`rosy_core`, `rosy_bringup`, `rosy_emotion`, `rosy_led`, `rosy_omx_adapter`) and ament_cmake (description, gz_sim, navigation, C++ drivers, interfaces).

## Key Files

No files at this level. Each child is a ROS 2 package with its own `package.xml`.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `rosy_core/` | Middleware: identity, state, command mux, safety, power, docking, FastAPI/WS, dashboard (see `rosy_core/AGENTS.md`) |
| `rosy_bringup/` | Physical motors, odometry, LiDAR, battery publisher, cmd_vel deadman (see `rosy_bringup/AGENTS.md`) |
| `rosy_navigation/` | Nav2/SLAM launch, maps, params; hardware navigation graph (see `rosy_navigation/AGENTS.md`) |
| `rosy_description/` | URDF/xacro, meshes, RViz view (see `rosy_description/AGENTS.md`) |
| `rosy_gz_sim/` | Gazebo worlds, multi-robot launch, lamp plugin; CMake no-ops on aarch64 (see `rosy_gz_sim/AGENTS.md`) |
| `rosy_interfaces/` | Custom services: Emotion, SetBrightness, SetLamp, SetLed (see `rosy_interfaces/AGENTS.md`) |
| `rosy_sensor_adc/` | C++ I2C ADC: IR, ultrasonic, battery — aarch64 only (see `rosy_sensor_adc/AGENTS.md`) |
| `rosy_imu_bno055/` | C++ BNO055 IMU driver — aarch64/wiringPi only (see `rosy_imu_bno055/AGENTS.md`) |
| `rosy_led/` | Python LED service (`set_led`, `set_brightness`) (see `rosy_led/AGENTS.md`) |
| `rosy_emotion/` | LCD GIF emotions + info-screen renderer (see `rosy_emotion/AGENTS.md`) |
| `rosy_lamp_control/` | C++ WS2811 lamp + SetLamp service — aarch64 only (see `rosy_lamp_control/AGENTS.md`) |
| `rosy_control/` | Absorbed Pinky sensing, camera/OpenCV, calibration, planning, safety-policy, and navigation-session code; final external API and motor command ownership remain in `rosy_core` (see `rosy_control/AGENTS.md`) |
| `rosy_omx_adapter/` | Disabled-by-default OMX model profile and ROS-native ros2_control/MoveIt contract boundary (see `rosy_omx_adapter/AGENTS.md`) |
| `rosy_fleet/` | Fleet seed: formation geometry, slot assignment, reference-stream relay, FOR-004 session, CLI (see `rosy_fleet/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Package names are `rosy_*`. Do not reintroduce `pinky_*`.
- After editing `package.xml` / `setup.py` / `CMakeLists.txt`, rebuild with colcon.
- `resource/<pkg>` is an ament index marker — do not delete; no need for AGENTS.md there.
- Do not check in `src/build`, `src/install`, `src/log`.

### Testing Requirements

```bash
cd src && colcon build --symlink-install --event-handlers console_direct+
python3 -m pytest rosy_core/test/ rosy_control/test/ rosy_fleet/test rosy_omx_adapter/test -q
# ament linters live in each Python package's test/ (copyright, flake8, pep257)
```

### Common Patterns

- Relative topics + namespace/`frame_prefix` (D-4). Avoid hardcoded `/cmd_vel`.
- Python drivers that must run without ROS in unit tests keep kinematics/policy ROS-free.

## Dependencies

### Internal

- Almost every hardware/UI package depends on `rosy_interfaces`.
- `rosy_bringup` launch includes `rosy_description`.
- `rosy_gz_sim` includes `rosy_description` and `rosy_navigation` launches.

### External

- ROS 2 Jazzy overlay (`/opt/ros/jazzy`)
- colcon, ament_cmake / ament_python

<!-- MANUAL: -->
