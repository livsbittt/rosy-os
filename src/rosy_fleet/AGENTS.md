<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-09 | Updated: 2026-09-09 -->

# rosy_fleet

## Purpose

Fleet-side seed (ROSY-FLEET-SRS-001 FOR-001~004). Formation geometry (FOR-001), slot
assignment (FOR-002), a reference-stream relay from one leader to N followers (D-31), and
the FOR-004 formation session (arm → relay → watch → hold), plus the CLI that opens a
session until the Fleet server exists (Phase 4). No Fleet server yet. Consumes the robot
contract only — it never modifies `rosy_core` — and imports `rosy_core.protocol.schemas`
for schema reuse (D-18). No ROS imports anywhere in this package.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_python; `rosy_core` is an `exec_depend` for colcon build order only — this package's code has no ROS import (D-18) |
| `setup.py` | Console script `rosy_fleet=rosy_fleet.cli:main` |
| `rosy_fleet/formation/geometry.py` | `Formation`, `SlotOffset`, `slots()` — FOR-001, pure functions |
| `rosy_fleet/formation/assignment.py` | `SlotAssigner` protocol, `GreedyDistanceAssigner` — FOR-002, pure functions |
| `rosy_fleet/swarm/robots.py` | `RobotEndpoint`, `load_robots()` / `write_robots()` for `robots.yaml` (per-robot token, D-30) |
| `rosy_fleet/swarm/transport.py` | `RobotClient` protocol and `HttpRobotClient` (httpx + websockets) — the only place that calls the robot contract |
| `rosy_fleet/swarm/relay.py` | `Relay`: leader pose socket 1 → follower reference sockets N, byte-for-byte fan-out (D-31) |
| `rosy_fleet/swarm/arming.py` | `FormationSpec` + pure pre-check/assignment planning, finished before the relay is touched |
| `rosy_fleet/swarm/session.py` | `FormationSession`: arm → relay → watch → FOR-004 (HOLD/ABORT policy) |
| `rosy_fleet/cli.py` | `rosy_fleet relay ...` / `rosy_fleet formation ...` |
| `test/fakes.py` | Fake `RobotClient` + `FakeClock` shared by relay/session tests — no network |
| `test/conftest.py` | Puts `src/rosy_fleet` and `src/rosy_core` on `sys.path` so pytest runs without colcon install |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `rosy_fleet/formation/` | Pure geometry and slot-assignment functions — no transport, no ROS |
| `rosy_fleet/swarm/` | Robot endpoints, transport, relay, arming, and the formation session |
| `test/` | pytest for geometry, assignment, robots, transport, relay, arming, session, CLI, and the import-boundary check |
| `resource/` | ament index marker `rosy_fleet` |

## For AI Agents

### Working In This Directory

- `formation/` and `swarm/arming.py` are pure — no `httpx`, `websockets`, `asyncio`, or `rclpy` imports. `test/test_boundaries.py` enforces this by walking the import graph.
- The relay forwards leader frames byte-for-byte and never synthesizes one. A stream that stops must read 0 Hz, not repeat the last frame.
- HOLD (FOR-004's whole-formation hold) is made by pausing the relay, not by a new endpoint (design §6.4, D-35 candidate).
- Everything that can be refused without touching a robot is decided in `arming.py` before `relay.pause()` is called — a rejected `reform` must leave a running formation exactly as it was.
- Never modify `rosy_core` from here. If the robot contract is missing something this package needs, that is a finding for an API Ref cycle, not a local patch.
- Tests use fakes (`test/fakes.py`) and `settle()`-style polling, never wall-clock `sleep`.

### Testing Requirements

```bash
python -m pytest src/rosy_fleet/test -v
python -m flake8 src/rosy_fleet --max-line-length=120
```

No ROS required — `conftest.py` puts `src/rosy_core` on `sys.path` for the schema import.

### Common Patterns

- `robot_id → RobotEndpoint(base_url, token)` loaded from `robots.yaml`; tokens are device-local (D-30).
- `SlotAssigner` is a `Protocol` so the greedy v1 assigner can be swapped for a Hungarian one without touching callers (FOR-002).
- `FormationSession` state machine: `RUNNING` / `HOLDING` / `STOPPED`; `pending_triggers` accumulate while holding and block `resume()` until cleared.

## Dependencies

### Internal

- `rosy_core` — schema reuse only (`rosy_core.protocol.schemas`, D-18); colcon build order via `exec_depend`

### External

- httpx
- websockets ≥13
- PyYAML
- pydantic

<!-- MANUAL: -->
