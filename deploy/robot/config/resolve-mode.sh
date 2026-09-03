# Canonical runtime mode from board.yaml. Source this file; do not execute it.
# Overlay YAML exists only for catalog modes. Aliases never get their own copy.

resolve_runtime_mode() {
    local requested="${1:-}"
    local board="${2:-}"
    if [[ -z "$requested" || -z "$board" ]]; then
        echo "error: resolve_runtime_mode requires mode and board.yaml" >&2
        return 2
    fi
    case "$requested" in
        core|motor|hardware)
            printf '%s\n' "$requested"
            return 0
            ;;
    esac
    if [[ ! -f "$board" ]]; then
        echo "error: board catalog not found: $board" >&2
        return 2
    fi
    local alias
    alias="$(sed -n "s/^  ${requested}: //p" "$board" | head -n 1 | tr -d '\r ')"
    case "$alias" in
        core|motor|hardware)
            printf '%s\n' "$alias"
            return 0
            ;;
    esac
    echo "error: unknown ROSY_RUNTIME_MODE '$requested' (expected core, motor, hardware, or a board.yaml alias)" >&2
    return 2
}
