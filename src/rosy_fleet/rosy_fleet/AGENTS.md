<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-14 | Updated: 2026-09-14 -->

# rosy_fleet (Python package)

## Purpose

Python package root for the fleet seed: operator CLI plus `formation/` (pure geometry/assignment) and `swarm/` (transport, relay, session). No ROS imports. No Fleet server.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `cli.py` | `rosy_fleet relay` / `rosy_fleet formation`; stdin `reform` / `resume` / `status` / `stop`; SIGINT calls `stop()` |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `formation/` | Pure FOR-001/002 geometry and slot assignment (see `formation/AGENTS.md`) |
| `swarm/` | Endpoints, HTTP/WS transport, relay, arming, FOR-004 session (see `swarm/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- CLI must not leave followers armed on SIGINT — `stop()` tears the session down.
- Do not import `rclpy` here. `test/test_boundaries.py` walks the import graph.
- Never modify `rosy_core` from this package. Missing robot-contract fields are an API Ref finding.

### Testing Requirements

```bash
python -m pytest src/rosy_fleet/test -v
```

### Common Patterns

`cli.py` constructs `HttpRobotClient` + `FormationSession` from `robots.yaml`. Logic stays in `formation/` and `swarm/`.

## Dependencies

### Internal

- `rosy_core.protocol.schemas` (schema reuse only, D-18)

### External

- httpx, websockets, PyYAML (via swarm/CLI)

<!-- MANUAL: -->
