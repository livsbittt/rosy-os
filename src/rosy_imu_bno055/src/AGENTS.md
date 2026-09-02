<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# src

## Purpose

BNO055 node implementation.

## Key Files

| File | Description |
|------|-------------|
| `main_node.cpp` | `RosyIMUBNO055`: I2C init, reset, `imu_raw` realtime publish |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

Fatal `assert` on I2C failure. Parameters: `interface`, `frame_id`, `rate`.

### Testing Requirements

Hardware. ament_lint at package root.

### Common Patterns

rclcpp node in a single translation unit.

## Dependencies

### External

- rclcpp, wiringPiI2C, realtime_tools, sensor_msgs

<!-- MANUAL: -->
