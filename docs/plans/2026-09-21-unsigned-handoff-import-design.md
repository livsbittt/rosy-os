# Unsigned ARM64 handoff import design

Date: 2026-09-21
Status: Approved for implementation under the active Pinky Pro commissioning goal

## Problem and trust boundary

D-145 exports an unsigned GitHub Actions artifact containing a compressed
`rosy-unsigned-payload/` tree, `arm64-builder.json`, and a sibling checksum.
The current runbook verifies only the outer archive checksum before asking an
offline operator to extract the payload and invoke `package_release.py`. That
leaves archive path safety, builder/manifest identity, provenance, declared
file hashes, and nested container architecture to separate manual checks.

The importer is an unprivileged, pre-signing tool. It never accepts, discovers,
or reads a private key. It converts a downloaded handoff into a verified local
directory; it does not make that directory trusted, signed, publishable, G0,
DEVICE, or FIELD evidence.

## Decision

Add `deploy/release/import_unsigned_payload.py`. The command requires the
archive, its checksum file, an unused output directory, and the expected
release ID, git revision, and signing-key ID. It verifies the outer checksum
before decompression, uses `zstd` into a private temporary tar, and inspects
every tar member before extraction. Absolute paths, parent traversal,
backslashes, links, devices, FIFOs, unexpected roots, excessive member counts,
and excessive expanded size fail closed.

The extracted handoff must contain exactly one payload directory and one
builder report. The importer validates the existing manifest schema, rejects
pre-existing signature files, requires builder/manifest/provenance identity to
match the operator-provided expectations, hashes every declared payload file,
and rejects undeclared files. It opens both Docker-save archives without
loading them, confirms `linux/arm64`, and matches their config image IDs to the
manifest and provenance. Only after every check passes is the staged handoff
renamed to the requested output. Success prints one machine-readable JSON line
with `signed: false`.

## Failure and cleanup behavior

The output directory must not exist. All work occurs in a sibling temporary
directory so a same-filesystem rename is atomic. Failures use stable error
codes and remove temporary tar and extraction data. The source archive and
checksum are never modified. Hash mismatches are reported without exposing
payload content, and subprocess stderr is reduced to a bounded diagnostic.

Tests build small real zstd-compressed tar fixtures and real nested Docker-save
fixtures. They cover a valid import, outer checksum tampering, path traversal,
links, identity mismatch, undeclared payload data, changed declared bytes,
non-arm64 image config, output collision, and cleanup after failure. The
runbook will use the importer before any offline signing command.
