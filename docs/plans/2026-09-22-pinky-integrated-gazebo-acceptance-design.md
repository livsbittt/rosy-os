# Pinky Pro Integrated Gazebo Acceptance Design

Date: 2026-09-22

Status: approved execution target. This is ROS-SIM evidence only; physical-device and field gates remain separate.

## Goal

In one run-ID-bound Gazebo execution, prove that the conservative Pinky Pro envelope can traverse the measured `map_260905_update_v2` space, build a navigation-usable live map, localize and complete a Nav2 goal, observe the white lane and supported road markings from the simulated front camera while moving, and stop fail-closed through CORE's sole final velocity publisher.

## Fixed physical and authority boundaries

- Robot diameter: `0.172 m`; body radius: `0.086 m`.
- Clearance margin: `0.010 m`; required center clearance: `0.096 m`.
- The checked-in 16-wall geometry is immutable during acceptance.
- `control` publishes sensor evidence only. Mapping and Nav2 publish candidate `nav_cmd_vel`; CORE is the only final `cmd_vel` publisher.
- Mapping traversal and Nav2 do not command concurrently. The mapping runner publishes a final zero, exits, and only then does launch start Nav2.
- Camera support is limited to the implemented lane, stop-line, crosswalk, and traffic-light classes. General obstacle/object recognition is outside this acceptance.

## Runtime sequence

1. Start the traffic-enhanced measured world at the semantic spawn `(-0.20, -0.15)` with lidar, odometry, TF, and `/camera/front`.
2. Start `slam_toolbox`, CORE, line/road observers, and the evidence collector. Hold long enough to observe lane, stop line, and crosswalk at the known camera pose.
3. Start the scan-safe mapping runner at route index 0. It first connects to the reviewed 52-point route and then covers the spawn-connected space using the accepted body envelope.
4. On terminal mapping status, publish zero, retain the terminal status long enough for the collector, and exit.
5. Launch Nav2 against the live SLAM map with a `0.086 m` circular radius and `0.010 m` padding. Send a bounded return goal to the semantic lane area.
6. After the Nav2 result and a stable final zero command, write a single JSON result and stop the launch.

## Evidence model

The collector records one run ID plus:

- exact world and wall-geometry SHA-256 values;
- camera frame count/size/frame ID;
- latest and best `CAMERA_LINE` and `CAMERA_ROAD` observations;
- whether a visible white line was observed while final motion was non-zero;
- mapping terminal state, occupancy-grid geometry, known cells, and freshness;
- trajectory length, minimum center-to-wall distance, minimum body clearance, and collision flag;
- robot-reachable unknown, occupied, and outside-raster fractions;
- full-raster wall recall and phantom occupancy as a distinct fidelity result;
- Nav2 goal acceptance/result/final pose error;
- final `cmd_vel`, its publisher identities, and final-zero stability.

## Acceptance gates

The integrated ROS-SIM result passes only when:

- mapping route is complete and a non-empty fresh map exists;
- robot-reachable unknown, occupied, and outside-raster fractions are each at most 1%;
- every sampled pose keeps at least `0.010 m` body clearance and no footprint-wall overlap occurs;
- `CAMERA_LINE` is visible with confidence at least 0.8, including at least one observation while the robot is moving;
- lane, stop line, and crosswalk are detected from real Gazebo frames;
- Nav2 accepts and succeeds on the bounded probe goal with final position error at most `0.08 m`;
- `/cmd_vel` has exactly one publisher, CORE;
- final linear and angular velocity remain effectively zero for at least 0.5 seconds.

Full-raster wall recall remains a separately named fidelity gate. It is not allowed to invalidate honest robot-reachable completion, and a value below the existing 98% research target is reported as `HOLD_FULL_RASTER_FIDELITY`, never hidden inside a broad PASS.

## Failure behavior

- Missing or malformed camera, map, odometry, mapping status, Nav2 result, or velocity evidence fails the run.
- Invalid geometry, stale map, non-finite coordinates, multiple final publishers, or clearance below the required envelope fails closed.
- A timeout writes the partial artifact with failed gates and publishes zero; it never fabricates a successful result.
- The launch may tune simulation timing and reducing-only speed, but may not shrink the robot, move walls, or promote this evidence to physical Pinky acceptance.

