#!/usr/bin/env bash
# Build a ROSY OS release image from the pinned Ubuntu Server 24.04 LTS arm64
# Raspberry Pi base image on a native ARM64 host.
#
# This has never been run. Every input it depends on is in inputs.lock.yaml,
# and the ones marked `verified: false` there are assumptions nobody has
# checked — run `verify-inputs.sh` first. Producing an image is not BUILD_GO;
# `verify-artifacts.sh` is.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOCK="$SCRIPT_DIR/inputs.lock.yaml"
DIST="${ROSY_DIST_DIR:-$REPO_ROOT/dist}"
WORKSPACE="$REPO_ROOT"
CACHE_DIR="${ROSY_IMAGE_CACHE:-$SCRIPT_DIR/cache}"

RELEASE_ID=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --release-id) RELEASE_ID="${2:-}"; shift 2 ;;
        --dist) DIST="${2:-}"; shift 2 ;;
        --workspace) WORKSPACE="${2:-}"; shift 2 ;;
        --cache-dir) CACHE_DIR="${2:-}"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

fail() { echo "FAIL: $*" >&2; exit 1; }

[[ -n "$RELEASE_ID" ]] || fail "--release-id is required (YYYY.MM.DD-NNN)"
[[ "$RELEASE_ID" =~ ^[0-9]{4}\.[0-9]{2}\.[0-9]{2}-[0-9]{3}$ ]] \
    || fail "release id must be YYYY.MM.DD-NNN, got '$RELEASE_ID'"

# The design is explicit that an x86 QEMU build is for development only and is
# never the basis of a release image. Refusing here rather than producing an
# artifact nobody may ship.
ARCH="$(uname -m)"
[[ "$ARCH" == "aarch64" ]] \
    || fail "release images are built on native arm64; this host is $ARCH (see design 7.1)"

[[ -f "$LOCK" ]] || fail "missing $LOCK"
"$SCRIPT_DIR/verify-inputs.sh" "$LOCK" \
    || fail "inputs are not pinned; see the 'verified: false' entries in $LOCK"

SOURCE_REVISION="$(awk '
    /^sources:[[:space:]]*$/ { in_sources=1; next }
    in_sources && /^[^[:space:]]/ { exit }
    in_sources && $1 == "rosy_revision:" {
        print $2
        exit
    }
' "$LOCK" | tr -d '\r')"
[[ "$SOURCE_REVISION" =~ ^[0-9a-f]{40}$ ]] \
    || fail "sources.rosy_revision is not a full Git commit"

"$SCRIPT_DIR/fetch-base-image.sh" \
    --lock "$LOCK" --cache-dir "$CACHE_DIR"

OUT="$DIST/$RELEASE_ID"
mkdir -p "$OUT"

"$SCRIPT_DIR/build-native-payload.sh" \
    --workspace "$WORKSPACE" \
    --release-root "$OUT/payload" \
    --source-revision "$SOURCE_REVISION" \
    --release-id "$RELEASE_ID"

echo "==> building $RELEASE_ID into $OUT"
echo "    The verified base image and offline native ROSY payload are ready."
fail "not implemented: no image has been built yet, and this script will not \
pretend otherwise. See docs/deployment/pi5-acceptance-checklist.md section 2."
