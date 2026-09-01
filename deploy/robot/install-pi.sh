#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="${ROSY_SOURCE_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
INSTALL_ROOT="${ROSY_INSTALL_ROOT:-/opt/rosy}"
ROSY_CONFIG="${ROSY_CONFIG_PATH:-/etc/rosy/rosy.yaml}"
ROSY_DATA="${ROSY_DATA_PATH:-/var/lib/rosy}"
RUN_USER="${ROSY_RUN_USER:-${SUDO_USER:-rosy}}"
INITIAL_CREDENTIALS="/etc/rosy/initial-credentials.txt"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

require_root() {
    [[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "run with sudo: sudo bash deploy/robot/install-pi.sh"
}

preflight_host() {
    [[ -r /proc/device-tree/model ]] || fail "Raspberry Pi model information is unavailable"
    local model
    model="$(tr -d '\0' </proc/device-tree/model)"
    [[ "$model" == *"Raspberry Pi 5"* ]] || fail "expected Raspberry Pi 5, found: $model"
    [[ "$(dpkg --print-architecture)" == "arm64" ]] || fail "Raspberry Pi OS Lite 64-bit (arm64/aarch64) is required"

    # shellcheck disable=SC1091
    source /etc/os-release
    [[ "${ID:-}" == "raspbian" || "${ID:-}" == "debian" ]] || fail "Raspberry Pi OS/Debian is required"
    [[ -n "${VERSION_CODENAME:-}" ]] || fail "VERSION_CODENAME is missing from /etc/os-release"
    id "$RUN_USER" >/dev/null 2>&1 || fail "runtime user '$RUN_USER' does not exist; create it in Raspberry Pi Imager"
    [[ -f "$SOURCE_ROOT/deploy/robot/compose.yaml" ]] || fail "Rosy release root is invalid: $SOURCE_ROOT"
}

install_host_packages() {
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl gnupg openssl rsync

    curl --fail --silent --show-error --location --max-time 20 \
        https://download.docker.com/linux/debian/gpg \
        --output /tmp/rosy-docker.asc || fail "Internet/DNS check failed while downloading Docker signing key"

    install -m 0755 -d /etc/apt/keyrings
    install -m 0644 /tmp/rosy-docker.asc /etc/apt/keyrings/docker.asc
    rm -f /tmp/rosy-docker.asc

    cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker.service
    docker compose version >/dev/null
}

install_release() {
    local source_real install_real
    source_real="$(readlink -f "$SOURCE_ROOT")"
    install -d -o root -g root -m 0755 "$INSTALL_ROOT"
    install_real="$(readlink -f "$INSTALL_ROOT")"
    if [[ "$source_real" != "$install_real" ]]; then
        rsync -a --delete --exclude '.git/' --exclude '.pytest_cache/' \
            "$source_real/" "$install_real/"
    fi
    chmod 0755 "$INSTALL_ROOT/deploy/robot/entrypoint.sh" \
        "$INSTALL_ROOT/deploy/robot/runtime-mode.sh" \
        "$INSTALL_ROOT/deploy/robot/install-pi.sh" \
        "$INSTALL_ROOT/deploy/robot/verify-pi.sh"
}

write_initial_config() {
    local run_group config_tmp admin_token operator_token viewer_token
    run_group="$(id -gn "$RUN_USER")"
    install -d -o root -g "$run_group" -m 0750 /etc/rosy
    install -d -o "$RUN_USER" -g "$run_group" -m 0750 "$ROSY_DATA"

    if [[ ! -f "$ROSY_CONFIG" ]]; then
        admin_token="$(openssl rand -hex 24)"
        operator_token="$(openssl rand -hex 24)"
        viewer_token="$(openssl rand -hex 24)"
        config_tmp="$(mktemp)"
        trap 'rm -f "${config_tmp:-}"' RETURN
        sed \
            -e "s/CHANGE_ME_ADMIN/$admin_token/" \
            -e "s/CHANGE_ME_OPERATOR/$operator_token/" \
            -e "s/CHANGE_ME_VIEWER/$viewer_token/" \
            "$INSTALL_ROOT/deploy/robot/config/rosy.pi5.example.yaml" >"$config_tmp"
        install -o root -g "$run_group" -m 0640 "$config_tmp" "$ROSY_CONFIG"
        {
            echo "Rosy initial API credentials — remove this file after recording them"
            echo "administrator=$admin_token"
            echo "operator=$operator_token"
            echo "viewer=$viewer_token"
        } >"$INITIAL_CREDENTIALS"
        chmod 0600 "$INITIAL_CREDENTIALS"
        rm -f "$config_tmp"
        trap - RETURN
    else
        echo "INFO: preserving existing $ROSY_CONFIG"
    fi
}

set_env_value() {
    local file="$1" key="$2" value="$3"
    if grep -q "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >>"$file"
    fi
}

write_runtime_environment() {
    local env_file run_group
    env_file="$INSTALL_ROOT/deploy/robot/.env"
    run_group="$(id -gn "$RUN_USER")"
    if [[ ! -f "$env_file" ]]; then
        install -o root -g "$run_group" -m 0640 \
            "$INSTALL_ROOT/deploy/robot/.env.example" "$env_file"
    fi
    set_env_value "$env_file" ROSY_UID "$(id -u "$RUN_USER")"
    set_env_value "$env_file" ROSY_GID "$(id -g "$RUN_USER")"
    set_env_value "$env_file" ROSY_DIALOUT_GID "$(getent group dialout | cut -d: -f3)"
    set_env_value "$env_file" ROSY_CONFIG_PATH "$ROSY_CONFIG"
    set_env_value "$env_file" ROSY_DATA_PATH "$ROSY_DATA"
    set_env_value "$env_file" ROSY_RUNTIME_MODE core
}

build_and_start_core() {
    local runtime_dir container_id status attempt
    runtime_dir="$INSTALL_ROOT/deploy/robot"
    cd "$runtime_dir"
    docker compose --env-file .env build rosy-core
    ROSY_RUNTIME_MODE=core "$runtime_dir/runtime-mode.sh" up
    container_id="$(docker compose --env-file .env ps -q rosy-core)"
    [[ -n "$container_id" ]] || fail "rosy-core container was not created"
    for attempt in $(seq 1 45); do
        status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
        [[ "$status" == "healthy" ]] && break
        [[ "$status" == "exited" || "$status" == "dead" ]] && fail "rosy-core entered state: $status"
        sleep 2
    done
    [[ "${status:-}" == "healthy" ]] || fail "rosy-core did not become healthy within 90 seconds"
    curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8080/api/v1 >/dev/null \
        || fail "FastAPI health request failed"
}

enable_boot_service() {
    install -m 0644 "$INSTALL_ROOT/deploy/robot/rosy-runtime.service" \
        /etc/systemd/system/rosy-runtime.service
    systemctl daemon-reload
    systemctl enable rosy-runtime.service
}

main() {
    require_root
    preflight_host
    install_host_packages
    install_release
    write_initial_config
    write_runtime_environment
    build_and_start_core
    enable_boot_service
    echo "PASS: Rosy core-only runtime is installed and healthy"
    echo "Credentials: sudo cat $INITIAL_CREDENTIALS"
    echo "After recording them: sudo rm -f $INITIAL_CREDENTIALS"
    echo "Verify Wi-Fi/dashboard: sudo $INSTALL_ROOT/deploy/robot/verify-pi.sh --require-internet"
}

main "$@"
