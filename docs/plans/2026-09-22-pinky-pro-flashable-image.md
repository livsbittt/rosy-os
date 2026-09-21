# Pinky Pro Flashable Image Implementation Plan

> Execute task-by-task with test-driven development. Never write physical media
> until Tasks 1-8 are green and the operator reconfirms the exact disk.

**Goal:** Produce a signed `rosy-os-pinky-pro-<release-id>-arm64.img.xz` that
Raspberry Pi Imager can write directly, then verify the complete media and Pinky Pro.

**Architecture:** Customize Canonical's checksum-pinned Ubuntu Server 24.04
Raspberry Pi preinstalled disk image on native ARM64. Install native ROS 2 Jazzy,
the offline ROSY payload, hardened systemd services and device-neutral first boot;
sign offline; personalize only after writing each card.

---

## Task 1: Freeze the flashable-image contract

**Files:**
- Create: `test/test_pinky_flashable_image_contract.py`
- Modify: `deploy/image/inputs.lock.yaml`
- Modify: `deploy/image/AGENTS.md`

1. Add failing contracts for `.img.xz`, exact product filename, Pi 5/arm64,
   required artifact set, no ISO, no product Docker and device-neutral common image.
2. Record image layout/tool prerequisites in the lock without marking unverified
   native-host facts as verified.
3. Run focused tests and commit `test(image): freeze Pinky flashable image contract`.

## Task 2: Verify Canonical input provenance

**Files:**
- Modify: `deploy/image/fetch-base-image.sh`
- Modify: `deploy/image/verify-inputs.sh`
- Modify: `test/test_image_pipeline.py`

1. Test official `.img.xz`, exact SHA-256, checksum-document provenance, cache reuse,
   altered bytes and filename/version drift.
2. Fetch only the locked Canonical URL and capture the verified evidence on the
   native release host.
3. Keep `verified: false` until the live native-host run succeeds.
4. Commit `feat(image): verify Canonical Pi image provenance`.

## Task 3: Build a disposable raw-image workspace

**Files:**
- Create: `deploy/image/image_workspace.sh`
- Create: `test/test_image_workspace_contract.py`
- Modify: `deploy/image/build-image.sh`

1. Test native-aarch64/root/tool preflight, no in-place cache mutation, unique temp
   workspace, loop partition discovery and reverse-order cleanup on every failure.
2. Implement decompress, raw-image expansion, loop setup and boot/root mount.
3. Run mutation tests that fail each mount step and prove no loop/mount leaks.
4. Commit `feat(image): add fail-closed Pi image workspace`.

## Task 4: Customize Ubuntu rootfs and boot partition

**Files:**
- Create: `deploy/image/customize-rootfs.sh`
- Create: `deploy/image/verify-mounted-image.py`
- Create: `test/test_image_customization_contract.py`
- Modify: `deploy/image/build-native-payload.sh`

1. Test device-neutral cloud-init, accounts, NetworkManager, native Jazzy, required
   ROSY packages, CORE-only target and absence of Docker/product credentials.
2. In native chroot install locked packages and copy payload/immutable overlay.
3. Enable release recovery, first boot, provision gate and runtime target in order.
4. Verify package inventory and `ros2 pkg prefix` inside the mounted image.
5. Commit `feat(image): install native ROSY into Ubuntu Pi image`.

## Task 5: Finalize the `.img.xz`

**Files:**
- Create: `deploy/image/finalize-image.sh`
- Create: `test/test_flashable_image_layout.py`
- Modify: `deploy/image/build-image.sh`

1. Test filesystem checks, unmount-before-compress, exact product filename, no sparse
   working image in release output and deterministic compression options.
2. Run filesystem checks, trim/zero free space where safe, compress the raw disk image
   and calculate its SHA-256.
3. Mount the result read-only and verify both partition content and bootability inputs.
4. Commit `feat(image): emit Pinky Pro flashable img.xz`.

## Task 6: Generate SBOM, manifest and unsigned handoff

**Files:**
- Create: `deploy/image/create-image-manifest.py`
- Modify: `deploy/image/verify-artifacts.sh`
- Modify: `test/test_image_checks.py`

1. Test the exact artifact set, base/source/build provenance, SBOM, inventory, secret
   scan and manifest-to-image hash binding.
