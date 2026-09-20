# Unsigned ARM64 Handoff Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a fail-closed importer that verifies and safely extracts the native ARM64 unsigned handoff before offline signing.

**Architecture:** A standalone unprivileged Python CLI verifies the sibling archive checksum, decompresses to a private temporary tar, validates all archive members, and extracts into staging. Existing manifest validation plus explicit builder, provenance, payload hash, and nested Docker archive checks must pass before an atomic rename exposes the output.

**Tech Stack:** Python 3 standard library, external `zstd` CLI, pytest, existing ROSY manifest validators.

---

### Task 1: Define the importer contract with failing tests

**Files:**
- Create: `test/test_unsigned_handoff_import.py`
- Create: `deploy/release/import_unsigned_payload.py`

**Step 1:** Build real compact handoff fixtures containing manifest,
provenance, builder JSON, runtime data, and two Docker-save archives.

**Step 2:** Add a valid-import test that calls `import_handoff(...)` and expects
an atomically materialized output plus a `signed: false` report.

**Step 3:** Run
`python -m pytest test/test_unsigned_handoff_import.py::test_imports_verified_arm64_handoff -q`
and confirm it fails because the importer module does not exist.

**Step 4:** Add the minimal module/API skeleton and repeat until the valid
fixture passes without weakening the assertions.

### Task 2: Add fail-closed archive boundary tests

**Files:**
- Modify: `test/test_unsigned_handoff_import.py`
- Modify: `deploy/release/import_unsigned_payload.py`

**Step 1:** Add separate red tests for outer checksum mismatch, unsafe member
path, symbolic/hard link, special member, unexpected root, member-count limit,
expanded-size limit, and pre-existing output.

**Step 2:** Run each new test and confirm the expected missing validation.

**Step 3:** Implement the smallest validation for each case. Extract only after
the complete member list passes.

**Step 4:** Run the focused file and require all cases to pass.

### Task 3: Add identity and content verification tests

**Files:**
- Modify: `test/test_unsigned_handoff_import.py`
- Modify: `deploy/release/import_unsigned_payload.py`

**Step 1:** Add red tests for builder, release, revision, signing-key, and
provenance mismatches; unexpected signature files; missing or undeclared
payload files; declared-byte tampering; duplicate image IDs; and non-arm64 or
non-Linux Docker configs.

**Step 2:** Implement checks using `manifest.validate_manifest`, SHA-256, and
read-only `tarfile` inspection of the nested image archives.

**Step 3:** Verify failure cleanup leaves neither output nor staging data.

### Task 4: Add CLI and runbook handoff

**Files:**
- Modify: `deploy/release/import_unsigned_payload.py`
- Modify: `docs/deployment/pinky-pro-first-device-runbook.md`
- Modify: `docs/deployment/arm64-build-notes.md`
- Modify: `deploy/release/AGENTS.md`

**Step 1:** Add required CLI arguments for archive, checksum, output, release
ID, revision, and signing-key ID. Return JSON on success and a stable coded
error on failure.

**Step 2:** Add a CLI test that verifies JSON output and confirms no private-key
argument exists.

**Step 3:** Replace the runbook's manual extraction gap with the importer
command, saved importer JSON, and explicit `$PAYLOAD` assignment.

### Task 5: Verify, document, and integrate

**Files:**
- Modify: `docs/reference/ROSY ADR Log.md`
- Modify: `deploy/logs.md`
- Modify: `deploy/progress.md`
- Modify: `deploy/index.md`

**Step 1:** Run focused importer, release manifest/signing/bundle, workflow,
secret-scan, and commissioning tests.

**Step 2:** Run `git diff --check` and the module harness.

**Step 3:** Commit the verified unit with explicit paths, fast-forward merge it
to local `main`, push, and require final CI success.
