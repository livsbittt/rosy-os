## D-36: Signed runtime delivery and writable generation data (2026-09-08)

**Status:** Accepted for local implementation; ARM64/Pi acceptance pending. D-35 is reserved by the concurrent Fleet work.

**Decision:** Release delivery uses pre-enrolled Ed25519 keys and bounded archive staging. GitHub checking may stage automatically, but activation requires explicit maintenance with the runtime stopped. Boot, activation and rollback start core only. Kernel/rootfs and host-tool updates remain outside this adapter.

Immutable config/data generations remain rollback evidence. Each activation data generation also owns a writable `data-working/<generation>` copied from its snapshot; CORE mounts only that working tree. First migration includes HOME's `.rosy` data. Rollback reuses the prior working tree and does not merge candidate writes. `activation.json` remains the sole active-generation authority. The host-owned previous activation is `/etc/rosy/previous-activation.json`, persisted by the activation journal before success is finalized and restored on rollback.

**Consequences:** Working generations require explicit storage retention; no automatic pruning is wired into the delivery CLI. The signed image digests used by this Docker save/load adapter are Docker content image IDs, not registry index digests. The host-agent socket/dashboard installer remains separate. See `docs/deployment/github-updates.md`.

---
