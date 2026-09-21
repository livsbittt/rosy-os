#!/usr/bin/env bash
# Validate, map and deterministically compress a completed raw Pi disk image.
set -euo pipefail

RAW=""
OUTPUT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --raw-image) RAW="${2:-}"; shift 2 ;;
        --output) OUTPUT="${2:-}"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
fail() { echo "FAIL: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail "image finalization requires root"
[[ -f "$RAW" && "$RAW" == *.img ]] || fail "--raw-image must name an existing .img"
[[ "$OUTPUT" == *.img.xz && ! -e "$OUTPUT" ]] || fail "--output must be a new .img.xz"
for command in losetup lsblk e2fsck bmaptool xz sync; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is missing: $command"
done

LOOP=""
cleanup() {
    set +e
    [[ -z "$LOOP" ]] || losetup --detach "$LOOP"
    rm -f -- "$OUTPUT.part"
}
trap cleanup EXIT

sync
LOOP="$(losetup --find --show --partscan --read-only "$RAW")"
PARTITIONS="$(lsblk -nrpo NAME,PARTN,FSTYPE "$LOOP")"
ROOT_DEVICE="$(printf '%s\n' "$PARTITIONS" | awk '$2 == "2" && tolower($3) ~ /^ext/ {print $1}')"
[[ -n "$ROOT_DEVICE" ]] || fail "root partition 2 was not found"
e2fsck -fn "$ROOT_DEVICE"
losetup --detach "$LOOP"
LOOP=""

bmaptool create -o "${OUTPUT%.xz}.bmap" "$RAW"
xz --threads=0 --check=crc64 -9e --stdout -- "$RAW" > "$OUTPUT.part"
xz --test "$OUTPUT.part"
mv -- "$OUTPUT.part" "$OUTPUT"
rm -f -- "$RAW"
trap - EXIT
echo "FLASHABLE_IMAGE_READY $OUTPUT"
