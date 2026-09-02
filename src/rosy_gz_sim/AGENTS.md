<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# rosy_gz_sim

## Purpose

Gazebo simulation: worlds, models, ros_gz bridge params, lamp plugin, and `gz_multi.launch.py` for N namespaced robots (`rosy_01` …).

## Key Files

| File | Description |
|------|-------------|
| `package.xml` | ament_cmake; ros_gz, gz_ros2_control |
| `CMakeLists.txt` | Installs launch, worlds, models, params, plugins. **`return()` on aarch64** — do not "fix" that skip |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `launch/` | `gz_multi.launch.py`, `launch_sim.launch.xml` (see `launch/AGENTS.md`) |
| `worlds/` | `rosy_factory.world`, `rosy_map.world`, `empty.world`, `default.sdf` (see `worlds/AGENTS.md`) |
| `models/` | Robot/shelf meshes and SDF (see `models/AGENTS.md`) |
| `params/` | `rosy_bridge.yaml` ros_gz topic maps |
| `plugins/` | `gz_lamp_control_plugin.cpp/.hpp` |

## For AI Agents

### Working In This Directory

```bash
ros2 launch rosy_gz_sim gz_multi.launch.py robots:=2
ros2 launch rosy_gz_sim gz_multi.launch.py robots:=3 mode:=slam headless:=true
```

- One Gazebo server; per-robot RSP, spawn, and ros_gz bridge with namespaced `cmd_vel`.
- Do not assume mapper `scan_topic` is namespaced — override per robot if needed.
- `CMakeLists.txt` exits on aarch64. Pi images do not ship Gazebo.

### Testing Requirements

Launch-level. CI flake8 includes `rosy_gz_sim/launch`.

### Common Patterns

`PushRosNamespace` + `frame_prefix`. Mode `nav` vs `slam`.

## Dependencies

### Internal

- `rosy_description`, `rosy_navigation` launches

### External

- Gazebo / ros_gz, gz_ros2_control

<!-- MANUAL: -->
