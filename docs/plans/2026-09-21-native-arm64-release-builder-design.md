# Native ARM64 release-bundle builder design

- Date: 2026-09-21
- Status: Accepted by the existing ROSY OS release and G0 contracts
- Related: D-66, `pinky-pro-first-device-runbook.md`,
  `2026-09-01-rosy-os-v1-image-release-design.md`

## Purpose

G0 needs a signed release bundle containing two real Linux/ARM64 Docker image
archives, an exact manifest, and a verified Ed25519 checksum signature. The
current repository documents the manual steps but has no command that creates
the unsigned payload, while `deploy/image/build-image.sh` is deliberately an
unimplemented full-SD-image path. This builder closes the release-bundle gap;
it does not claim that a Raspberry Pi OS SD image has been built.

## Trust boundary

The build runs only on a native `aarch64` host and refuses a dirty source tree,
an abbreviated revision, a mutable ROS base tag, or an existing output path.
It builds `core` and `io` from the checked-out revision using a ROS base image
specified as `name@sha256:<digest>`. Both results must inspect as `linux/arm64`,
carry the source-revision OCI label, and expose an immutable Docker image ID.

The builder never reads a private signing key. It produces an atomic unsigned
payload containing `runtime/`, both Docker-save archives, `manifest.json`, and
`build-provenance.json`. The existing offline `package_release.py` is the only
step that creates `SHA256SUMS`, signs it, verifies the matching public key, and
packs `rosy-release-<id>.tar.zst`.

## Data flow and failure handling

1. Validate native architecture, clean Git revision, release/key identifiers,
   digest-pinned ROS base, and output placement.
2. Build both targets with Buildx `--load` and revision labels.
3. Inspect OS, architecture, image ID, and label; any mismatch fails closed.
4. Save both images, copy the runtime compose/config tree, and hash every
   payload file.
5. Validate the generated manifest with the production manifest validator.
6. Atomically rename the staging directory to the requested output.

Any failure removes only the builder-created sibling staging directory. It
never replaces an existing payload, changes a runtime, signs data, publishes a
release, or operates a robot.

## Verification

Host tests inject a command runner and assert rejection paths, exact Docker
commands, architecture/revision inspection, deterministic manifest contents,
and atomic cleanup. The native Pi run must additionally retain command output,
image inspection JSON, payload hashes, signed-bundle verification, and G0
staging JSON. Windows/QEMU tests remain source evidence only.
