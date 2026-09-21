from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "sd" / "prepare-rosy-sd.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def _disk(**overrides):
    disk = {
        "Number": 7,
        "FriendlyName": "Fixture USB SD Reader",
        "SerialNumber": "FIXTURE-SD-0007",
        "Size": 32 * 1024**3,
        "BusType": "USB",
        "IsBoot": False,
        "IsSystem": False,
        "IsOffline": False,
        "IsReadOnly": False,
    }
    disk.update(overrides)
    return disk


@pytest.fixture
def writer_case(tmp_path: Path):
    image = tmp_path / "rosy.img"
    image.write_bytes(b"fixture rosy image\n")
    signature = tmp_path / "rosy.img.sig"
    signature.write_text("fixture detached signature\n", encoding="utf-8")
    inventory = tmp_path / "disks.json"
    inventory.write_text(json.dumps([_disk()]), encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"robot_numbers": [], "device_names": [], "device_uids": []}),
        encoding="utf-8",
    )
    marker = tmp_path / "writer-called.txt"
    fake_writer = tmp_path / "fake-writer.ps1"
    fake_writer.write_text(
        f"Set-Content -LiteralPath '{marker}' -Value called\nexit 0\n",
        encoding="utf-8",
    )
    local_app_data = tmp_path / "local-app-data"
    credential_dir = local_app_data / "Rosy" / "credentials"
    credential_dir.mkdir(parents=True)
    credential = credential_dir / "fixture-profile.credential.xml"
    command = (
        "$s=ConvertTo-SecureString ('fixture-'+'writer-pass') -AsPlainText -Force;"
        "$c=[pscredential]::new('fixture-ssid',$s);"
        f"$c|Export-Clixml -LiteralPath '{credential}'"
    )
    subprocess.run([POWERSHELL, "-NoProfile", "-Command", command], check=True)
    return {
        "image": image,
        "signature": signature,
        "inventory": inventory,
        "registry": registry,
        "marker": marker,
        "writer": fake_writer,
        "receipt": tmp_path / "receipt.json",
        "env": {**os.environ, "LOCALAPPDATA": str(local_app_data)},
    }


def _run(case, *extra, plan_only=True):
    command = [
        POWERSHELL,
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(SCRIPT),
        "-DiskNumber", "7",
        "-RobotNumber", "1",
        "-Model", "pinky_pro",
        "-Preset", "hardware",
        "-WifiProfile", "fixture-profile",
        "-ImagePath", str(case["image"]),
        "-ImageSha256", hashlib.sha256(case["image"].read_bytes()).hexdigest(),
        "-ImageSignaturePath", str(case["signature"]),
        "-ReleaseId", "2026.09.21-001",
        "-FleetEndpoint", "https://fleet.fixture.invalid:8443",
        "-FleetTrustProfile", "site-ca-2026",
        "-DiskInventoryJson", str(case["inventory"]),
        "-RegistryJson", str(case["registry"]),
        "-ReceiptPath", str(case["receipt"]),
        "-RpiImager", str(case["writer"]),
        "-DeviceName", "rosy-pinky-k7m4",
        "-DeviceUid", "9d40feaa-871f-4fd3-975a-a704e82d3af9",
    ]
    if plan_only:
        command.append("-PlanOnly")
    extra_values = list(map(str, extra))
    index = 0
    while index < len(extra_values):
        name = extra_values[index]
        value = extra_values[index + 1]
        if name in command:
            command[command.index(name) + 1] = value
        else:
            command.extend((name, value))
        index += 2
    return subprocess.run(command, capture_output=True, text=True, env=case["env"])


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_plan_only_prints_a_redacted_physical_disk_plan(writer_case):
    completed = _run(writer_case)

    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["physical_drive"] == r"\\.\PhysicalDrive7"
    assert plan["device_name"] == "rosy-pinky-k7m4"
    assert plan["mode"] == "PLAN_ONLY"
    assert "writer-pass" not in completed.stdout + completed.stderr
    assert not writer_case["marker"].exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize(
    "change",
    [
        {"IsBoot": True},
        {"IsSystem": True},
        {"BusType": "SATA"},
        {"IsOffline": True},
        {"IsReadOnly": True},
        {"Size": 4 * 1024**3},
        {"SerialNumber": ""},
    ],
)
def test_unsafe_disk_is_rejected_without_invoking_writer(writer_case, change):
    writer_case["inventory"].write_text(json.dumps([_disk(**change)]), encoding="utf-8")

    completed = _run(writer_case)

    assert completed.returncode != 0
    assert not writer_case["marker"].exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_disk_drift_between_probes_is_rejected(writer_case, tmp_path):
    second = tmp_path / "second.json"
    second.write_text(json.dumps([_disk(SerialNumber="CHANGED-SERIAL")]), encoding="utf-8")

    completed = _run(writer_case, "-SecondDiskInventoryJson", second)

    assert completed.returncode != 0
    assert "changed between safety probes" in completed.stderr
    assert not writer_case["marker"].exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize(
    ("field", "value"),
    [("robot_numbers", [1]), ("device_names", ["rosy-pinky-k7m4"]),
     ("device_uids", ["9d40feaa-871f-4fd3-975a-a704e82d3af9"])],
)
def test_registry_reuse_is_rejected(writer_case, field, value):
    registry = {"robot_numbers": [], "device_names": [], "device_uids": []}
    registry[field] = value
    writer_case["registry"].write_text(json.dumps(registry), encoding="utf-8")

    completed = _run(writer_case)

    assert completed.returncode != 0
    assert not writer_case["marker"].exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize("missing", ["hash", "signature"])
