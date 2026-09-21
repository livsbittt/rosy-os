## D-55 Mobile manipulation is a robot-local mission capability

**Status:** Accepted (2026-09-17). Architecture. OMX capability stays disabled
until Device payload tests. Pinky+OMX composite Asset is still not v1 (D-71).

**Context:** Nav2 can move the base but does not establish grasp success,
object possession, arm collision safety or pallet stability. The current OS has
no accepted OMX/MoveIt execution path. A second arm or mission process that
publishes base velocity would also bypass the CORE command boundary.

**Decision:** A future `rosy_manipulation` action/state machine owns the
approach, perception, grasp, transport and placement transaction. OMX/MoveIt
publishes arm actions only; CORE remains the sole final `cmd_vel` arbiter. The
carried-object state selects a measured 2-D base footprint and speed envelope,
while MoveIt maintains the corresponding 3-D collision scene. Unknown object,
arm or gripper state causes HOLD after restart or link loss.

**Consequences:** Navigation and manipulation can be tested independently and
then composed with one mission ID and one evidence record. The API does not
advertise OMX until model, mount, power, hand-eye, collision interlock,
payload and recovery tests pass.

**Validation / Transition:** First validate known rectangular blocks and a
fixed placement fixture. Record grasp/placement success, repeatability,
minimum clearance, tip margin, battery/thermal load and recovery outcomes on
the Pi and Pinky bench before enabling a mobile profile.

**Implementation note (2026-09-13):** The Device configuration now carries a
`motion_profiles.yaml` template with explicit `unknown`, `base`, `stowed_arm`,
`carrying_box` and `placing` states. All are unmeasured by default. Hardware
launch accepts a measured state only when its polygon, clearance, payload,
motion envelope and MoveIt scene revision are present; it then injects the
same polygon into both Nav2 costmaps and applies the tighter state speed
limits. No estimated box or arm dimensions are shipped.

**References:** [mobile manipulation research](../plans/2026-09-12-mobile-manipulation-research.md), [Pinky/OMX mounting research](../plans/2026-09-12-pinky-omx-mounting-spec-research.md), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).
