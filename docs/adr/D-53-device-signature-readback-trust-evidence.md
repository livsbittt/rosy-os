## D-53 Device signature/readback trust evidence

**Status:** Accepted (2026-09-13). Pi and physical release acceptance remain
pending.

**Context:** Rosy release staging verifies the signed checksum list, while the
current readback reports the manifest key ID and immutable digests. A key ID or
digest report alone does not prove that the installed release was verified by
the trusted key or that an unauthorized downgrade was rejected.

**Decision:** Device acceptance retains the signed checksum verification result,
trusted key ID, manifest, image digests, activation record, and readback as one
evidence set. A tampered manifest, missing/untrusted signature, unsupported
downgrade, or digest mismatch quarantines the runtime in core-off state. The
readback contract exposes a cryptographic verification result and requires it
for `device_runtime=GO`.

**Consequences:** Existing release staging remains the first enforcement point;
the Device readback repeats the signed checksum verification without
serializing credentials. A readback with only `signing_key_id`, missing
signature material, or a failed verifier is `HOLD`.

**Validation / Transition:** Fake-device cases cover missing, malformed,
untrusted, and valid signatures. The focused readback and release-boundary
tests pass locally; repeat on a Pi after installing the signed ARM64 artifact
and preserve the JSON alongside the release manifest.

**References:** [release signing](../deployment/release-signing-key.md), [Device readback ADR](#d-46-device-install--readback-evidence-contract), [Device validation plan](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
