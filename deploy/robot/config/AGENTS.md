<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# config

## Purpose

Pinky Pro board overlays mounted into `rosy-core`. `ROSY_RUNTIME_MODE` selects `core`, `motor`, or `hardware`. The full in-tree `src/rosy_core/config/capabilities.yaml` is the Pinky source profile; these files are what the robot actually advertises.

## Key Files

| File | Description |
|------|-------------|
| `profile.core.yaml` / `capabilities.core.yaml` | Dashboard only: no teleop, no lidar |
| `profile.motor.yaml` / `capabilities.motor.yaml` | Dynamixel teleop, encoder only |
| `profile.hardware.yaml` / `capabilities.hardware.yaml` | Motor + RPLidar; nav/slam still false |
| `profile.pi5-lite.yaml` / `capabilities.pi5-lite.yaml` | Alias of the hardware overlay |
| `board.yaml` | Catalog of modes, overlay files, and the pi5-lite alias |
| `rosy.pi5.example.yaml` | Example `ROSY_CONFIG` for the device |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Compose bind-mounts profile/capabilities over `/etc/rosy/`. Keep keys aligned with `src/rosy_core/config/` schemas.
- Do not enable slam/nav/swarm here unless the hardware image actually contains those stacks.

### Testing Requirements

Covered by `test/test_robot_runtime.py` and `src/rosy_core/test/test_runtime_config.py`.

### Common Patterns

YAML only; no code.

## Dependencies

### Internal

- `src/rosy_core/config/rosy_default.yaml` structure
- `deploy/robot/compose.yaml` volume mounts

### External

None.

<!-- MANUAL: -->
