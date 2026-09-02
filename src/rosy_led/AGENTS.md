<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_led

## Purpose

Python LED service server (`led_service_server`) wrapping `rosylib.LED`. Services `set_led` and `set_brightness` (`rosy_interfaces`).

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_python (description/license still TODO from upstream) |
| `setup.py` / `setup.cfg` | Package install |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `rosy_led/` | `led_server.py` (see `rosy_led/AGENTS.md`) |
| `test/` | ament copyright/flake8/pep257 |
| `resource/` | ament marker |

## For AI Agents

### Working In This Directory

- CORE battery/LED policy calls `set_led` through `ros_bridge`; do not drive the strip from CORE.
- `rosylib` is a hardware helper, not in this repo.

### Testing Requirements

```bash
# linters only unless hardware is present
python3 -m pytest src/rosy_led/test/ -v
```

### Common Patterns

Commands `set_pixel` and `fill` with RGB tuples.

## Dependencies

### Internal

- `rosy_interfaces` (`SetLed`, `SetBrightness`)

### External

- rclpy, rosylib

<!-- MANUAL: -->
