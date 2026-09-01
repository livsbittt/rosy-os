"""Static safety contracts for headless Raspberry Pi Wi-Fi deployment."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "robot"
INSTALLER = DEPLOY / "install-pi.sh"
VERIFIER = DEPLOY / "verify-pi.sh"
RUNTIME_MODE = DEPLOY / "runtime-mode.sh"
WINDOWS_DEPLOY = DEPLOY / "deploy-from-windows.ps1"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_deployment_kit_files_exist():
    for path in (INSTALLER, VERIFIER, RUNTIME_MODE, WINDOWS_DEPLOY):
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


def test_installer_guards_destructive_paths_and_activates_systemd():
    script = _text(INSTALLER)

    assert '[[ "$INSTALL_ROOT" == "/opt/rosy" ]]' in script
    assert '[[ "$ROSY_CONFIG" == "/etc/rosy/rosy.yaml" ]]' in script
    assert '[[ "$ROSY_DATA" == "/var/lib/rosy" ]]' in script
    assert "umask 077" in script
    assert "systemctl enable --now rosy-runtime.service" in script


def test_runtime_defaults_to_core_only_and_rejects_unknown_modes():
    environment = _text(DEPLOY / ".env.example")
    wrapper = _text(RUNTIME_MODE)
    unit = _text(DEPLOY / "rosy-runtime.service")

    assert "ROSY_RUNTIME_MODE=core" in environment
    assert '${ROSY_RUNTIME_MODE:-core}' in wrapper
    assert '"core"|"hardware")' in wrapper
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


def test_shell_scripts_are_lf_only():
    for path in (INSTALLER, VERIFIER, RUNTIME_MODE, DEPLOY / "entrypoint.sh"):
        assert b"\r\n" not in path.read_bytes(), f"CRLF is unsafe in container/Pi shell: {path.name}"


def test_pi_profile_binds_dashboard_to_wifi_reachable_interface():
    config = yaml.safe_load(_text(DEPLOY / "config" / "rosy.pi5.example.yaml"))

    assert config["network"]["api_host"] == "0.0.0.0"
    assert config["network"]["api_port"] == 8080


def test_wifi_runbook_is_linked_from_runtime_guide():
    runbook = ROOT / "docs" / "deployment" / "raspberry-pi-wifi-image.md"
    runtime_guide = _text(ROOT / "docs" / "deployment" / "raspberry-pi-runtime.md")

    assert runbook.is_file()
    assert "raspberry-pi-wifi-image.md" in runtime_guide
