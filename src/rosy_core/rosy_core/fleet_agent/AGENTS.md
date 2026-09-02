<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# fleet_agent

## Purpose

Placeholder for Phase 4 outbound Fleet WebSocket (D-5): hello/welcome, heartbeat, backoff, gap fill. **Not implemented** — `agent.py` is a TODO stub.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `agent.py` | Stub documenting P4-2 / D-5 |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Do not pretend this speaks to a fleet server. Implement against API ref §7 and `protocol/schemas.py`.
- Robot remains local-first: this agent must not be required for teleop/nav/safety.

### Testing Requirements

None until the stub grows. Protocol tests already cover envelope types.

### Common Patterns

Outbound WS from robot; Fleet sends commands over REST (D-5).

## Dependencies

### Internal

- `protocol.schemas` envelope types

### External

- websockets (future)

<!-- MANUAL: -->
