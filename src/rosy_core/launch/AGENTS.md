<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# launch

## Purpose

Launch file for the `rosy_core` node.

## Key Files

| File | Description |
|------|-------------|
| `rosy_core.launch.py` | Declares `config` and `mode` (`nav`/`slam`); runs executable `rosy_core` |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

```bash
ros2 launch rosy_core rosy_core.launch.py
```

On Pi, compose runs `ros2 run rosy_core rosy_core` with `__ns` instead of this launch. Keep both equivalent regarding node name.

### Testing Requirements

CI boot smoke uses `ros2 run`, not this launch.

### Common Patterns

`get_package_share_directory("rosy_core")` for default YAML.

## Dependencies

### Internal

- `rosy_core.main:main`

### External

- launch, launch_ros

<!-- MANUAL: -->
