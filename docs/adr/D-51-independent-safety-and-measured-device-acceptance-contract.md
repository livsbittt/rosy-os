## D-51 Independent safety and measured Device acceptance contract

**Status:** Proposed (2026-09-13). The source and simulation suites cannot
approve physical motion by equivalence alone.

**Context:** The absorbed Control behavior is useful regression evidence, but
matching it does not establish a safe response to stale, contradictory, or
missing sensors, restart, e-stop release, or a delayed stop. Device acceptance
also needs numeric limits that can be reproduced by another operator.

**Decision:** Before a real command handoff, each Device profile must define
the `NORMAL`, `LIMITED`, `HOLD`, `ESTOP_LATCHED`, and `RECOVERY_PENDING` states,
required-stream deadlines, invalid and contradictory-input behavior, limit
precedence, maximum stop latency, and maximum stop distance. Unset values are
`HOLD`. E-stop release and restart discard the previous candidate and require
fresh evidence plus an explicit new action. Equivalence tests remain a
regression layer; the independent safety matrix is a separate acceptance
layer.

**Consequences:** The implementation plan can report a measured threshold and
an evidence owner for every physical gate. A green Python/ROS test cannot
promote a motor, camera, payload, or OMX capability by itself.

**Validation / Transition:** Add the matrix to the selected Pinky Pro profile
and run boot, restart, CORE loss, sensor loss, tilt, pickup, obstacle, stop,
e-stop, and recovery trials with wheels lifted first. Record repetitions,
fixture, timing source, result, artifact revision, and rollback result.

**References:** [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md), [integrated design](../plans/2026-09-12-rosy-os-control-integrated-design.md).

---
