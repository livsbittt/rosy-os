## D-49 Gazebo motion provenance hashes use the absorbed package root

**Status:** Accepted (2026-09-13). This is a source-evidence and maintenance
contract; it does not certify a physical robot or motion trial.

**Context:** The absorbed Gazebo motion contract tool still hashed a historical
`/tmp` checkout path. On a clean Rosy OS checkout or Device that path was
absent, so the evidence could silently contain no runtime source hashes while
appearing to complete.

**Decision:** `measure_motion_contract.py` resolves the current package root
from its own location by default. A measurement host may set
`ROSY_SOURCE_ROOT`, but the path must exist and contain both `package.xml` and
the `rosy_control/` package directory. Hashes are deterministic, relative to
that root, and limited to the runtime package. The old checkout is not a
supported source.

**Consequences:** Source provenance remains valid after folder consolidation,
and a missing or malformed source root fails before ROS initialization. The
measurement tool stays an opt-in simulation aid; its output remains distinct
from ARM64 artifact, Device readback, and FIELD evidence.

**Validation / Transition:** Pure tests cover default discovery, explicit
source-root override, missing-root failure, and the absence of the retired
checkout reference. The full absorbed Control suite remains the local gate.

**References:** [motion contract tool](../../src/rosy_control/tools/gz/measure_motion_contract.py), [folder governance](../plans/2026-09-13-folder-structure-governance.md), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
