<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# scripts

## Purpose

Legacy Flask Nav2 web UI (`nav2_web_server.py`, ~pre-D-3). Do not add features. Parity target is `rosy_core` FastAPI.

## Key Files

| File | Description |
|------|-------------|
| `nav2_web_server.py` | Flask server: goal, costmap, initial pose, cancel |
| `index.html` | Legacy UI |
| `pinklab_logo.png` | Logo asset |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Implementation Plan P0-7 / Flask parity checklist tracks remaining gaps.
- New endpoints go to `src/rosy_core/rosy_core/api/v1/routes.py`.

### Testing Requirements

Do not add pytest here. Cover behavior in `src/rosy_core/test/test_api.py`.

### Common Patterns

Flask + rclpy in one process (historical; CORE replaced this with FastAPI).

## Dependencies

### Internal

- Not launched. `web_nav2.launch.xml` / `web_slam.launch.xml` start `rosy_core` (D-3).

### External

- Flask, rclpy, nav2_msgs

<!-- MANUAL: -->
