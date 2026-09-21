## D-50 Active rosy_control guides use Rosy OS Device procedures

**Status:** Accepted (2026-09-13). Historical standalone instructions remain
available for provenance, but they are not an install or runtime interface.

**Context:** The absorbed package retained long standalone Control guides that
referenced `/home/pinky/dev_ws` and a separate workspace. A banner labelled
them legacy, but an agent or operator could still copy those commands into a
Rosy OS Device procedure.

**Decision:** `src/rosy_control/CLAUDE.md` and `src/rosy_control/STEPS.txt` are
canonical Rosy OS guides. They use the repository test/build flow and the
Device sequence `install-pi.sh`, `verify-pi.sh`, `runtime-mode.sh`, and
`device-readback.sh --json`. The old standalone guides stay in the workspace
archive and are never required by build, runtime, or tests.

**Consequences:** A package-level guide now agrees with the root README and
Device evidence gates. The absorption inventory records the two files as
adapted with their current destination hashes. Legacy entry points remain
available only for parity tests and still cannot run beside CORE.

**Validation / Transition:** The package ownership contract checks both guide
files for the canonical commands and rejects the old standalone workspace
paths. Device installation and physical acceptance remain separate gates.

**References:** [package guides](../../src/rosy_control/CLAUDE.md), [Device runbook](../../src/rosy_control/STEPS.txt), [absorption inventory](../plans/2026-09-12-control-absorption-inventory.csv), [folder governance](../plans/2026-09-13-folder-structure-governance.md).

---
