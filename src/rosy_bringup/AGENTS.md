<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_bringup

## Purpose

Physical robot bringup: Dynamixel differential drive, odometry/TF, optional LiDAR and battery publisher, and a driver-side cmd_vel deadman independent of `rosy_core` (D-22).

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_python; exec depends include sllidar_ros2, robot_state_publisher |
| `setup.py` / `setup.cfg` | Package install |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `rosy_bringup/` | Nodes and ROS-free motor contracts (see `rosy_bringup/AGENTS.md`) |
| `launch/` | `bringup_robot.launch.py` with namespace/frame_prefix (see `launch/AGENTS.md`) |
| `config/` | Params + localhost CycloneDDS (see `config/AGENTS.md`) |
| `scripts/` | Per-robot env isolation `rosy_env.sh` (see `scripts/AGENTS.md`) |
| `test/` | Deadman + ament linters (see `test/AGENTS.md`) |
| `resource/` | ament marker |

## For AI Agents

### Working In This Directory

- `motor_control.py` and `command_deadman.py` must remain importable without rclpy (repo `test/` uses them).
- Default serial `/dev/ttyAMA4`, baud 1_000_000, IDs `[1, 2]` (left, right). Do not coerce IDs.
- Driver enforces RPM limits and 32-bit encoder wrap even if CORE is down.
- Stale `cmd_vel` → confirmed zero-RPM stop (`CommandDeadman`).

### Testing Requirements

```bash
python3 -m pytest test/test_motor_control.py test/test_bringup_motor_contracts.py \
  test/test_dynamixel_driver_safety.py src/rosy_bringup/test/test_command_deadman.py -v
```

### Common Patterns

Launch arguments: `namespace`, `enable_battery`, `enable_lidar`, `use_sim_time`.

## Dependencies

### Internal

- `rosy_description` (robot_state_publisher from launch)

### External

- dynamixel_sdk, sllidar_ros2, tf_transformations, rclpy

<!-- MANUAL: -->
