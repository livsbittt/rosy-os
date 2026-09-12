<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# deployment

## Purpose

Operator runbooks for Raspberry Pi 5: first Wi-Fi image, runtime services, power-bench, acceptance, and release key/retention.

## Key Files

| File | Description |
|------|-------------|
| `raspberry-pi-runtime.md` | Device permissions, systemd/compose runtime, core/motor/hardware modes |
| `pinky-pro-board-support.md` | First ROSY OS board: mode-specific capabilities, LiDAR hardware slice |
| `raspberry-pi-wifi-image.md` | Headless SD burn, Wi-Fi, SSH, Windows deploy |
| `arm64-build-notes.md` | Current ARM64/Pi build and runtime boundary notes |
| `legacy-arm64-guide.md` | Historical upstream instructions kept for provenance; do not use for deployment |
| `pi5-acceptance-checklist.md` | Physical acceptance tests |
| `power-bench-verification.md` | Power/idle/standby bench |
| `release-signing-key.md` | Ed25519 signing key handling |
| `release-retention.md` | How many signed releases to keep |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Align steps with `deploy/robot/` scripts (`install-pi.sh`, `deploy-from-windows.ps1`, `runtime-mode.sh`). Modes are `core` / `motor` / `hardware`.
- UART on Pi 5 is documented in `deploy/robot/configure-uart-pi5.sh` (default motor device `/dev/ttyAMA4`).
- Do not enable `lidar.standby_stop` until `power-bench-verification.md` passes. `pi5-acceptance-checklist.md` gates are HOLD until field sign-off.

### Testing Requirements

Contracts: `test/test_robot_runtime.py`, `test/test_pi_wifi_deployment.py`, `test/test_dds_identity_contracts.py` (the commissioning and renumber procedures in these runbooks). Hardware steps are manual (`pi5-acceptance-checklist.md`).

### Common Patterns

Korean operator prose; commands are copy-pasteable bash/pwsh.

## Dependencies

### Internal

- `deploy/robot/`, `deploy/image/`, `deploy/release/`

### External

- Raspberry Pi OS Lite 64-bit, Docker, nmcli

<!-- MANUAL: -->
