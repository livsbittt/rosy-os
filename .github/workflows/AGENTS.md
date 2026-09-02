<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# workflows

## Purpose

CI job definitions for this repository.

## Key Files

| File | Description |
|------|-------------|
| `ci.yml` | `ci` workflow: colcon build, flake8 (max 120, non-gating), pytest `src/rosy_core/test` and repo `test/`, rosy_core boot smoke, slam_toolbox SaveMap type guard |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Triggers: push to `main`, all pull requests.
- Boot smoke: `timeout 60 ros2 run rosy_core rosy_core`; must log `rosy_core up` **and** `slam_toolbox unavailable`.
- SaveMap guard unpacks the slam_toolbox deb and asserts `SaveMap.Request.name` is `std_msgs/String` and `RESULT_SUCCESS == 0`.
- pip installs: flake8, pydantic, fastapi, uvicorn, httpx, websockets, pyyaml.

### Testing Requirements

Edit `ci.yml` only with a matching local command. Do not drop the root `test/` step.

### Common Patterns

`set -eo pipefail` after sourcing ROS setup (setup.sh is not `-u` safe).

## Dependencies

### Internal

- `src/`, `src/rosy_core/test/`, `test/`

### External

- `ros:jazzy-ros-base`, apt colcon + openssl

<!-- MANUAL: -->
