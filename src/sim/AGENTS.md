<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-20 | Updated: 2026-09-20 -->

# sim

## Purpose

Simulation assets and launches: URDF/xacro description and Gazebo worlds with multi-robot launch (`gz_multi.launch.py`). `gz_sim` CMake no-ops on aarch64.

## Key Files

None at this level. Each package directory has its own `AGENTS.md`.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `description/` | URDF/xacro, meshes, RViz view (see `description/AGENTS.md`) |
| `gz_sim/` | Gazebo worlds, multi-robot launch, lamp plugin, launch tests (see `gz_sim/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- `gz_sim` includes `description` and `navigation` launches.
- Multi-instance launch tests self-skip when `ros_gz_sim` share is absent (CI shows them as skip).

### Testing Requirements

```bash
# from src/ — needs a ROS overlay
python3 -m pytest sim/gz_sim/test -v
```

## Dependencies

### Internal

- `description`, `navigation`, and exec_depend on `src/site/fleet`.

### External

- gz_ros2_control, ros_gz (Gazebo)

<!-- MANUAL: -->
