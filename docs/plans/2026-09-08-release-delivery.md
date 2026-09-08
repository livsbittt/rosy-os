# Release Delivery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete a locally testable signed release delivery and core-only activation path, ready for a future public GitHub repository.

**Architecture:** Reuse manifest/signing/layout/Updater. Add bounded bundle staging, a public GitHub client, host CLI/runtime adapter and opt-in timer. Preserve immutable generation snapshots and use separate writable data copies.

**Tech Stack:** Python standard library, OpenSSL 3, zstd, Docker Compose, systemd, GitHub Releases.

## Task 1 — Signed bundle boundary
Create deploy/release/bundle.py and test/test_release_bundle.py. First assert the module is missing;
then implement archive validation, signature verification, manifest payload matching, bounded
staging and atomic promotion. Test actual signed fixtures and tampering, not mocked verification.

## Task 2 — GitHub pull
Create deploy/release/github_release.py and test/test_github_release.py. Inject only HTTP transport.
Test stable version selection, repository/URL validation, digest/size checks, partial download cleanup
and downgrade prevention. Implement no token persistence and no automatic install.

## Task 3 — Activation adapter and CLI
Create deploy/release/release_runtime.py, cli.py and test/test_release_delivery.py. Test root-scoped status,
staging→installation, state refusal, image verification, health rollback, durable previous record,
and writable working data without changing immutable generation snapshots.

## Task 4 — Host integration and publication
Add deploy/robot/rosy-release, update-check service/timer and explicit installer. Add a
workflow_dispatch-only publish workflow for externally signed artifacts. Extend ci.yml with Fleet.
Document commands and actual remaining physical gates in docs/deployment/github-updates.md.

## Task 5 — Verification
Run new tests plus manifest/signing/layout/updater/storage/host/runtime boundaries and core/Fleet.
Mutate a path or signature guard and prove a targeted test fails, restore and rerun.
Run git diff --check, Python compile and shell syntax. Keep unrun ARM64/Pi proof as HOLD.

## Local result (2026-09-08)

Tasks 1–5 implemented in isolated branch `feature/rosy-update-delivery`, based on `b0b6623`.
The concurrently changing Fleet worktree was not merged or modified.

- Windows full CORE/Fleet/host contract suites: **1595 passed, 17 skipped**.
- WSL Linux release/bundle/GitHub/runtime/CLI/updater/publication suites: **113 passed**.
- Final Linux CLI/delivery delta, including unfinished-journal refusal and `.rosy` migration: **14 passed**.
- New release modules pass flake8 (120 columns), Python compilation and host scripts pass bash syntax checks.
- Four source guards and the archive traversal guard were disabled in temporary copied trees;
  each mutation failed its intended test, and restored copies passed. Production working files were untouched.
- Independent review fixes: readable nonroot payload, journal-owned previous activation,
  decompression reserve, pre-install disk budget, and refusal to boot an unfinished activation.

No real release keys, GitHub repository, published artifact, Docker ARM64 activation or hardware operation
was created/performed. Public repository creation remains a user decision. Host OS/rootfs OTA,
updater self-update, host-agent/dashboard integration and real Pi acceptance remain outside this local result.
Operational commands and remaining boundaries are in `docs/deployment/github-updates.md`.
