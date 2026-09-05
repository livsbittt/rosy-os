<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# navigation

## Purpose

NAV-001–004/006 facade. ROS-free. Nav2 action client lives behind `NavExecutor` (implemented by `RosBridge`).

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `manager.py` | `NavigationManager`, `NavGoalSpec`, `NavExecutor` protocol, `NavigationError` |
| `initial_pose.py` | AMCL covariance for `/initialpose` (zero covariance is ignored) |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- `save_map` returns `map_id` (filename + checksum, D-13). Bridge computes the hash.
- Stuck timeout is SAF/NAV-006 — honor `stuck_timeout_s` from config.

### Testing Requirements

`test_core_logic.py`, `test_sprint2.py`

### Common Patterns

Goals in `map` frame with x, y, yaw.

## Dependencies

### Internal

- `protocol.schemas.NavigationState`
- Executor: `bridge.ros_bridge`

### External

None (in this package).

<!-- MANUAL: -->
