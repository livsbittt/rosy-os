<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# image

## Purpose

Build a signed ROSY OS release image on **native aarch64**. The scripts refuse x86/QEMU hosts. Inputs must be pinned in `inputs.lock.yaml`; producing a file is not enough — `verify-artifacts.sh` is the go/no-go.

## Key Files

| File | Description |
|------|-------------|
| `build-image.sh` | Native arm64 image build; requires `--release-id YYYY.MM.DD-NNN` |
| `inputs.lock.yaml` | Pinned inputs; entries with `verified: false` block the build |
| `verify-inputs.sh` | Fails if lock entries are unverified or missing |
| `verify-artifacts.sh` | Post-build artifact checks (`BUILD_GO`) |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Do not add an x86 "release" path. Dev QEMU images are not shippable (design 7.1).
- The pipeline is not implemented: after `verify-inputs.sh`, `build-image.sh` still fails (“no image has been built yet”). `inputs.lock.yaml` still has `verified: false` / unset commits. Do not pretend a shippable image exists.
- Tests: `test/test_image_pipeline.py`, `test/test_image_checks.py`.

### Testing Requirements

```bash
python3 -m pytest test/test_image_pipeline.py test/test_image_checks.py -v
```

### Common Patterns

`set -euo pipefail`; `ROSY_DIST_DIR` defaults to repo `dist/`.

## Dependencies

### Internal

- Design: `docs/plans/2026-09-01-rosy-os-v1-image-release-design.md`
- Signing/storage in `deploy/release/`

### External

- Native aarch64 Raspberry Pi OS host, OpenSSL

<!-- MANUAL: -->
