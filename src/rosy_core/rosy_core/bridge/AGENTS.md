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
| `translate.py` | ROS-free message → domain dict conversion. Imports no ROS type, so host pytest runs it |
| `goal_tracker.py` | ROS-free Nav2 goal generations: which result is current, what to cancel |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- `SaveMap` name field is `std_msgs/String`, success code 0. Wrong types SIGABRT — CI guards this.
- Topics: `cmd_vel` out; `nav_cmd_vel` in from Nav2; `battery/voltage`; `us_sensor/range`; `batt_state`.
- LED and LiDAR start/stop are services, not CORE GPIO.
- Do not put policy here. Policy lives in command/safety/power; bridge only adapts.
- More than one Nav2 goal can be in flight (SWM-001 moving goal). Route every acceptance, result and cancel through `GoalTracker`: a preempted goal's late abort must not be read as the current goal's failure, and a cancel must reach every live handle.
- `_setup_diagnostics` registers exactly `{rosy_core, cpu, memory, disk, odom_topic}`. That set is the baseline any
  refactor of this file must reproduce — compare `GET /api/v1/diagnostics` key-for-key, not for non-emptiness. A dropped
  provider shows up as a missing key, never as an error.
- Message → dict conversion belongs in `translate.py`, not in a callback. A callback should read one line: translate, then hand the result to a service. Anything computed inline in `ros_bridge.py` cannot be tested on the host, and the source-grep tests that stand in for it pass on wrong values.

### Testing Requirements

Host pytest does not import `ros_bridge.py` (optional ROS): CI boot smoke + SaveMap guard cover it.
`translate.py` and `goal_tracker.py` are host-testable and have real value assertions in `test/test_bridge_translate.py` and `test/test_goal_tracker.py` — duck-typed `SimpleNamespace` messages, no rclpy.

### Common Patterns

`frame_prefix` on TF frames. Hash map files for `map_id` (D-13).

## Dependencies

### Internal

- `CommandManager`, `NavigationManager`, `DiagnosticsCollector`, `power.battery.resolve_led`

### External

- rclpy, nav2_msgs, tf2_ros, slam_toolbox (optional), rosy_interfaces.SetLed

<!-- MANUAL: -->
