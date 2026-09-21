## D-52 ARM64 camera placement and shadow handoff gates

**Status:** Proposed (2026-09-13). Camera execution placement and final command
handoff remain unaccepted Device decisions.

**Context:** Picamera2/libcamera permissions and timing determine whether a
host service or least-privilege container can deliver bounded frames. A new
policy must also be observed with real input before it can own output.

**Decision:** On a native ARM64 bench Pi, compare host capture with a
least-privilege vision container using identical fixtures. Measure permission,
restart, frame freshness/drops, p95 latency, CPU, memory, and fault isolation;
record the selected path in a follow-up accepted ADR. Before changing the
publisher, run the new producer in shadow mode while the approved publisher
alone drives the robot. The shadow record must include sample count, mismatch
classes, worst latency, and owner-approved tolerances. Missing tolerances or a
second real publisher keep the gate `HOLD`.

**Consequences:** The current camera worker and sensor adapter remain
observation-only and disabled by default. Device evidence, rather than a
Windows fixture, decides the placement and handoff.

**Validation / Transition:** Complete the ARM64 spike and shadow replay before
enabling camera or switching final command ownership. Keep the old generation
available for rollback and repeat stationary readback after every change.

**References:** [camera worker ADR](#d-48-optional-camera-preprocessing-worker-telemetry), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
