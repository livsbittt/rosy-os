<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_lamp_control

## Purpose

C++ WS2811 lamp driver (`rosy_lamp_control`): 8 LEDs on GPIO 19 / DMA 10, `SetLamp` service, `ColorRGBA` subscription. Gazebo counterpart is `rosy_gz_sim/plugins/gz_lamp_control_plugin.cpp`.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_cmake; rclcpp, rosy_interfaces |
| `CMakeLists.txt` | Builds `src/main_node.cpp` **only on aarch64** (ws2811); x86 does not link the node |
| `README.md` | Upstream lamp notes |
| `progress.md` | Current gate snapshot (SOURCE…FIELD). Overwrite; state of record over this file |
| `logs.md` | Append-only work journal, one entry per change |
| `index.md` | Generated: ADRs, plans, solutions, tests, recent logs. Do not edit |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | `main_node.cpp` (see `src/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Harness (D-61 Proposed): read `progress.md` and `index.md` first. After a change, append `logs.md`, overwrite `progress.md` if a gate moved, then run `python tools/harness/rosy_harness.py generate` from the repo root.
- Strip type `WS2811_STRIP_GBR`, 8 pixels. Changing count/GPIO is a hardware contract.
- Needs rpi_ws281x (`ws2811.h`); will not run on a desktop without that stack.

### Testing Requirements

ament_lint. Hardware or Gazebo plugin for visual check.

### Common Patterns

Service + topic dual control; init failure is logged from `ws2811_init`.

## Dependencies

### Internal

- `rosy_interfaces/SetLamp`
- Sim plugin in `rosy_gz_sim/plugins/`

### External

- rclcpp, rpi_ws281x

<!-- MANUAL: -->
