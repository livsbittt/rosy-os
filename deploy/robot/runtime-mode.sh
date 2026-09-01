#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROSY_ENV_FILE:-$SCRIPT_DIR/.env}"
ACTION="${1:-}"
MODE="${ROSY_RUNTIME_MODE:-core}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "error: Rosy environment file not found: $ENV_FILE" >&2
    exit 1
fi

cd "$SCRIPT_DIR"

compose() {
    docker compose --env-file "$ENV_FILE" "$@"
}

case "$MODE" in
    "core"|"hardware") ;;
    *)
        echo "error: unknown ROSY_RUNTIME_MODE '$MODE' (expected core or hardware)" >&2
        exit 2
        ;;
esac

case "$ACTION" in
    up)
        if [[ "$MODE" == "core" ]]; then
            compose up -d --remove-orphans rosy-core
        else
            compose --profile hardware up -d --remove-orphans
        fi
        ;;
    down)
        compose --profile hardware down --timeout 10
        ;;
    status)
        compose --profile hardware ps
        ;;
    *)
        echo "usage: $0 {up|down|status}" >&2
        exit 2
        ;;
esac
