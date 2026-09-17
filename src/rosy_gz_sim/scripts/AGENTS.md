<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-14 | Updated: 2026-09-14 -->

# scripts

## Purpose

Host-side swarm formation bench. Uses `rosy_fleet` over the robot HTTP/WS contract. No `rclpy`. Not installed as a ROS node.

## Key Files

| File | Description |
|------|-------------|
| `swarm_bench.py` | Async bench: `follow` / `reform` / `hold` / `stuck` scenarios; CSV of slot error, stream age, relay Hz |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- The measurement loop must not block. A blocking call stalls the relay and can cause a HOLD that the scenario did not request.
- Design: `docs/plans/2026-09-08-swarm-formation-slice-design.md` §8.2.
- `BLOCKED` is not a terminal nav state for sending the next waypoint.

### Testing Requirements

Not in host pytest. Package launch contracts are in `../test/`.

### Common Patterns

asyncio throughout. Writes CSV; does not synthesize relay frames.

## Dependencies

### Internal

- `rosy_fleet.formation.geometry`, `rosy_fleet.swarm.{robots,session,transport}`

### External

- Gazebo spawn for the `stuck` obstacle SDF; httpx/websockets via fleet transport

<!-- MANUAL: -->