2. Produce `SHA256SUMS` only after every unsigned artifact is final.
3. Export an atomic unsigned handoff with no private key.
4. Commit `feat(image): package verifiable Pinky image handoff`.

## Task 7: Sign offline and verify before disk discovery

**Files:**
- Modify: `deploy/release/package_release.py`
- Create: `deploy/sd/verify-image-release.py`
- Modify: `deploy/sd/prepare-rosy-sd.ps1`
- Modify: `test/test_sd_writer_contract.py`

1. Add failing tests for wrong key, signature, image filename/hash, release ID, board and
   architecture; prove rejection happens before `Get-Disk` and the writer.
2. Reuse the Ed25519 release verifier and approved public-key trust store.
3. Replace signature-file existence checks with signed-release verification.
4. Commit `feat(sd): verify signed image before media selection`.

## Task 8: Run the native ARM64 build and capture ARTIFACT evidence

**Files:**
- Modify: `.github/workflows/build-arm64-payload.yml` or create a dedicated manual
  unsigned-image workflow
- Create: `docs/validation/<release-id>/artifact-report.md`

1. Run on `ubuntu-24.04-arm` or an approved native aarch64 release host.
2. Capture base verification, build logs, cleanup proof, image/SBOM/inventory hashes and
   read-only mount inspection.
3. Transfer the unsigned handoff to the offline signer and verify the signed result with
   the committed public key.
4. Set ARTIFACT GO only when the evidence is complete.
5. Commit `docs(validation): prove Pinky flashable artifact`.

## Task 9: Prepare and write the connected card

1. Store the Wi-Fi passphrase once with `-SetWifiCredential`; never put it in a command.
2. Re-probe the disk, run `-PlanOnly`, confirm model/serial/size and retain the plan.
3. Require `ERASE DISK <n> <rosy-pinky-xxxx>`, write the signed `.img.xz`, copy the
   one-time bundle and update the registry/receipt atomically.
4. Read the entire media back and compare the image-level digest before safe eject.
5. Keep MEDIA HOLD on any mismatch.

## Task 10: Boot and accept Pinky Pro

1. Boot the card and capture Ubuntu release, kernel/firmware, first-boot state, release
   signature, systemd status and all required `ros2 pkg prefix` results.
2. Verify unique identity, serial binding, ROS domain/namespace, CORE-only initial mode,
   device ACL and single final `cmd_vel` publisher.
3. Exercise reboot, power loss, network loss, rollback and motor deadman.
4. Repeat with a second Pinky before FLEET GO.
5. Commit `docs(validation): accept Pinky Pro image and device`.

## Current checkpoint

- Task 1: source-complete. D-164, the lock and executable contract agree on the exact
  `.img.xz` filename, required signed sidecars, device-neutral fields and ISO prohibition.
- Task 2: source-complete. The fetcher now pins Canonical's checksum document,
  detached signature, Ubuntu image-signing key fingerprint and trusted keyring; it
  rejects signature, signer, filename, signed-digest and downloaded-byte drift.
- Task 3: source-complete. A native-root-only disposable workspace decompresses a
  copy, expands partition 2, mounts root then boot, exposes bounded paths to one
  customizer and always unmounts/detaches/removes in reverse order. It publishes
  no raw image when setup, customization or cleanup fails.
- Task 4: source-complete. Native ARM64 chroot customization installs a SHA-pinned
  official ROS apt-source package, Jazzy/rosdep dependencies, ROSY release and
  CORE-only systemd/first-boot overlay, then checks package/layout neutrality.
- Tasks 5-6: planned; existing native payload, systemd, rollback and first-boot pieces
  are inputs, not proof of a completed disk image.
- Task 7 writer preflight: source-complete ahead of Tasks 4-6. The Windows writer
  now verifies the Ed25519-signed checksum set and exact image manifest identity
  before its first disk probe; offline key ceremony and real artifact remain pending.
- Task 8: blocked until a native ARM64 run verifies the real Canonical inputs and
  produces the actual signed `.img.xz`; `base_image.verified` therefore remains false.
- Tasks 9-10: physical and destructive; connected media remains untouched until the
  signed artifact and explicit operator confirmation exist.
