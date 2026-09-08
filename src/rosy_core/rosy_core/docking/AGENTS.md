<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-09 -->

# docking

## Purpose

Docking state machine (DNC-002–003). Map pose is only for staging; final approach is sensor closed-loop. Whole action runs in `DOCKING` mode so Fleet/Nav cannot preempt.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `manager.py` | `DockingManager`, `DockPhase`, `DockingConfig` |
| `database.py` | `DockDatabase`, `DockInstance`, `DockType`, `DockError` |
| `detector.py` | `DockDetector` protocol + `SimulatedDetector` |
| `charging.py` | `ChargingConfirmation` (contact vs current) |
| `agent.py` | Poll client for dock `GET /status` (urllib only; required `load_present`/`charging`) |
| `profile.py` | `DockProfile`, `fit()` — three asymmetric posts in a flat scan → `base_link` pose. Every constant carries the measurement that set it; a number beside a constant that does not reproduce is a defect |
| `probe.py` | `ProbeRow` CSV schema (`append_row` / `read_rows`, `ProbeFormatError`) plus the lane-aware `verdict(rows, lane=None)` — one verdict per (candidate, lane) pair, because ruler truth and sim truth cannot share one RMS and the design's sample floors are declared per lane (`LANES`, `MIN_ABSENT`, `MIN_STAGING`) |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Design: `docs/plans/2026-09-02-docking-station-design.md`.
- `profile.py` / `probe.py` belong to the measurement rig: `docs/plans/2026-09-07-dock-detector-measurement-rig-design.md`. The two collectors that feed `probe.py` live outside this package (`src/rosy_gz_sim/scripts/dock_sweep.py` writes `lane="sim"`, `src/rosy_bringup/rosy_bringup/dock_probe.py` writes `lane="bench"`); a lane string neither recognises fails the verdict rather than being averaged in.
- Pinky Pro `capabilities.yaml` has `docking.supported: false` — keep capability checks.
- ROS-free: inject clock and detector. Do not subscribe to scans here.

### Testing Requirements

```bash
python3 -m pytest src/rosy_core/test/test_docking.py -v
```

```bash
python3 -m pytest src/rosy_core/test/test_dock_profile.py src/rosy_core/test/test_dock_probe.py -v
```

### Common Patterns

Phases inside `DOCKING`; never drive by map coordinates at the contact.

## Dependencies

### Internal

- `protocol.schemas` DockingStatus / DockState
- `services.py` builds `DockingManager` with `SimulatedDetector` by default

### External

None.

<!-- MANUAL: -->
