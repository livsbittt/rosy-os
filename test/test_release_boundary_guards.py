"""Privilege- and secret-boundary guards for the ROSY OS release contract.

Two boundaries in the image/release design are cheap to state and expensive
to lose:

* CORE is the robot API, not a host administrator. It must not own ``/dev``
  devices, the Docker socket, or host root (design sections 2.13, 4.2, 12.1).
  A future Host Agent gets those responsibilities as a separate least-
  privilege process.
* Nothing that ships carries a secret — no shared password, no shared API
  token, no Wi-Fi PSK, no SSH private key (design sections 2.7, 12.1, 12.2).

Today's ``compose.yaml`` already satisfies the first. These tests exist to
keep it that way: the boundary is one convenience mount away from being gone,
and the loss would not be obvious in review.

``test_robot_runtime.py`` also asserts parts of this, but by exact string
(``"/var/run/docker.sock:/var/run/docker.sock" not in mounts``). That form
passes the moment someone writes the same mount with a ``:ro`` suffix or via
``/run/docker.sock``. The checks here are structural instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from secret_scan import iter_tracked_files, scan_files, scan_text  # via test/conftest.py

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "robot" / "compose.yaml"
ENV_EXAMPLE = ROOT / "deploy" / "robot" / ".env.example"
RUNTIME_MODE = ROOT / "deploy" / "robot" / "runtime-mode.sh"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def core(compose: dict) -> dict:
    return compose["services"]["rosy-core"]


def _host_side(mount: str) -> str:
    """The host path of a ``host:container[:mode]`` bind."""
    return mount.split(":", 1)[0]


def _container_side(mount: str) -> str:
    parts = mount.split(":")
    return parts[1] if len(parts) > 1 else ""


# --- CORE privilege boundary ---------------------------------------------


def test_core_owns_no_devices(core):
    assert "devices" not in core, "CORE must not be handed /dev nodes"
    assert "device_cgroup_rules" not in core


def test_core_is_not_privileged(core):
    assert core.get("privileged", False) is False
    assert "cap_add" not in core, "CORE must not add capabilities back"


def test_core_drops_all_capabilities(core):
    assert core["cap_drop"] == ["ALL"]


def test_core_forbids_privilege_escalation(core):
    security_opt = core["security_opt"]
    assert "no-new-privileges:true" in security_opt
    # Unconfining seccomp or AppArmor would undo the rest of the boundary.
    for option in security_opt:
        assert "unconfined" not in option, f"CORE relaxes confinement: {option}"


def test_core_filesystem_is_read_only(core):
    assert core["read_only"] is True


def test_core_never_receives_a_container_runtime_socket(core):
    """Structural, not exact-string: any docker/podman socket in any form."""
    for mount in core.get("volumes", []):
        host = _host_side(mount)
        assert "docker.sock" not in host, f"CORE gets the Docker socket: {mount}"
        assert "podman.sock" not in host, f"CORE gets the Podman socket: {mount}"
        assert "containerd" not in host, f"CORE gets a containerd socket: {mount}"


def test_core_never_receives_host_root(core):
    """Any bind whose host side is / — with or without a :ro suffix."""
    for mount in core.get("volumes", []):
        host = _host_side(mount)
        assert host != "/", f"CORE gets host root: {mount}"
        container = _container_side(mount)
        assert container not in {"/", "/host/root", "/rootfs"}, (
            f"CORE mounts something as a root filesystem: {mount}"
        )


def test_core_host_telemetry_is_read_only(core):
    """The host paths CORE may read are telemetry, and read-only at that."""
    for mount in core.get("volumes", []):
        host = _host_side(mount)
        if not host.startswith(("/proc", "/sys", "/etc", "/dev", "/var/run", "/run")):
            continue  # a ROSY data/config bind, covered below
        assert mount.endswith(":ro"), f"host path mounted writable into CORE: {mount}"


def test_core_joins_no_extra_host_groups(core):
    """group_add is how a container gets dialout (UART) without a device."""
    assert "group_add" not in core, "CORE must not join host groups such as dialout"


def test_core_does_not_share_host_namespaces(core):
    for key in ("pid", "ipc", "userns_mode", "cgroup"):
        value = core.get(key)
        assert value != "host", f"CORE shares the host {key} namespace"


def test_core_runs_as_a_non_root_user(core):
    user = core["user"]
    assert not user.startswith("0:"), "CORE must not run as uid 0"
    assert user == "${ROSY_UID:-1000}:${ROSY_GID:-1000}"


# --- default runtime mode is core-only -----------------------------------


def test_hardware_services_are_gated_behind_compose_profiles(compose):
    """A plain `docker compose up` must start CORE and nothing else."""
    services = compose["services"]
    assert services["rosy-motor"]["profiles"] == ["motor"]
    assert services["rosy-io"]["profiles"] == ["hardware"]
    assert "profiles" not in services["rosy-core"], "CORE is the default service"


def test_declared_default_runtime_mode_is_core():
    assert "ROSY_RUNTIME_MODE=core" in ENV_EXAMPLE.read_text(encoding="utf-8")


def test_runtime_mode_wrapper_falls_back_to_core():
    script = RUNTIME_MODE.read_text(encoding="utf-8")
    assert 'MODE="${ROSY_RUNTIME_MODE:-core}"' in script
    assert 'MODE="${configured_mode:-core}"' in script, (
        "an empty ROSY_RUNTIME_MODE in .env must still mean core, not hardware"
    )


# --- no shipped secrets ---------------------------------------------------


def test_no_secrets_in_tracked_files():
    findings = scan_files(iter_tracked_files(ROOT), root=ROOT)
    assert not findings, "secrets found in tracked files:\n" + "\n".join(
        str(f) for f in findings
    )


PLANTED = """\
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
-----END OPENSSH PRIVATE KEY-----
wifi_password: hunter2swordfish
psk=SuperSecretSitePsk99
ROSY_API_TOKEN=deadbeefcafebabe0123456789abcdef01234567
"""

PLACEHOLDERS = """\
wifi_password: <your-wifi-password>
psk=${ROSY_WIFI_PSK}
api_token = "CHANGE_ME"
admin_password: REPLACE_ME
def authenticate(config: dict, bearer: Optional[str]) -> AuthContext:
image digest sha256: a3f9c2e81b7d4056af92e310cb77aa019283746511223344556677889900aabb
docs: https://www.raspberrypi.com/documentation/computers/configuration-and-networking
"""


def test_scanner_detects_planted_secrets():
    """Proof the repository check above is not vacuously green."""
    findings = scan_text("planted.txt", PLANTED)
    kinds = {f.kind for f in findings}
    assert "private-key" in kinds
    assert "wifi-psk" in kinds
    assert "credential" in kinds
    assert len(findings) >= 4


@pytest.mark.parametrize(
    "kind,sample",
    [
        ("private-key", "-----BEGIN RSA PRIVATE KEY-----"),
        ("private-key", "-----BEGIN EC PRIVATE KEY-----"),
        ("wifi-psk", "psk=NotAPlaceholderValue1"),
        ("wifi-psk", "wifi_passphrase: correcthorsebattery"),
        ("credential", 'api_key = "sk_live_9182aeb27c4d"'),
        ("credential", "ADMIN_PASSWORD=Tr0ub4dor3xyz"),
    ],
)
def test_scanner_detects_each_secret_shape(kind, sample):
    findings = scan_text("sample.txt", sample)
    assert findings, f"scanner missed {kind}: {sample!r}"
    assert findings[0].kind == kind


def test_scanner_ignores_placeholders_and_public_data():
    """False positives train people to ignore the scanner."""
    findings = scan_text("placeholders.txt", PLACEHOLDERS)
    assert not findings, "scanner flagged placeholders:\n" + "\n".join(
        str(f) for f in findings
    )
