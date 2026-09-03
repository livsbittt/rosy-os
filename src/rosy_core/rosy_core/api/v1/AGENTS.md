<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# v1

## Purpose

REST routers under `/api/v1/*` (API Ref §5). One module: `routes.py`.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `routes.py` | Routers: system, robot, control, safety, navigation, waypoints, events, logs, power, sensors, slam, docking, metrics, host |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Prefixes are the contract. Do not rename `/api/v1/robot/state` etc. without API ref + tests.
- Map snapshots: `GET /api/v1/map`, `/navigation/path`, `/map/costmap?scope=global|local`. Missing grid is 404; empty path is `[]`.
- `POST /mode` allows IDLE|MANUAL|NAVIGATION only (not DOCKING/EMERGENCY via this body).
- Host card endpoints proxy Host Agent; never fabricate telemetry (`host_agent_client`).
- Docking and battery routes were extended on `feat/battery-integrity-low-battery-alert`.

### Testing Requirements

`python3 -m pytest src/rosy_core/test/test_api.py -v`

### Common Patterns

`Depends(viewer|operator|admin)` + `get_services`. Return pydantic `model_dump()`.

## Dependencies

### Internal

- `api.deps`, `command.arbitration.Mode`, docking DB types, `HostAgentClient`

### External

- FastAPI, pydantic

<!-- MANUAL: -->
