<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# deploy

## Purpose

Older single-unit install helpers for rosy_core. Current Pi runtime is `deploy/robot/` at repo root (compose + `rosy-runtime.service`). Keep this folder consistent or delete only with an ADR; do not add new production units here.

## Key Files

| File | Description |
|------|-------------|
| `install.sh` | Legacy install helper |
| `rosy-core.service` | systemd unit that runs rosy_core directly |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Prefer `F:\Dev\Control\Robot\ROS\Rosy\deploy\robot` for runtime changes.
- If you must edit this unit, keep ExecStart as `ros2 run rosy_core rosy_core` and do not grant it host privileges.

### Testing Requirements

Boundary tests target repo `deploy/robot` and Host Agent, not this folder.

### Common Patterns

Simple systemd + bash.

## Dependencies

### Internal

- `rosy_core` executable

### External

- systemd

<!-- MANUAL: -->
