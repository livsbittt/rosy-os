<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_emotion

## Purpose

LCD emotion GIFs (`set_emotion` service) and PWR-003 info-card renderer (`info_screen.py`). Info-screen is ROS-free PIL so tests do not need an LCD.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_python; python3-pil, rosy_interfaces |
| `setup.py` / `setup.cfg` | Package install |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `rosy_emotion/` | Node, LCD helper, info_screen (see `rosy_emotion/AGENTS.md`) |
| `emotion/` | GIFs: hello, basic, angry, bored, fun, happy, interest, sad |
| `test/` | `test_info_screen.py` + ament linters (see `test/AGENTS.md`) |
| `resource/` | ament marker |

## For AI Agents

### Working In This Directory

- `info_screen.py` draws 320×240 landscape; LCD code rotates/resizes. Keep that contract.
- CORE publishes `display/info` JSON; this package renders it. Do not put PIL in `rosy_core`.

### Testing Requirements

```bash
python3 -m pytest src/rosy_emotion/test/test_info_screen.py -v
```

### Common Patterns

Share-dir lookup: `get_package_share_directory('rosy_emotion')/emotion`.

## Dependencies

### Internal

- `rosy_interfaces/Emotion`
- Power manager wake/info hold in `rosy_core`

### External

- PIL, rclpy, hardware LCD via `rosy_lcd.py`

<!-- MANUAL: -->
