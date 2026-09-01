#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="${ROSY_SOURCE_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
INSTALL_ROOT="${ROSY_INSTALL_ROOT:-/opt/rosy}"
ROSY_CONFIG="${ROSY_CONFIG_PATH:-/etc/rosy/rosy.yaml}"
ROSY_DATA="${ROSY_DATA_PATH:-/var/lib/rosy}"
RUN_USER="${ROSY_RUN_USER:-${SUDO_USER:-rosy}}"
INITIAL_CREDENTIALS="/etc/rosy/initial-credentials.txt"
INITIAL_CREDENTIALS_CREATED=0

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

require_root() {
    [[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "run with sudo: sudo bash deploy/robot/install-pi.sh"
}

preflight_host() {
    [[ "$INSTALL_ROOT" == "/opt/rosy" ]] || fail "ROSY_INSTALL_ROOT must be /opt/rosy"
    [[ "$ROSY_CONFIG" == "/etc/rosy/rosy.yaml" ]] || fail "ROSY_CONFIG_PATH must be /etc/rosy/rosy.yaml"
    [[ "$ROSY_DATA" == "/var/lib/rosy" ]] || fail "ROSY_DATA_PATH must be /var/lib/rosy"
    [[ "$RUN_USER" != "root" ]] || fail "Rosy must run as the non-root user created in Raspberry Pi Imager"
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
    local docker_key_tmp
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl gnupg openssl rsync

    install -m 0755 -d /etc/apt/keyrings
    (
        docker_key_tmp="$(mktemp)"
        trap 'rm -f "${docker_key_tmp:-}"' EXIT
        curl --fail --silent --show-error --location --max-time 20 \
            https://download.docker.com/linux/debian/gpg \
            --output "$docker_key_tmp" \
            || fail "Internet/DNS check failed while downloading Docker signing key"
        install -m 0644 "$docker_key_tmp" /etc/apt/keyrings/docker.asc
    )

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

stop_existing_runtime() {
    local -a project_containers=()

    if systemctl is-active --quiet rosy-runtime.service 2>/dev/null; then
        systemctl stop rosy-runtime.service
    fi
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        mapfile -t project_containers < <(
            docker ps -aq --filter label=com.docker.compose.project=rosy-runtime
        )
        if ((${#project_containers[@]} > 0)); then
            docker stop --time 10 "${project_containers[@]}"
            docker rm "${project_containers[@]}"
        fi
    fi
}

install_release() {
    local source_real install_real
    source_real="$(readlink -f "$SOURCE_ROOT")"
    [[ ! -L "$INSTALL_ROOT" ]] || fail "$INSTALL_ROOT must not be a symbolic link"
    [[ ! -e "$INSTALL_ROOT" || -d "$INSTALL_ROOT" ]] || fail "$INSTALL_ROOT must be a directory"
    install -d -o root -g root -m 0755 "$INSTALL_ROOT"
    install_real="$(readlink -f "$INSTALL_ROOT")"
    [[ "$install_real" == "$INSTALL_ROOT" ]] || fail "$INSTALL_ROOT resolves outside its canonical path"
    [[ "$source_real" != "$INSTALL_ROOT/"* ]] || fail "release source must not be inside $INSTALL_ROOT"
    if [[ "$source_real" != "$install_real" ]]; then
        rsync -a --delete --chown=root:root \
            --exclude '.git/' --exclude '.pytest_cache/' \
            --exclude 'deploy/robot/.env' \
            "$source_real/" "$install_real/"
    fi
    chown -R root:root "$INSTALL_ROOT"
    chmod -R go-w "$INSTALL_ROOT"
    chmod 0755 "$INSTALL_ROOT/deploy/robot/entrypoint.sh" \
        "$INSTALL_ROOT/deploy/robot/runtime-mode.sh" \
        "$INSTALL_ROOT/deploy/robot/install-pi.sh" \
        "$INSTALL_ROOT/deploy/robot/verify-pi.sh"
}

write_initial_config() {
    local run_group config_tmp admin_token operator_token viewer_token
    run_group="$(id -gn "$RUN_USER")"
    [[ ! -L /etc/rosy ]] || fail "/etc/rosy must not be a symbolic link"
    install -d -o root -g "$run_group" -m 0750 /etc/rosy
    [[ "$(readlink -f /etc/rosy)" == "/etc/rosy" ]] || fail "/etc/rosy is not canonical"
    [[ ! -L "$ROSY_DATA" ]] || fail "$ROSY_DATA must not be a symbolic link"
    install -d -o "$RUN_USER" -g "$run_group" -m 0750 "$ROSY_DATA"
    [[ "$(readlink -f "$ROSY_DATA")" == "$ROSY_DATA" ]] || fail "$ROSY_DATA is not canonical"
    [[ ! -L "$ROSY_CONFIG" ]] || fail "$ROSY_CONFIG must not be a symbolic link"

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
        [[ ! -L "$INITIAL_CREDENTIALS" ]] || fail "$INITIAL_CREDENTIALS must not be a symbolic link"
        install -o root -g root -m 0600 /dev/null "$INITIAL_CREDENTIALS"
        {
            echo "Rosy initial API credentials — remove this file after recording them"
            echo "administrator=$admin_token"
            echo "operator=$operator_token"
            echo "viewer=$viewer_token"
        } >"$INITIAL_CREDENTIALS"
        chmod 0600 "$INITIAL_CREDENTIALS"
        INITIAL_CREDENTIALS_CREATED=1
        rm -f "$config_tmp"
        trap - RETURN
    else
        echo "INFO: preserving existing $ROSY_CONFIG"
    fi
    [[ -f "$ROSY_CONFIG" ]] || fail "$ROSY_CONFIG must be a regular file"
    if grep -Eq "CHANGE_ME|rosy-dev-" "$ROSY_CONFIG"; then
        fail "$ROSY_CONFIG contains placeholder or development credentials"
    fi
    chown root:"$run_group" "$ROSY_CONFIG"
    chmod 0640 "$ROSY_CONFIG"
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
    local env_file run_group dialout_gid
    env_file="$INSTALL_ROOT/deploy/robot/.env"
    run_group="$(id -gn "$RUN_USER")"
    dialout_gid="$(getent group dialout | cut -d: -f3)"
    [[ -n "$dialout_gid" ]] || fail "the dialout group is unavailable"
    if [[ ! -f "$env_file" ]]; then
        install -o root -g "$run_group" -m 0640 \
            "$INSTALL_ROOT/deploy/robot/.env.example" "$env_file"
    fi
    [[ ! -L "$env_file" && -f "$env_file" ]] || fail "$env_file must be a regular non-symlink file"
    set_env_value "$env_file" ROSY_UID "$(id -u "$RUN_USER")"
    set_env_value "$env_file" ROSY_GID "$(id -g "$RUN_USER")"
    set_env_value "$env_file" ROSY_DIALOUT_GID "$dialout_gid"
    set_env_value "$env_file" ROSY_CONFIG_PATH "$ROSY_CONFIG"
    set_env_value "$env_file" ROSY_DATA_PATH "$ROSY_DATA"
    set_env_value "$env_file" ROSY_RUNTIME_MODE core
    chown root:"$run_group" "$env_file"
    chmod 0640 "$env_file"
}

build_and_start_core() {
    local runtime_dir container_id status attempt
    runtime_dir="$INSTALL_ROOT/deploy/robot"
    cd "$runtime_dir"
    ROSY_RUNTIME_MODE=core "$runtime_dir/runtime-mode.sh" down
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
    systemctl enable --now rosy-runtime.service
}

main() {
    require_root
    preflight_host
    stop_existing_runtime
    install_host_packages
    install_release
    write_initial_config
    write_runtime_environment
    build_and_start_core
    enable_boot_service
    echo "PASS: Rosy core-only runtime is installed and healthy"
    if ((INITIAL_CREDENTIALS_CREATED)); then
        echo "Credentials: sudo cat $INITIAL_CREDENTIALS"
        echo "After recording them: sudo rm -f $INITIAL_CREDENTIALS"
    else
        echo "INFO: existing credentials were preserved; no new credential file was created"
    fi
    echo "Verify Wi-Fi/dashboard: sudo $INSTALL_ROOT/deploy/robot/verify-pi.sh --require-internet"
}

main "$@"
