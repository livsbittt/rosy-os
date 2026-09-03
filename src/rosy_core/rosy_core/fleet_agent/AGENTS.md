<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-03 -->

# fleet_agent

## Purpose

Outbound Fleet WebSocket (D-5) is **disabled**. `FleetAgent.start()` does not open a socket. This repository has no Fleet server. The robot stays local-first.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker |
| `agent.py` | `FleetAgent`: `enabled`/`connected` stay false |

## For AI Agents

- Do not add a connection, URL, token, or heartbeat here until a Fleet server exists.
- Teleop, navigation, and safety must not import or wait on this agent.
- Commissioning reports `fleet_hold: true`. Robot overlay `swarm.follow` / `swarm.lead` stay false.

### Testing Requirements

`src/rosy_core/test/test_fleet_agent.py`, commissioning fields in `test_host_cards.py`.
