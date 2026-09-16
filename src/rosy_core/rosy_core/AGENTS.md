<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-15 -->

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
| `config.py` | YAML load/merge + local overlay patch (`~/.rosy/rosy.yaml` / `ROSY_CONFIG`) |
| `identity.py` | IDN-001 robot id/name/IP/version |
| `profile.py` | HWA-001 `RobotProfile` loader |
| `capability.py` | CAP-001 dotted lookup + `CapabilityError` |
| `domain/` | Concept inventory, adapter registry, TaskKind (ROS-free) |
| `maps.py` | MAP-003/004 **grid frames for the render path** — last OccupancyGrid / Path / Costmap snapshot (ROS-free). Not map artifacts: authoring and persistence are not its concern |

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
| `swarm/` | robot-side follow (see `swarm/AGENTS.md`) |
| `waypoints/` | JSON waypoint store (see `waypoints/AGENTS.md`) |
| `power/` | IDLE/STANDBY + battery monitor (see `power/AGENTS.md`) |
| `docking/` | Dock SM, DB, detector (see `docking/AGENTS.md`) |
| `diagnostics/` | Health providers (see `diagnostics/AGENTS.md`) |
| `system/` | Host probe, ROS graph, host-agent client (see `system/AGENTS.md`) |
| `fleet_agent/` | Disabled outbound Fleet WS; does not connect (see `fleet_agent/AGENTS.md`) |

## For AI Agents

### Working In This Directory

#### Split criteria — before making a module a package, or splitting a file

Full reasoning: `docs/plans/2026-09-06-module-split-criteria.md`. Operative rules:

- **Size is never a reason.** `waypoints/` is 85 lines and is a package; `docking/manager.py` is 511 and is one file.
- **Promote a module only if all three hold:** it owns a requirement family no package claims, it needs a second file with a
  different role *today* (or one is scheduled under a requirement ID), and ≥2 packages import it. One file, one role → stays.
- **Split a file only on a defect.** C1: it cannot be imported by host pytest and hides a decision → extract a ROS-free sibling
  (`bridge/translate.py`, `bridge/goal_tracker.py`). C6: a dependency reached via `hasattr`/`getattr` → declare the member;
  `test/test_module_criteria.py` fails on any new reach. C7: one service field spanning two requirement families.
- **Record the "leave it alone" verdicts too.** They are what stops the next round of churn.

- `SOFTWARE_VERSION` lives in `identity.py` and must match `package.xml`. `node.py` imports it.
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
