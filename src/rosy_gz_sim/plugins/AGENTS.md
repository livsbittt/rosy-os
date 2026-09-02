<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# plugins

## Purpose

Gazebo plugin that mirrors `rosy_lamp_control` for sim.

## Key Files

| File | Description |
|------|-------------|
| `gz_lamp_control_plugin.hpp` | Plugin API |
| `gz_lamp_control_plugin.cpp` | Lamp control in Gazebo |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

Keep service/topic names aligned with `rosy_lamp_control` / `rosy_interfaces/SetLamp`.

### Testing Requirements

Build via ament_cmake; visual check in Gazebo.

### Common Patterns

C++ Gazebo plugin.

## Dependencies

### Internal

- `rosy_lamp_control` behavior
- `rosy_interfaces`

### External

- Gazebo / gz-sim headers

<!-- MANUAL: -->
