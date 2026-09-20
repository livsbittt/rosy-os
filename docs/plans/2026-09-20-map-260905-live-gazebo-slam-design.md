# map_260905_update_v2 Live Gazebo SLAM Design

Date: 2026-09-20

Status: approved execution target. Completion requires a fresh runtime evidence bundle; checked-in static geometry is not sufficient.

## Goal

Run one Pinky-sized Rosy in the exact `map_260905_update_v2` Gazebo world, traverse the spawn-connected drivable space, build and save a live `slam_toolbox` occupancy map, compare it with the source collision geometry, and expose the same run through CORE and Fleet.

## Non-goals and evidence boundary

- A copied PGM, replayed scan, or static world raster cannot satisfy this run.
- Gazebo success does not certify physical stopping distance, camera homography, wheel calibration, or a higher device speed tier.
- The disconnected lower-left pocket is reported separately. A robot cannot be required to enter sealed geometry, but its observable walls remain part of the wall-recall audit.
- CORE remains the only final per-robot `cmd_vel` publisher. Nav2 or a mapping controller may produce `nav_cmd_vel`; Gazebo consumes only CORE's final output.

## Architecture

### Exact world asset

The Control map bundle remains the source of truth. Its world, reference map, identity metadata, and review assets are installed with the `control` package. The Gazebo world catalog points to that installed asset instead of maintaining a second editable copy. A host contract test checks that the catalog entry resolves to the exact v2 file and carries a safe spawn inside the connected corridor.

### Runtime graph

```text
exact v2 world -> Gazebo lidar/odom/TF -> ros_gz_bridge
                                      -> slam_toolbox -> live /rosy_01/map
mapping goals -> Nav2 -> /rosy_01/nav_cmd_vel -> CORE safety/command manager
                                               -> /rosy_01/cmd_vel -> Gazebo
CORE API -> Fleet client/monitor
```

Every component uses one run ID. The runner refuses motion until clock, scan, odom, TF, SLAM map, CORE API, and the sole-final-publisher check are fresh.

### Adaptive traversal and recovery

The initial route is a conservative centerline coverage path derived from the v2 wall geometry. Speed is reducing-only and varies continuously:

- open straight space: use the configured simulation ceiling;
- curvature or shrinking front/side clearance: reduce speed using the available stopping/uncertainty margin;
- blocked nose or lost progress: stop, reverse by a clearance-derived distance, rotate toward the more open side, then retry;
- recovery distance is bounded by measured rear clearance and robot footprint, not a fixed 8 cm constant;
- repeated failure at a segment marks the segment for a different approach direction instead of grinding indefinitely.

The simulator can tune route spacing, lookahead, clearance bands, speed ceiling, reverse margin, and retry count. Defaults remain map/footprint derived. Physical deployments still require an active calibration and motion-envelope certificate; Gazebo tuning never promotes a physical certificate.

### Map and run acceptance

The evidence monitor saves the latest OccupancyGrid as NPZ, PGM, and YAML and records trajectory, topic freshness, publisher ownership, CORE state, and Fleet readback. Acceptance is fail-closed:

- fresh map frame and finite origin;
- no collision/contact and no footprint-wall penetration along the recorded trajectory;
- spawn-connected interior unknown fraction at most 1%;
- known-corridor purity at least 95%;
- minimum wall-surface recall at least 98%;
- phantom occupied fraction below 2%;
- CORE is alive and is the sole final `cmd_vel` publisher;
- Fleet reads the same robot/run as online;
- final velocity is zero and artifacts share the same run ID.

If the world or SLAM raster makes one threshold physically impossible, the run remains HOLD until the metric or geometry defect is explained and fixed; the threshold is not silently weakened.

## Failure handling

- Missing/frozen sensor, TF, map, CORE, or Fleet evidence stops motion and fails the run.
- A recovery maneuver is allowed only with fresh front/rear/side clearance.
- Timeout saves partial evidence with `mapping_complete=false`.
- All generated runtime files are written under a run-specific evidence directory and are not substituted for source assets.

## Verification layers

1. ROS-free contracts: world resolution, asset install, topic/remap ownership, route/recovery math, audit thresholds.
2. Linux ROS/Gazebo smoke: exact world loads, robot spawns, bridge topics carry messages, SLAM publishes a non-empty map, CORE stays alive.
3. Full live run: autonomous traversal, saved map, geometric audit, CORE/Fleet same-run proof, screenshot.
4. Regression: full Control, CORE, Fleet, simulation, and repository contract suites.

