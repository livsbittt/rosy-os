<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# config

## Purpose

Pi 5 lite overlays mounted into `rosy-core`. These replace the full Pinky Pro profile/capabilities when running the lite image.

## Key Files

| File | Description |
|------|-------------|
| `profile.pi5-lite.yaml` | Hardware profile for Pi 5 lite (kinematics, model) |
| `capabilities.pi5-lite.yaml` | CAP-001 flags: `slam: false`, `goal_navigation: false`, `swarm.follow/lead: false` |
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
