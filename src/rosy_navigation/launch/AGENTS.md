<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# launch

## Purpose

XML launches for Nav2, SLAM, localization, and Gazebo/web variants.

## Key Files

| File | Description |
|------|-------------|
| `bringup_launch.xml` | Real-robot Nav2 bringup |
| `navigation_launch.xml` | Navigation stack |
| `localization_launch.xml` | AMCL localization |
| `map_building.launch.xml` / `map_view.launch.xml` | SLAM mapping |
| `nav2_view.launch.xml` | RViz nav view |
| `gz_bringup_launch.xml` / `gz_map_building.launch.xml` / `gz_map_view.launch.xml` / `gz_nav2_view.launch.xml` / `gz_web_nav2.launch.xml` / `gz_web_slam.launch.xml` | Gazebo counterparts |
| `web_nav2.launch.xml` / `web_slam.launch.xml` | Nav2/SLAM + `rosy_core` FastAPI (Flask node removed, D-3) |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Prefer `rosy_core` + `gz_multi.launch.py` over `web_*.xml` for new work (D-3).
- When including from `gz_multi`, preserve namespace.

### Testing Requirements

Launch-level only.

### Common Patterns

XML `include` of nav2_bringup with param files from `../params`.

## Dependencies

### Internal

- `../params`, `../map`, `../rviz`, `../scripts`

### External

- Nav2, slam_toolbox

<!-- MANUAL: -->
