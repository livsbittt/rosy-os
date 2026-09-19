<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# workflows

## Purpose

CI job definitions for this repository.

## Key Files

| File | Description |
|------|-------------|
| `ci.yml` | `ci` workflow: colcon build, flake8 (max 120, non-gating), pytest `src/rosy_core/test`, `src/rosy_fleet/test`, `src/rosy_gz_sim/test`, repo `test/`, `rosy_core` boot smoke, slam_toolbox SaveMap type guard — still on pre-regroup `rosy_*` paths; pending realignment to the domain tree (executable is now `core`) |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Triggers: push to `main`, all pull requests.
- Boot smoke: `timeout 60 ros2 run rosy_core rosy_core`; must log `rosy_core up` **and** `slam_toolbox unavailable`. (Legacy names — the package/executable is now `core`; fix this step when ci.yml is realigned.)
- SaveMap guard unpacks the slam_toolbox deb and asserts `SaveMap.Request.name` is `std_msgs/String` and `RESULT_SUCCESS == 0`.
- pip installs: flake8, pydantic, fastapi, uvicorn, httpx, websockets, pyyaml.

### Testing Requirements

Edit `ci.yml` only with a matching local command. Do not drop the root `test/` step.

### Common Patterns

`set -eo pipefail` after sourcing ROS setup (setup.sh is not `-u` safe).

## Dependencies

### Internal

- `src/`, `src/core/core/test/` (legacy `src/rosy_core/test/`), `src/site/fleet/test/`, `src/sim/gz_sim/test/`, `test/`

### External

- `ros:jazzy-ros-base`, apt colcon + openssl

<!-- MANUAL: -->
