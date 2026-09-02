<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# bridge

## Purpose

ROS-101: the only module allowed to import rclpy message types and talk to the ROS graph. Publishes the muxed `cmd_vel` at 50 Hz. Optional `slam_toolbox` must be imported inside try/except.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `ros_bridge.py` | Subs (odom, battery, nav_cmd_vel, range, batt_state), pubs (cmd_vel, power/mode, display/info), Nav2 action, TF, LiDAR motor services, SetLed |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- `SaveMap` name field is `std_msgs/String`, success code 0. Wrong types SIGABRT — CI guards this.
- Topics: `cmd_vel` out; `nav_cmd_vel` in from Nav2; `battery/voltage`; `us_sensor/range`; `batt_state`.
- LED and LiDAR start/stop are services, not CORE GPIO.
- Do not put policy here. Policy lives in command/safety/power; bridge only adapts.

### Testing Requirements

Host pytest does not import this file (optional ROS). CI boot smoke + SaveMap guard.

### Common Patterns

`frame_prefix` on TF frames. Hash map files for `map_id` (D-13).

## Dependencies

### Internal

- `CommandManager`, `NavigationManager`, `DiagnosticsCollector`, `power.battery.resolve_led`

### External

- rclpy, nav2_msgs, tf2_ros, slam_toolbox (optional), rosy_interfaces.SetLed

<!-- MANUAL: -->
