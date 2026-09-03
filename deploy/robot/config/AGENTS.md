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
| `profile.hardware.yaml` / `capabilities.hardware.yaml` | Motor + RPLidar + Nav2 goal/return-home; slam still false |
| `board.yaml` | Catalog of modes and aliases (`pi5-lite` → `hardware`) |
| `resolve-mode.sh` | Maps aliases to catalog modes; overlay YAML exists only for catalog modes |
| `rosy.pi5.example.yaml` | Example `ROSY_CONFIG` for the device |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Compose bind-mounts profile/capabilities over `/etc/rosy/`. Keep keys aligned with `src/rosy_core/config/` schemas.
- Overlay YAML exists only for `core` / `motor` / `hardware`. Do not copy YAML for aliases.
- Do not enable slam/swarm here unless the hardware image actually launches those stacks. `hardware` may advertise Nav2 only because `hardware.launch.py` starts it.

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
