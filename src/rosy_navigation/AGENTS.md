<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_navigation

## Purpose

Nav2 and SLAM Toolbox launch/config/maps for real robot and Gazebo. ament_cmake. The Flask `scripts/nav2_web_server.py` is the pre-D-3 UI; new web control belongs in `rosy_core`.

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | Depends on navigation2, nav2_bringup |
| `CMakeLists.txt` | Installs launch, params, maps, rviz, scripts |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `launch/` | XML launches: bringup, localization, slam, gz_*, web_* (see `launch/AGENTS.md`) |
| `params/` | `nav2_params.yaml`, `mapper_params.yaml` (see `params/AGENTS.md`) |
| `map/` | Occupancy maps (`my_map`, `pinklab`) (see `map/AGENTS.md`) |
| `rviz/` | map_building / nav2_view configs (see `rviz/AGENTS.md`) |
| `scripts/` | Legacy Flask nav UI (see `scripts/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Do not extend Flask. D-3: feature parity via `/api/v1/*`.
- Nav2 velocity_smoother output must be remappable to `nav_cmd_vel` so CommandManager owns `cmd_vel`.
- Watch absolute vs namespaced `scan_topic` in mapper params (noted in `gz_multi.launch.py`).

### Testing Requirements

No dedicated pytest here. Integration is launch + `rosy_core` navigation tests. ament_lint via CMake.

### Common Patterns

XML launches included from `rosy_gz_sim` with per-robot namespace.

## Dependencies

### Internal

- Used by `rosy_gz_sim/launch/gz_multi.launch.py`

### External

- Nav2, slam_toolbox, rviz2

<!-- MANUAL: -->
