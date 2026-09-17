# rosy_games

Laptop game host (D-90). CORE does not import this package. Final `cmd_vel` stays in CORE.

`field` / `game` / `policy` must not import `cv2`, `httpx`, `rclpy`, `rosy_core`, or `rosy_fleet`. OpenCV belongs only in `host/overhead.py` (not created; LOCAL closed without a camera). `host/loop.py` and `host/transport.py` must not import `cv2`. Do not add `isaac/`, `host/overhead.py`, or `field/homography.py` until a camera plan.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_python. No ROS exec_depend |
| `setup.py` / `setup.cfg` | Package install |
| `progress.md` | Current gate snapshot (SOURCE…FIELD). Overwrite; state of record over this file |
| `logs.md` | Append-only work journal, one entry per change |
| `index.md` | Generated: ADRs, plans, solutions, tests, recent logs. Do not edit |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `rosy_games/field/` | Pitch numbers. No camera, no HTTP |
| `rosy_games/game/` | Referee. No policy HTTP |
| `rosy_games/policy/` | Heuristic now, neural later |
| `rosy_games/host/` | Match loop and CORE teleop client. No `overhead.py` yet |
| `test/` | ROS-free pytest |

## For AI Agents

### Working In This Directory

- Harness (D-61): read `progress.md` and `index.md` first. After a change, append `logs.md`, overwrite `progress.md` if a gate moved, then run `python tools/harness/rosy_harness.py generate` from the repo root.
- LOCAL host is closed without overhead: `docs/plans/2026-09-18-rosy-games-local-host.md`. Design: `docs/plans/2026-09-17-robot-soccer-game-host-design.md`. Next plan owns the ceiling camera.

### Testing Requirements

```bash
python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q
```
