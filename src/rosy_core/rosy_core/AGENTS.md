<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_core (Python package)

## Purpose

Importable middleware. `main.py` starts rclpy; `node.py` builds `CoreServices`, `RosBridge`, `RosGraphMonitor`, and the API thread. Subpackages are the feature managers.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `main.py` | Entry: `rclpy.init` → `RosyCoreNode.run` → shutdown |
| `node.py` | Assembles profile/capabilities/services, starts uvicorn thread |
| `services.py` | `CoreServices` DI; battery/power config mapping; shutdown sentinel name |
| `config.py` | YAML load/merge (`rosy_default` → `~/.rosy/rosy.yaml` → `ROSY_CONFIG`) |
| `identity.py` | IDN-001 robot id/name/IP/version |
| `profile.py` | HWA-001 `RobotProfile` loader |
| `capability.py` | CAP-001 dotted lookup + `CapabilityError` |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI app, auth, REST, WS (see `api/AGENTS.md`) |
| `web/` | Dashboard HTML/CSS/JS (see `web/AGENTS.md`) |
| `bridge/` | All ROS I/O (see `bridge/AGENTS.md`) |
| `command/` | Mode machine + cmd_vel mux (see `command/AGENTS.md`) |
| `safety/` | E-stop, speed limits, battery policy (see `safety/AGENTS.md`) |
| `state/` | 10 Hz snapshot (see `state/AGENTS.md`) |
| `events/` | In-process event bus (see `events/AGENTS.md`) |
| `protocol/` | Pydantic fleet/API schemas (see `protocol/AGENTS.md`) |
| `navigation/` | Nav facade; Nav2 behind protocol (see `navigation/AGENTS.md`) |
| `waypoints/` | JSON waypoint store (see `waypoints/AGENTS.md`) |
| `power/` | IDLE/STANDBY + battery monitor (see `power/AGENTS.md`) |
| `docking/` | Dock SM, DB, detector (see `docking/AGENTS.md`) |
| `diagnostics/` | Health providers (see `diagnostics/AGENTS.md`) |
| `system/` | Host probe, ROS graph, host-agent client (see `system/AGENTS.md`) |
| `fleet_agent/` | Outbound Fleet WS stub (Phase 4) (see `fleet_agent/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- `SOFTWARE_VERSION` is `"0.1.0"` in `node.py` / `identity.py` — keep in sync with `package.xml`.
- Waypoints default path: `~/.rosy/waypoints.json` (on Pi, `HOME=/var/lib/rosy`).
- `SHUTDOWN_SENTINEL_NAME = "battery-shutdown-request.json"` in `services.py`. Dock database JSON lives beside waypoints.

### Testing Requirements

See sibling `../test/AGENTS.md`.

### Common Patterns

Managers take an injected clock. Events via `EventBus.publish(type, source, data)`.

## Dependencies

### Internal

- Subpackages listed above; assembled only in `node.py` / `services.py`

### External

- rclpy (node/main/bridge only), yaml, fastapi/uvicorn (api thread)

<!-- MANUAL: -->
