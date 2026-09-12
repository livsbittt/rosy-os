"""Device installation readback evidence is deterministic and secret-free."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deploy" / "robot" / "device_readback.py"

_TRUSTED_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEA" + "L6hVkPrxqDNolCmMvsuHEw0bEP7vFxHk8I3K3j0LiVY=" +
    "\n-----END PUBLIC KEY-----\n"
)
_UNTRUSTED_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEA" + "YE9UJoRcaYjFVdGxg8yY6ewbzzZ5ZODOuNXpIFlghOM=" +
    "\n-----END PUBLIC KEY-----\n"
)
_VALID_SIGNATURE = "".join((
    "d6LFNVwb6qpKp2KHaPrfN4MqGliIhqoN",
    "aLxqcRqt8oHeP4c0GY2qt2x3aGuFiedJDX",
    "atBSAYaYpabXoXFGoaAA==",
))

SPEC = importlib.util.spec_from_file_location("device_readback", MODULE_PATH)
assert SPEC and SPEC.loader
device_readback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(device_readback)


def _fake_device(tmp_path: Path) -> Path:
    root = tmp_path / "device"
    install = root / "opt" / "rosy"
    (install / "deploy" / "robot").mkdir(parents=True)
    (root / "etc").mkdir(parents=True)
    (root / "proc" / "device-tree").mkdir(parents=True)
    (root / "var" / "lib" / "rosy").mkdir(parents=True)
    (install / "deploy" / "robot" / ".env").write_text(
        "ROSY_ROBOT_NUMBER=3\n"
        "ROS_DOMAIN_ID=43\n"
        "ROSY_NAMESPACE=rosy_03\n"
        "ROSY_RUNTIME_MODE=core\n"
        "ROSY_ADMIN_TOKEN=must-not-appear\n",
        encoding="utf-8",
    )
    (root / "etc" / "hostname").write_text("pinky-03\n", encoding="utf-8")
    (root / "etc" / "os-release").write_text(
        'ID=raspbian\nVERSION_ID="13"\nVERSION_CODENAME=trixie\n',
        encoding="utf-8",
    )
    (root / "proc" / "device-tree" / "model").write_bytes(b"Raspberry Pi 5 Model B Rev 1.0\x00")
    (root / "var" / "lib" / "rosy" / "activation.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "2026.09.13-001",
                "release_path": "/opt/rosy/releases/2026.09.13-001",
                "config_generation": "2026.09.13-001",
                "data_generation": "2026.09.13-001",
                "runtime_mode": "core",
                "activated_at": "2026-09-13T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    release = install / "releases" / "2026.09.13-001"
    release.mkdir(parents=True)
    (release / "SHA256SUMS").write_bytes(b"test\n")
    (release / "SHA256SUMS.sig").write_text(_VALID_SIGNATURE, encoding="utf-8")
    trusted_keys = root / "etc" / "rosy" / "trusted-release-keys"
    trusted_keys.mkdir(parents=True)
    (trusted_keys / "rosy-release-2026-01.pem").write_text(
        _TRUSTED_PUBLIC_KEY, encoding="utf-8"
    )
    (release / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "2026.09.13-001",
                "git_revision": "a" * 40,
                "target": {"board": "raspberry-pi-5", "architecture": "arm64"},
                "containers": {
                    "rosy_core": "sha256:" + "1" * 64,
                    "rosy_io": "sha256:" + "2" * 64,
                },
                "signing_key_id": "rosy-release-2026-01",
            }
        ),
        encoding="utf-8",
    )
    return root


def _runner(command: list[str], *, timeout: float):
    del timeout
    if command == ["dpkg", "--print-architecture"]:
        return subprocess.CompletedProcess(command, 0, "arm64\n", "")
    if command[:3] == ["systemctl", "is-active", "--quiet"]:
        return subprocess.CompletedProcess(command, 0, "", "")
    if command[:2] == ["docker", "compose"] and command[-2:] == ["-q", "rosy-core"]:
        return subprocess.CompletedProcess(command, 0, "core-container\n", "")
    if command[:2] == ["docker", "inspect"]:
        return subprocess.CompletedProcess(
            command,
            0,
            "sha256:container-image\trosy-core@sha256:" + "1" * 64 + "\thealthy\n",
            "",
        )
    if command[:3] == ["docker", "exec", "core-container"]:
        if command[-3:] == ["ros2", "node", "list"]:
            return subprocess.CompletedProcess(command, 0, "/rosy_03/rosy_core\n", "")
        return subprocess.CompletedProcess(command, 0, "Publisher count: 1\n", "")
    return subprocess.CompletedProcess(command, 1, "", "command unavailable")


def test_readback_reports_identity_artifact_runtime_and_ros_graph(tmp_path: Path):
    root = _fake_device(tmp_path)

    evidence = device_readback.collect_readback(root=root, run=_runner)

    assert evidence["schema_version"] == 1
    assert evidence["device"]["hostname"] == "pinky-03"
    assert evidence["device"]["model"].startswith("Raspberry Pi 5")
    assert evidence["identity"] == {
        "robot_number": "3",
        "ros_domain_id": "43",
        "namespace": "rosy_03",
        "runtime_mode": "core",
    }
    assert evidence["artifact"]["git_revision"] == "a" * 40
    assert evidence["artifact"]["containers"]["rosy_core"].startswith("sha256:")
    assert evidence["artifact"]["signature"] == {"status": "verified"}
    assert evidence["runtime"]["core"]["health"] == "healthy"
    assert evidence["runtime"]["core"]["image_match"] == "verified"
    assert evidence["ros_graph"]["nodes"] == ["/rosy_03/rosy_core"]
    assert evidence["ros_graph"]["cmd_vel_publishers"] == 1
    assert evidence["gates"] == {"device_runtime": "GO", "field": "HOLD"}


def test_readback_never_serializes_credentials(tmp_path: Path):
    root = _fake_device(tmp_path)

    encoded = json.dumps(device_readback.collect_readback(root=root, run=_runner))

    assert "must-not-appear" not in encoded
    assert "ROSY_ADMIN_TOKEN" not in encoded


def test_readback_holds_when_immutable_artifact_is_missing(tmp_path: Path):
    root = _fake_device(tmp_path)
    (root / "opt" / "rosy" / "releases" / "2026.09.13-001" / "manifest.json").unlink()

    evidence = device_readback.collect_readback(root=root, run=_runner)

    assert evidence["artifact"] == {"status": "unavailable", "reason": "manifest_missing"}
    assert evidence["gates"] == {
        "device_runtime": "HOLD",
        "field": "HOLD",
    }


def test_readback_holds_when_release_signature_is_missing(tmp_path: Path):
    root = _fake_device(tmp_path)
    (root / "opt" / "rosy" / "releases" / "2026.09.13-001" / "SHA256SUMS.sig").unlink()

    evidence = device_readback.collect_readback(root=root, run=_runner)

    assert evidence["artifact"]["signature"] == {
        "status": "unavailable",
        "reason": "signature_missing",
    }
    assert evidence["gates"]["device_runtime"] == "HOLD"


def test_readback_holds_when_release_signature_is_malformed(tmp_path: Path):
    root = _fake_device(tmp_path)
    sig = root / "opt" / "rosy" / "releases" / "2026.09.13-001" / "SHA256SUMS.sig"
    sig.write_text("not base64", encoding="utf-8")

    evidence = device_readback.collect_readback(root=root, run=_runner)

    assert evidence["artifact"]["signature"]["status"] == "unverified"
    assert evidence["artifact"]["signature"]["reason"] == "SIGNATURE_MALFORMED"
    assert evidence["gates"]["device_runtime"] == "HOLD"


def test_readback_holds_when_trusted_key_does_not_match_signature(tmp_path: Path):
    root = _fake_device(tmp_path)
    key = root / "etc" / "rosy" / "trusted-release-keys" / "rosy-release-2026-01.pem"
    key.write_text(_UNTRUSTED_PUBLIC_KEY, encoding="utf-8")

    evidence = device_readback.collect_readback(root=root, run=_runner)

    assert evidence["artifact"]["signature"]["status"] == "unverified"
    assert evidence["artifact"]["signature"]["reason"] == "SIGNATURE_INVALID"
    assert evidence["gates"]["device_runtime"] == "HOLD"


def test_readback_holds_when_running_image_is_not_the_manifest_digest(tmp_path: Path):
    root = _fake_device(tmp_path)

    def mismatching_runner(command: list[str], *, timeout: float):
        result = _runner(command, timeout=timeout)
        if command[:2] == ["docker", "inspect"]:
            result.stdout = result.stdout.replace("1" * 64, "9" * 64)
        return result

    evidence = device_readback.collect_readback(root=root, run=mismatching_runner)

    assert evidence["runtime"]["core"]["image_match"] == "mismatch"
    assert evidence["gates"]["device_runtime"] == "HOLD"


def test_readback_refuses_activation_path_escape(tmp_path: Path):
    root = _fake_device(tmp_path)
    activation_path = root / "var" / "lib" / "rosy" / "activation.json"
    activation = json.loads(activation_path.read_text(encoding="utf-8"))
    activation["release_path"] = "/opt/rosy/releases/2026.09.13-001/../../etc"
    activation_path.write_text(json.dumps(activation), encoding="utf-8")

    evidence = device_readback.collect_readback(root=root, run=_runner)

    assert evidence["artifact"] == {"status": "unavailable", "reason": "release_path_invalid"}
    assert evidence["gates"]["device_runtime"] == "HOLD"


def test_readback_refuses_non_core_activation(tmp_path: Path):
    root = _fake_device(tmp_path)
    activation_path = root / "var" / "lib" / "rosy" / "activation.json"
    activation = json.loads(activation_path.read_text(encoding="utf-8"))
    activation["runtime_mode"] = "hardware"
    activation_path.write_text(json.dumps(activation), encoding="utf-8")

    evidence = device_readback.collect_readback(root=root, run=_runner)

    assert evidence["activation"] == {
        "status": "unavailable",
        "reason": "activation_runtime_mode_not_core",
    }
    assert evidence["gates"]["device_runtime"] == "HOLD"


def test_installer_and_wrapper_expose_the_same_readback_command():
    wrapper = (ROOT / "deploy" / "robot" / "device-readback.sh").read_text(encoding="utf-8")
    installer = (ROOT / "deploy" / "robot" / "install-pi.sh").read_text(encoding="utf-8")
    verifier = (ROOT / "deploy" / "robot" / "verify-pi.sh").read_text(encoding="utf-8")

    assert 'exec python3 "$SCRIPT_DIR/device_readback.py" "$@"' in wrapper
    assert '"$INSTALL_ROOT/deploy/robot/device-readback.sh"' in installer
    assert "device-readback.sh --json" in verifier
