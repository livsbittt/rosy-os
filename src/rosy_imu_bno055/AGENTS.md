<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_imu_bno055

## Purpose

C++ BNO055 IMU driver node `rosy_imu_bno055`. Publishes `sensor_msgs/Imu` on `imu_raw` via a realtime publisher.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_cmake; rclcpp, sensor_msgs |
| `CMakeLists.txt` | Builds `src/main_node.cpp` **only on aarch64** (wiringPi); x86 logs skip |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | `main_node.cpp` (see `src/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Default I2C `/dev/i2c-0`, address `0x28`, rate 100 Hz, `frame_id` `imu_link`.
- Constructor currently `assert(false)` if I2C init fails — do not run this node without hardware.
- SYS_TRIGGER reset (`0x3F`/`0x20`) is part of init; preserve chip init sequence.

### Testing Requirements

ament_lint. Needs Pi + BNO055.

### Common Patterns

wiringPiI2C register reads; `RealtimePublisher<sensor_msgs::msg::Imu>`.

## Dependencies

### Internal

None beyond workspace overlay.

### External

- rclcpp, wiringPiI2C, angles, realtime_tools

<!-- MANUAL: -->
