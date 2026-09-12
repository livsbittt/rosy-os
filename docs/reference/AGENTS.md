<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# reference

## Purpose

Shared contracts: REST/WS/protocol, architecture decisions, and the Host Agent unix-socket API. Changing these without code (or vice versa) is a defect.

## Key Files

| File | Description |
|------|-------------|
| `ROSY API & Protocol Reference.md` | ROSY-API-REF-001 — only shared robot/fleet/SDK interface; `/api/v1`, envelope, events |
| `ROSY ADR Log.md` | ROSY-ADR-001 — append-only decisions through D-45 (D-19 superseded by D-26, D-6 by D-33; D-29 is an unused gap) |
| `rosy-host-agent-contract.md` | ROSY-HOSTAGENT-001 — `/run/rosy/host-agent.sock`, no arbitrary shell |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Schema source of truth for Python is still `rosy_core.protocol.schemas` (D-18); this API ref is the human contract.
- Host Agent: CORE client is `rosy_core.system.host_agent_client`; server is `deploy/release/host_agent.py`.
- Important ADRs: D-1 single process, D-2 cmd_vel mux, D-3 FastAPI replaces Flask, D-8 in-process event bus, D-22 Core/IO split + deadman, D-23 embedded dashboard, D-24/D-25 power (STANDBY not hibernate), D-27 deep-battery halt exception, D-33 robot identity from one robot number (supersedes D-6), D-34 publish rates matched to the consumer.

### Testing Requirements

Protocol tests: `src/rosy_core/test/test_protocol_schemas.py`. Host Agent: `test/test_host_agent.py`.

### Common Patterns

API versioning is path-based (`/api/v1`). Additive schema changes bump protocol MINOR (PRT-006).

## Dependencies

### Internal

- `src/rosy_core/rosy_core/protocol/schemas.py`
- `src/rosy_core/rosy_core/api/`
- `deploy/release/host_agent.py`

### External

None.

<!-- MANUAL: -->
