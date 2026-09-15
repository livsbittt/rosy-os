<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# config

## Purpose

Default robot config, Pinky Pro hardware profile, and static capability YAML. Installed to `share/rosy_core/config`. Local override is `~/.rosy/rosy.yaml` (not in this folder).

## Key Files

| File | Description |
|------|-------------|
| `rosy_default.yaml` | CFG-001 defaults: robot id, API port 8080, auth tokens, safety/battery curve, power, navigation |
| `profile.pinky_pro.yaml` | HWA-001 Pinky Pro profile (model, max velocities, geometry) |
| `capabilities.yaml` | CAP-001 advertisement for packaged `runtime.mode: core`. Must equal `derive_capability(profile, mode)` |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Auth tokens in `rosy_default.yaml` are **dev defaults** (`rosy-dev-admin` etc.). Never ship them as production secrets.
- Battery curve is 2S Li-ion OCV. Invalid `battery_curve` must not prevent boot (`services._battery_config` falls back).
- `capabilities.yaml` currently has `docking.supported: false` for Pinky Pro. Pi lite overlay may also set `slam: false`.
- New safety keys need matching fields in `BatteryConfig` / `PowerConfig` with defaults.

### Testing Requirements

`src/rosy_core/test/test_runtime_config.py`, `test_battery.py`, `test_power.py`.

### Common Patterns

Deep-merge; missing keys keep dataclass defaults. Runtime settings (SAF-004 limits) write only the overlay via `patch_local_config` — never `rosy_default.yaml`.

## Dependencies

### Internal

- Loaded by `rosy_core.config.load_config` and `RosyCoreNode`

### External

- PyYAML

<!-- MANUAL: -->
