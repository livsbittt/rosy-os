<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-14 | Updated: 2026-09-14 -->

# public-keys

## Purpose

Committed Ed25519 **public** trust anchors for signed releases. No production key is selected yet.

## Key Files

| File | Description |
|------|-------------|
| `README.md` | How a `<signing-key-id>.pem` public key gets committed; private key stays offline |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Commit only the selected public key as `<signing-key-id>.pem` after ownership is decided.
- Never generate a shared signing key in CI or on a robot. Never commit a private key.
- `ROSY_RELEASE_KEY_ID` lives in the GitHub `release` environment (approval required).

### Testing Requirements

Release signing tests live in `../../../test/test_release_signing.py`, not here.

### Common Patterns

One public PEM per key id. Empty directory plus README until a key is chosen.

## Dependencies

### Internal

- `../signing.py`, `docs/deployment/release-signing-key.md`

### External

- OpenSSL 3 Ed25519

<!-- MANUAL: -->
