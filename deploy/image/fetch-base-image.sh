#!/usr/bin/env bash
# Fetch and verify the exact Ubuntu Raspberry Pi base image declared in the lock.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="$SCRIPT_DIR/inputs.lock.yaml"
CACHE_DIR="${ROSY_IMAGE_CACHE:-$SCRIPT_DIR/cache}"
OFFLINE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --lock) LOCK="${2:-}"; shift 2 ;;
        --cache-dir) CACHE_DIR="${2:-}"; shift 2 ;;
        --offline) OFFLINE=1; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

fail() { echo "FAIL: $*" >&2; exit 1; }

[[ -f "$LOCK" ]] || fail "missing lock file: $LOCK"

lock_value() {
    local wanted="$1"
    awk -v wanted="$wanted" '
        /^base_image:[[:space:]]*$/ { in_base=1; next }
        in_base && /^[^[:space:]]/ { exit }
        in_base {
            key=$1
            sub(/:$/, "", key)
            if (key == wanted) {
                $1=""
                sub(/^[[:space:]]+/, "")
                sub(/\r$/, "")
                gsub(/^['\''"]|['\''"]$/, "")
                print
                exit
            }
        }
    ' "$LOCK"
}

URL="$(lock_value url)"
EXPECTED_SHA256="$(lock_value sha256)"
MINIMUM_SIZE="$(lock_value minimum_size_bytes)"

[[ "$URL" == https://* ]] || fail "base image must use a pinned HTTPS URL"
[[ "${URL,,}" != *latest* ]] || fail "base image must use a pinned HTTPS URL, not latest"
[[ "$EXPECTED_SHA256" =~ ^[0-9a-fA-F]{64}$ ]] \
    || fail "base image sha256 must be a pinned 64-character digest"
[[ "$MINIMUM_SIZE" =~ ^[1-9][0-9]*$ ]] \
    || fail "base image minimum_size_bytes must be a positive integer"

URL_PATH="${URL%%\?*}"
FILENAME="${URL_PATH##*/}"
[[ -n "$FILENAME" && "$FILENAME" != "$URL_PATH" ]] \
    || fail "base image URL has no filename"

mkdir -p "$CACHE_DIR"
DEST="$CACHE_DIR/$FILENAME"

verify_file() {
    local candidate="$1"
    local size actual
    size="$(wc -c < "$candidate" | tr -d '[:space:]')"
    (( size >= MINIMUM_SIZE )) \
        || fail "base image is too small: $size bytes (minimum $MINIMUM_SIZE)"
    actual="$(sha256sum "$candidate" | awk '{print $1}')"
    [[ "${actual,,}" == "${EXPECTED_SHA256,,}" ]] \
        || fail "base image checksum mismatch: expected $EXPECTED_SHA256, got $actual"
}

if [[ -f "$DEST" ]]; then
    verify_file "$DEST"
    echo "CACHE_VERIFIED $DEST"
    exit 0
fi

(( OFFLINE == 0 )) || fail "verified cache is missing in offline mode: $DEST"
command -v curl >/dev/null 2>&1 || fail "curl is required to fetch the base image"

PART="$DEST.part.$$"
trap 'rm -f -- "$PART"' EXIT
curl --fail --location --proto '=https' --proto-redir '=https' \
    --retry 3 --output "$PART" "$URL"
verify_file "$PART"
mv -f -- "$PART" "$DEST"
trap - EXIT
echo "DOWNLOADED_VERIFIED $DEST"
