<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# deploy

## Purpose

Robot-host delivery: build a signed ROSY OS image, store/activate releases, and run CORE/motor/IO as Docker Compose services on Raspberry Pi 5. Host privilege (network, reboot, release activate) lives in Host Agent, never in `rosy_core` (D-22).

## Key Files

None at this level — three sibling pipelines.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `image/` | Native aarch64 image build + input/artifact verification (see `image/AGENTS.md`) |
| `release/` | Manifest, signing, storage, updater, Host Agent (see `release/AGENTS.md`) |
| `robot/` | Dockerfile, compose, systemd, Pi install/verify scripts (see `robot/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- CORE is internet-facing and unprivileged. Do not add `nmcli`, `reboot`, or docker-compose control inside `rosy_core`.
- Compose services: `rosy-core` (always), `rosy-motor` (profile `motor`), hardware/LiDAR (profile `hardware`). `runtime-mode.sh` modes are `core` | `motor` | `hardware`.
- Release images must be built on native arm64, not x86 QEMU (`deploy/image/build-image.sh`).
- `test/` at repo root is the contract suite for this tree; `test/conftest.py` puts `deploy/release` on `sys.path`.

### Testing Requirements

```bash
python3 -m pytest test/ -v
# notable modules: test_host_agent, test_release_*, test_image_*, test_robot_runtime,
# test_pi_wifi_deployment, test_network_*, test_release_boundary_guards
```

### Common Patterns

- Read-only containers, `cap_drop: ALL`, `no-new-privileges`, host network, CycloneDDS.
- Secrets and Wi-Fi credentials stay on the host (`/etc/rosy`), not in the image.

## Dependencies

### Internal

- Image/Dockerfile build context is the repo root (`src/` packages).
- Contract: `docs/reference/rosy-host-agent-contract.md`

### External

- Docker Compose, systemd, OpenSSL 3 (Ed25519), Raspberry Pi OS Lite 64-bit

<!-- MANUAL: -->
