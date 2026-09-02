<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_sensor_adc

## Purpose

C++ I2C ADC node (`rosy_sensor_adc`). Channels 0–2 IR, 3 ultrasonic, 4 battery. Publishes `sensor_msgs/Range`, battery state, and respects `power/mode` duty cycling (PWR-001) without slowing down if CORE is absent.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_cmake; rclcpp, sensor_msgs, realtime_tools |
| `CMakeLists.txt` | Builds `src/main_node.cpp` **only on aarch64** (wiringPi); x86 logs skip |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | `main_node.cpp` (see `src/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Default I2C `/dev/i2c-1`, address `0x08`.
- Parameters `rate_active` / `rate_idle` / `rate_standby` (20 / 5 / 2 Hz). Until a valid `power/mode` arrives, keep the startup rate.
- wiringPi I2C is a Pi-only dependency.

### Testing Requirements

ament_lint. Hardware-in-the-loop on Pi; power policy tests are in `rosy_core`.

### Common Patterns

`RealtimePublisher` for range messages.

## Dependencies

### Internal

- CORE publishes `power/mode`; this node subscribes

### External

- rclcpp, wiringPiI2C, realtime_tools

<!-- MANUAL: -->
