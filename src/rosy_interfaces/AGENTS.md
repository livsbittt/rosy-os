<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_interfaces

## Purpose

Custom ROS 2 services for LED, lamp, brightness, and LCD emotion. rosidl package; rebuild after any `.srv` change.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | `rosidl_default_generators`; member of `rosidl_interface_packages` |
| `CMakeLists.txt` | Generates interfaces from `srv/` |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `srv/` | `Emotion.srv`, `SetLed.srv`, `SetBrightness.srv`, `SetLamp.srv` (see `srv/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- REST/Fleet contracts do **not** live here — those are pydantic in `rosy_core.protocol.schemas`.
- After editing `.srv`, `colcon build --packages-select rosy_interfaces` and rebuild dependents.

### Testing Requirements

ament_lint. Compile is the real check.

### Common Patterns

Simple request/response strings and RGB fields; keep them stable for hardware nodes.

## Dependencies

### Internal

- Used by `rosy_led`, `rosy_emotion`, `rosy_lamp_control`, `rosy_core` (SetLed)

### External

- std_msgs, action_msgs, builtin_interfaces, rosidl

<!-- MANUAL: -->
