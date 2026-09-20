# Pinky Pro hardware mapping G5 implementation plan

**Goal:** make the documented G5 procedure executable on the real Pinky Pro
without weakening the normal localization runtime.

1. Add red host contracts for backend validation, capabilities, mount mode,
   SLAM packaging/launch, readiness profiles, safe map output, and raw G5
   artifacts.
2. Add the SLAM hardware graph and namespace-aware mapper parameters.
3. Add the runtime/backend overlay selection and SLAM-only write boundary.
4. Add SLAM lifecycle readiness and safe shared map-save paths.
5. Add bounded MCAP/map artifact collection to the operator runbook and G5
   evidence validator.
6. Run focused tests, full host tests, Docker Compose rendering, and available
   image/launch smoke checks.
7. Commit, merge to local `main`, rerun the merged verification, and leave the
   physical gate HOLD until the robot is reachable.
