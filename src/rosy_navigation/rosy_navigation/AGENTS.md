<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-03 | Updated: 2026-09-03 -->

# rosy_navigation (Python)

## Purpose

Nav2 policy used by launch files: D-4 frame prefixing and the temp params rewrite. Not a ROS node.

## Key Files

| File | Description |
|------|-------------|
| `frame_prefix.py` | Prefix `odom` / `base_*` TF frames; leave `map` global |
| `params_rewrite.py` | Write a namespaced copy of `nav2_params.yaml` for launch |

## For AI Agents

- Import `rosy_navigation.frame_prefix` / `params_rewrite`. Do not add helpers under `launch/`.
- Tests: `test/test_nav2_hardware_slice.py` (host pytest, no ROS overlay).

<!-- MANUAL: -->
