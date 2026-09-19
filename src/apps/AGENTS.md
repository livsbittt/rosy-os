<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-20 | Updated: 2026-09-20 -->

# apps

## Purpose

Application layer on top of CORE: the absorbed Control package (`control`), device personality (`emotion`), the laptop game host (`games`, D-90), and the disabled-by-default ros2_control/MoveIt contract boundary (`omx_adapter`).

## Key Files

None at this level. Each package directory has its own `AGENTS.md`.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `control/` | Absorbed Control: sensing, camera/OpenCV, calibration, planning, safety-policy; legacy final publisher must not run beside `core` (see `control/AGENTS.md`) |
| `emotion/` | LCD GIF emotions + info-screen renderer (see `emotion/AGENTS.md`) |
| `games/` | Laptop game host (D-90). Not a CORE slice — no ROS, no `cmd_vel` (see `games/AGENTS.md`) |
| `omx_adapter/` | OMX model profile + ROS-native ros2_control/MoveIt contract boundary, disabled by default (see `omx_adapter/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- `games` and `omx_adapter` must keep working without a ROS overlay (host pytest on Windows).
- `control` produces sensor evidence; the operational final command stays owned by `core`.

### Testing Requirements

```bash
# from src/
python3 -m pytest apps/control/test/ apps/omx_adapter/test/ apps/games/test apps/emotion/test -q
```

## Dependencies

### Internal

- `control` has no declared dependency on `core`; `core/core/core/bridge/` imports `control` through the opt-in sensor adapter (`control_sensor_adapter.py`).

### External

- ROS 2 Jazzy (control, emotion), httpx/websockets/yaml (games, omx_adapter), numpy/OpenCV (control)

<!-- MANUAL: -->
