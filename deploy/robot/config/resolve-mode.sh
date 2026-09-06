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
    if [[ ! "$requested" =~ ^[A-Za-z0-9_-]+$ ]]; then
        # 별칭 조회는 이 값을 sed 식에 넣는다. 걸러내지 않으면 운영자가
        # 거절 사유 대신 sed 의 파싱 오류를 읽게 된다.
        echo "error: unknown ROSY_RUNTIME_MODE '$requested' (expected core, motor, hardware, or a board.yaml alias)" >&2
        return 2
    fi
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
