## D-54 Nav2 profile limits and field maps fail closed

**Status:** Accepted (2026-09-17). Source/configuration gate. Field-map identity
and physical acceptance remain HOLD.

**Context:** CORE and Nav2 currently receive related limits from different
files. The CORE Pinky profile caps angular velocity at 0.80 rad/s, while Nav2
launch and smoother defaults are higher. Hardware launch also selects a
packaged demo map when the site map is missing. Those defaults are useful for
simulation but can hide a commissioning error on a real robot.

**Decision:** The selected Device profile is the source for Nav2 velocity,
acceleration, goal tolerance, progress and footprint parameters. The launch
path validates the generated values before enabling hardware mode. Demo maps
are allowed only for simulation/bench profiles; a field profile enters HOLD
until a loadable site map, image checksum and matching map ID are present.

**Consequences:** Planner tuning is versioned with the robot profile and the
same limits apply to API, Nav2 and absorbed Control candidates. A missing or
stale map becomes a visible commissioning failure instead of a successful goal
on the wrong map.

**Validation / Transition:** Add source tests for profile/parameter equality,
map fail-closed behavior and waypoint map matching. On a Pi, record map ID,
localization covariance, goal error and minimum clearance on a fixed course.

**Implementation note (2026-09-13):** `rosy_navigation.profile_limits` now
loads the mounted Device profile during `hardware.launch.py`, validates launch
overrides and velocity-bearing Nav2 parameters, and fails before including the
Nav2 graph when a ceiling is exceeded. The same launch defaults to a strict
site-map requirement; only an explicit `allow_demo_map:=true` enables the
packaged demo map. This closes the source/configuration gate; the field-map
identity and physical acceptance gates remain open.

**References:** [hardware launch](../../src/rosy_navigation/launch/hardware.launch.py), [Nav2 parameters](../../src/rosy_navigation/params/nav2_params.yaml), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
