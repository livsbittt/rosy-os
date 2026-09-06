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
| `display.py` | ROS-free `display/info` decisions: address resolution and payload rounding (PWR-003) |
| `reconcile.py` | ROS-free change-detection latch. LED latches on a skipped call, LiDAR does not |
| `odometry.py` | ROS-free `travelled_m` — the only measure undocking has |
| `battery_policy.py` | ROS-free SAF-005/DNC-006 chain: what one voltage reading sets in motion, in order |
| `save_map.py` | ROS-free SaveMap reply handling: `RESULT_SUCCESS = 0` (truthiness inverts it) and the D-13 map id |

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
One exception, deliberately narrow — `test/test_bridge_timers.py` stubs `rclpy` in `sys.modules` to build
the bridge against a recording node and assert **what it registers**: six timers at fixed periods, eleven
subscriptions, five publishers, three service clients. Structural only. It exists so the 3b adapter reshape
is gradable without a robot. Do not add semantic tests there and do not move the stub into `conftest.py` —
a stub asserts stub semantics, and its blast radius is meant to stay one file.
The ROS-free siblings are host-testable and carry real value assertions — `translate.py` (`test_bridge_translate.py`), `goal_tracker.py` (`test_goal_tracker.py`), `display.py` (`test_bridge_display.py`), `reconcile.py` (`test_bridge_reconcile.py`), `odometry.py` (`test_bridge_odometry.py`), `save_map.py` (`test_bridge_save_map.py`), `battery_policy.py` (`test_bridge_battery_policy.py`). Duck-typed `SimpleNamespace` inputs, no rclpy. Extract a decision here rather than leaving it inline: this file is the one place host pytest cannot reach.

### Common Patterns

`frame_prefix` on TF frames. Hash map files for `map_id` (D-13).

## Dependencies

### Internal

- `CommandManager`, `NavigationManager`, `DiagnosticsCollector`, `power.battery.resolve_led`

### External

- rclpy, nav2_msgs, tf2_ros, slam_toolbox (optional), rosy_interfaces.SetLed

<!-- MANUAL: -->