def test_image_integrity_companions_are_required(writer_case, missing):
    if missing == "signature":
        writer_case["signature"].unlink()
        completed = _run(writer_case)
    else:
        completed = _run(writer_case, "-ImageSha256", "invalid")

    assert completed.returncode != 0
    assert not writer_case["marker"].exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_existing_receipt_is_never_overwritten(writer_case):
    writer_case["receipt"].write_text("existing evidence\n", encoding="utf-8")

    completed = _run(writer_case)

    assert completed.returncode != 0
    assert not writer_case["marker"].exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_wrong_confirmation_never_invokes_writer(writer_case):
    completed = _run(
        writer_case,
        "-Confirmation", "ERASE DISK 7 rosy-pinky-wrong",
        plan_only=False,
    )

    assert completed.returncode != 0
    assert "confirmation did not match" in completed.stderr
    assert not writer_case["marker"].exists()


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
def test_successful_write_stages_one_time_bundle_and_updates_registry(writer_case, tmp_path):
    boot = tmp_path / "boot"
    boot.mkdir()
    completed = _run(
        writer_case,
        "-Confirmation", "ERASE DISK 7 rosy-pinky-k7m4",
        "-BootMountPath", boot,
        plan_only=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert writer_case["marker"].exists()
    bundle_path = boot / "rosy-provision" / "provision.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8-sig"))
    assert bundle["device_identity"]["device_name"] == "rosy-pinky-k7m4"
    assert bundle["network"]["ssid"] == "fixture-ssid"
    assert len(bundle["network"]["wpa_psk"]) == 64
    receipt = json.loads(writer_case["receipt"].read_text(encoding="utf-8-sig"))
    registry = json.loads(writer_case["registry"].read_text(encoding="utf-8-sig"))
    rendered = completed.stdout + completed.stderr + json.dumps(receipt)
    assert "fixture-writer-pass" not in rendered
    assert "wpa_psk" not in json.dumps(receipt)
    assert registry["robot_numbers"] == [1]
    assert registry["device_names"] == ["rosy-pinky-k7m4"]
    assert registry["device_uids"] == ["9d40feaa-871f-4fd3-975a-a704e82d3af9"]


def test_script_has_no_plain_password_or_shell_string_escape_hatch():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "WifiPassword" not in text
    assert "Export-Clixml" in text and "Import-Clixml" in text
    assert "Read-Host -AsSecureString" in text
    assert "--cli" in text and "--sha256" in text
    assert "--disable-verify" not in text
    assert "cmd /c" not in text.lower()
    assert '"ERASE DISK $DiskNumber $DeviceName"' in text
    assert "& $RpiImager" in text
    assert "create-provision-bundle.py" in text
    assert "BootMountPath" in text
    assert "GetNetworkCredential().Password" in text
