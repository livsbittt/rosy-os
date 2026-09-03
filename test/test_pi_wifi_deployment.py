"""Static safety contracts for headless Raspberry Pi Wi-Fi deployment."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "robot"
INSTALLER = DEPLOY / "install-pi.sh"
VERIFIER = DEPLOY / "verify-pi.sh"
RUNTIME_MODE = DEPLOY / "runtime-mode.sh"
WINDOWS_DEPLOY = DEPLOY / "deploy-from-windows.ps1"
WINDOWS_VERIFY = DEPLOY / "verify-from-windows.ps1"
UART_CONFIG = DEPLOY / "configure-uart-pi5.sh"
MOTOR_VERIFY = DEPLOY / "verify-motors.sh"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deployment_kit_files_exist():
    for path in (
        INSTALLER,
        VERIFIER,
        RUNTIME_MODE,
        WINDOWS_DEPLOY,
        WINDOWS_VERIFY,
        UART_CONFIG,
        MOTOR_VERIFY,
    ):
        assert path.is_file(), f"missing deployment file: {path.relative_to(ROOT)}"


def test_installer_uses_official_arm64_capable_docker_repository():
    script = _text(INSTALLER)

    assert "download.docker.com/linux/debian" in script
    assert "docker-ce" in script
    assert "docker-buildx-plugin" in script
    assert "docker-compose-plugin" in script
    assert "get.docker.com" not in script
    assert "/proc/device-tree/model" in script
    assert "aarch64" in script
    assert "VERSION_CODENAME" in script


def test_installer_generates_device_local_tokens_and_preserves_config():
    script = _text(INSTALLER)

    assert "openssl rand -hex" in script
    assert "initial-credentials" in script
    assert "chmod 0600" in script
    assert "-m 0640" in script
    assert 'if [[ ! -f "$ROSY_CONFIG" ]]' in script
    assert "rosy-dev-admin" not in script
    assert "WIFI_PASSWORD" not in script
    assert "SSID=" not in script
    assert "set_env_default" in script
    assert "set_env_default \"$env_file\" ROSY_MOTOR_BAUDRATE 1000000" in script
    assert "set_env_default \"$env_file\" ROSY_MOTOR_IDS '[1,2]'" in script
    assert "set_env_default \"$env_file\" ROSY_MAX_LINEAR_MPS 0.25" in script
    assert "set_env_default \"$env_file\" ROSY_MAX_ANGULAR_RPS 2.5" in script
    assert "set_env_default \"$env_file\" ROSY_MAX_WHEEL_RPM 100.0" in script
    assert (
        "set_env_default \"$env_file\" ROSY_MOTOR_PROFILE_ACCELERATION 200"
        in script
    )


def test_installer_guards_destructive_paths_and_activates_systemd():
    script = _text(INSTALLER)

    assert '[[ "$INSTALL_ROOT" == "/opt/rosy" ]]' in script
    assert '[[ "$ROSY_CONFIG" == "/etc/rosy/rosy.yaml" ]]' in script
    assert '[[ "$ROSY_DATA" == "/var/lib/rosy" ]]' in script
    assert "umask 077" in script
    assert '[[ ! -L "$INSTALL_ROOT" ]]' in script
    assert '[[ "$install_real" == "$INSTALL_ROOT" ]]' in script
    assert '[[ "$source_real" != "$INSTALL_ROOT/"* ]]' in script
    assert "--chown=root:root" in script
    assert "--exclude 'deploy/robot/.env'" in script
    assert "systemctl stop rosy-runtime.service" in script
    assert "trap on_install_exit EXIT" in script
    assert "systemctl disable --now rosy-runtime.service" in script
    assert "Rosy remains quarantined in core-off state" in script
    assert "systemctl enable --now rosy-runtime.service" in script
    assert 'grep -Eq "CHANGE_ME|rosy-dev-" "$ROSY_CONFIG"' in script
    assert 'chown root:"$run_group" "$ROSY_CONFIG"' in script
    assert 'chmod 0640 "$ROSY_CONFIG"' in script
    assert 'chown root:"$run_group" "$env_file"' in script
    assert 'chmod 0640 "$env_file"' in script
    assert "preflight_host\n    stop_existing_runtime\n    install_host_packages" in script


def test_installer_uses_private_temporary_docker_key_file():
    script = _text(INSTALLER)

    assert "mktemp" in script
    assert "/tmp/rosy-docker.asc" not in script


def test_runtime_defaults_to_core_only_and_rejects_unknown_modes():
    environment = _text(DEPLOY / ".env.example")
    wrapper = _text(RUNTIME_MODE)
    unit = _text(DEPLOY / "rosy-runtime.service")

    assert "ROSY_RUNTIME_MODE=core" in environment
    assert '${ROSY_RUNTIME_MODE:-core}' in wrapper
    assert "s/^ROSY_RUNTIME_MODE=//p" in wrapper
    assert '"core"|"motor"|"hardware")' in wrapper
    assert '--profile motor up -d --remove-orphans rosy-core rosy-motor' in wrapper
    assert "unknown ROSY_RUNTIME_MODE" in wrapper
    assert "runtime-mode.sh up" in unit
    assert "runtime-mode.sh down" in unit
    assert "network-online.target" in unit
    assert "docker.service" in unit


def test_network_verifier_separates_wifi_lan_internet_and_dashboard():
    script = _text(VERIFIER)

    for command in (
        "nmcli radio wifi",
        "nmcli -t -f GENERAL.CONNECTION",
        "ip -4",
        "ip route show default",
        "getent ahosts",
        "curl",
        "/api/v1",
        "/dashboard",
        "--require-internet",
    ):
        assert command in script
    for gate in ("WIFI", "LAN", "DNS", "INTERNET", "RUNTIME", "DASHBOARD"):
        assert gate in script
    assert "WIFI_PASSWORD" not in script
    assert "ip route show default dev wlan0" in script
    assert "curl --interface wlan0" in script
    assert 'runtime_service="rosy-motor"' in script
    assert 'runtime_service="rosy-io"' in script
    assert "capabilities.${configured_mode}.yaml" in script
    assert "missing board overlay" in script
    assert "requires running $runtime_service" in script


def test_windows_uploader_archives_only_git_head_and_keeps_ssh_host_checks():
    script = _text(WINDOWS_DEPLOY)

    assert "git archive" in script
    assert "Get-FileHash" in script
    assert "scp" in script
    assert "ssh" in script
    assert "git status --porcelain" in script
    assert "StrictHostKeyChecking=no" not in script
    assert "WifiPassword" not in script
    assert "CHANGE_ME" not in script
    assert "verify-from-windows.ps1" in script


def test_uart4_configuration_is_explicit_idempotent_and_does_not_move_motors():
    script = _text(UART_CONFIG)

    assert "/boot/firmware/config.txt" in script
    assert "dtoverlay=uart4-pi5" in script
    assert "[all]" in script
    assert "overlay_applies_to_pi5" in script
    assert '"[pi5]"' in script
    assert "grep -Fqx" in script
    assert "mktemp" in script
    assert "goal velocity" not in script.lower()
    assert "torque" not in script.lower()


def test_motor_preflight_checks_uart_and_runs_torque_free_dynamixel_probe():
    script = _text(MOTOR_VERIFY)
    probe = _text(ROOT / "src" / "rosy_bringup" / "rosy_bringup" / "dynamixel_probe.py")

    assert "/proc/device-tree/model" in script
    assert "dtoverlay=uart4-pi5" in script
    assert "overlay_applies_to_pi5" in script
    assert "ttyAMA4" in script
    assert "console=ttyAMA4" in script
    assert "dynamixel_probe" in script
    assert "--profile motor" in script
    assert "build rosy-motor" in script
    assert 'source "$ENV_FILE"' not in script
    assert "ROSY_DIALOUT_GID" in script
    assert "stat -c '%g'" in script
    assert ".ping(" in probe
    assert "ADDR_TORQUE_ENABLE" in probe
    assert "read1ByteTxRx" in probe
    assert "write1ByteTxRx" not in probe
    assert "write4ByteTxRx" not in probe


def test_windows_peer_verifier_checks_api_and_dashboard_over_wlan():
    script = _text(WINDOWS_VERIFY)

    assert "ip -4 -o addr show dev wlan0" in script
    assert "Invoke-WebRequest" in script
    assert "/api/v1" in script
    assert "/dashboard" in script
    assert "StrictHostKeyChecking=no" not in script
    assert "Authorization" not in script


def test_shell_scripts_are_lf_only():
    for path in (
        INSTALLER,
        VERIFIER,
        RUNTIME_MODE,
        UART_CONFIG,
        MOTOR_VERIFY,
        DEPLOY / "entrypoint.sh",
    ):
        assert b"\r\n" not in path.read_bytes(), f"CRLF is unsafe in container/Pi shell: {path.name}"


def test_pi_profile_binds_dashboard_to_wifi_reachable_interface():
    config = yaml.safe_load(_text(DEPLOY / "config" / "rosy.pi5.example.yaml"))

    assert config["network"]["api_host"] == "0.0.0.0"
    assert config["network"]["api_port"] == 8080


def test_wifi_runbook_is_linked_from_runtime_guide():
    runbook = ROOT / "docs" / "deployment" / "raspberry-pi-wifi-image.md"
    runtime_guide = _text(ROOT / "docs" / "deployment" / "raspberry-pi-runtime.md")
    readme = _text(ROOT / "README.md")

    assert runbook.is_file()
    assert "raspberry-pi-wifi-image.md" in runtime_guide
    assert "raspberry-pi-wifi-image.md" in readme
    assert "sudoedit /opt/rosy/deploy/robot/.env" in runtime_guide
    assert "sudo install -d -o rosy -g rosy /opt/rosy" not in runtime_guide
    assert "cp .env.example .env" not in runtime_guide
