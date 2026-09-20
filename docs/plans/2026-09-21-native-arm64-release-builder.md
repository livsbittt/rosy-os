# Native ARM64 release-bundle builder implementation plan

> Use `executing-plans`, `using-git-worktrees`, TDD, and verification before
> completion.

## Task 1: Fail-closed input contract

- Add tests for native `aarch64`, clean full Git revision, release/key IDs,
  digest-pinned ROS base, and an unused output outside the checkout.
- Implement the minimal validator and CLI argument surface.
- Run `python -m pytest test/test_arm64_release_builder.py -q`.

## Task 2: Build and inspect the two images

- Add failing tests for the two Buildx commands and for rejecting OS,
  architecture, image-ID, and revision-label mismatches.
- Build `core` and `io` with `--load`, then inspect both results.
- Re-run the focused tests.

## Task 3: Assemble the unsigned payload atomically

- Add failing tests for Docker-save archives, runtime/config copying,
  provenance, exact manifest file hashes, production manifest validation, and
  staging cleanup on failure.
- Implement assembly and atomic rename without accessing a private key.
- Re-run release manifest/bundle/signing and image-pipeline suites.

## Task 4: Native/operator handoff

- Document the exact native build, offline signing, verification, and G0 stage
  commands in the first-device runbook.
- Run the full deploy/release/commissioning tests and `git diff --check`.
- Commit and integrate only after review and fresh verification.
