# map_260905_update_v2 validation record — 2026-09-20

## Outcome

The exact map bundle can boot the isolated Gazebo + Nav2 + CORE stack, publish a
fresh localized pose, and accept a CORE navigation goal. Static analysis also
finds a connected route through the requested checkpoints with a conservative
0.115 m circumscribed radius. A complete unattended traversal and a new SLAM
map comparison are **not proven** by this run.

## Evidence obtained

- Exact map: `map_260905_update_v2/maps/map_260905.yaml` and `.pgm`, 600 x 300
  cells, 0.005 m resolution, origin `[-1.5, -0.75]`.
- CORE reported `map_id=occupancy:2646647774c5` and a fresh pose after the
  namespaced initial-pose seed completed.
- The non-composed Nav2 launch namespace was corrected from
  `/<robot>/<robot>/...` to `/<robot>/...`; map server, AMCL, planner,
  controller and behavior server reached active state.
- One earlier goal to `(0.0, 0.0)` reached `ARRIVED`. A later goal toward
  `(0.3, -0.15)` exposed a genuine corner case: at approximately
  `(0.08, -0.01)` the rectangular footprint could enter at one yaw and become
  `Start occupied` after turning.
- Simulation planning now uses the padded circumscribed radius
  `sqrt(0.06^2 + 0.06^2) + 0.03 = 0.1148528 m` in both costmaps. This is more
  conservative than the prior orientation-dependent rectangle.
- A repeat run booted and localized correctly, but its goal timed out while the
  shared WSL host load was approximately 60--90. That run is not counted as a
  route pass or a geometry failure.

## Flexible clearance recovery

When fresh calibrated geometry says turning is blocked, the recovery planner
checks both fixed-heading directions. Reverse is preferred only when otherwise
equivalent; an unsafe rear corridor never receives authority. The bound is
`min(calibrated circumscribed diameter, measured straight room - 0.005 m)`, not
a fixed 0.08 m. Execution remains at 0.005 m/s and stops on the first fresh
scan that restores rotation clearance, or on stale evidence, geometry change,
heading/lateral error, no progress, mission timeout, or a hazard.

Proposals without both `robot_diameter_m` and `max_reposition_m` fail closed;
there is no legacy 0.08 m fallback.

## Verification

- Flexible recovery unit/adapter tests: 30 passed.
- Wider recovery, adaptive-speed, certificate, command-gate, and calibration
  regression set: 102 passed.
- Full Control package: 1021 passed, 26 skipped, 2 failed. Both failures are the
  pre-existing `test_startup_profile.py` fixture omission of `web_port`, outside
  this change.
- Gazebo/Nav2 contract tests: 11 passed in 31.69 s.

## Remaining gates

- Full exact-route traversal: HOLD.
- SLAM re-generation and pixel/geometry comparison with this map: HOLD.
- Active CORE/Nav2 use of the Control recovery proposal: HOLD; the tested
  executor belongs to the legacy Control navigation session and must not be
  started beside CORE as a second final velocity publisher.
- Pi/ARM64 artifact, physical Pinky Pro clearance, stopping-distance trials,
  control-room observation, and field acceptance: HOLD.
