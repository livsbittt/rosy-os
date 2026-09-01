from __future__ import annotations

from pathlib import Path
import socket

import pytest

from rosy_core.system.runtime import HostRuntimeProbe


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _host_tree(root: Path) -> None:
    _write(
        root,
        "etc/os-release",
        'PRETTY_NAME="Raspberry Pi OS 13 (trixie)"\nNAME="Raspberry Pi OS"\nVERSION_ID="13"\n',
    )
    _write(root, "etc/hostname", "rosy-pi\n")
    _write(root, "proc/uptime", "93784.25 123.0\n")
    _write(root, "proc/loadavg", "0.18 0.11 0.07 1/234 567\n")
    _write(root, "proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
    _write(
        root,
        "proc/meminfo",
        "MemTotal:        8192000 kB\nMemAvailable:   6144000 kB\n",
    )
    _write(root, "sys/class/thermal/thermal_zone0/temp", "52250\n")


def test_snapshot_reads_raspberry_pi_host_metrics(tmp_path):
    _host_tree(tmp_path)
    data_path = tmp_path / "data"
    data_path.mkdir()
    probe = HostRuntimeProbe(
        host_root=tmp_path,
        data_path=data_path,
        address_resolver=lambda _hostname: ["192.168.0.42"],
    )

    first = probe.snapshot()
    _write(tmp_path, "proc/stat", "cpu  150 0 150 900 0 0 0 0 0 0\n")
    second = probe.snapshot()

    assert first["source"] == "host"
    assert first["os"] == {
        "name": "Raspberry Pi OS",
        "version": "13",
        "pretty_name": "Raspberry Pi OS 13 (trixie)",
    }
    assert first["hostname"] == "rosy-pi"
    assert first["uptime_seconds"] == pytest.approx(93784.25)
    assert first["cpu"]["usage_percent"] is None
    assert second["cpu"]["usage_percent"] == pytest.approx(50.0)
    assert second["cpu"]["load_1"] == pytest.approx(0.18)
    assert second["memory"]["total_bytes"] == 8192000 * 1024
    assert second["memory"]["available_bytes"] == 6144000 * 1024
    assert second["memory"]["used_percent"] == pytest.approx(25.0)
    assert second["temperature_c"] == pytest.approx(52.25)
    assert second["network"]["addresses"] == ["192.168.0.42"]
    assert second["storage"]["path"] == str(data_path)
    assert "collected_at" in second


def test_snapshot_degrades_to_null_when_host_files_are_missing(tmp_path):
    data_path = tmp_path / "data"
    data_path.mkdir()
    probe = HostRuntimeProbe(
        host_root=tmp_path,
        data_path=data_path,
        address_resolver=lambda _hostname: [],
    )

    snapshot = probe.snapshot()

    assert snapshot["os"]["pretty_name"] is None
    assert snapshot["uptime_seconds"] is None
    assert snapshot["cpu"]["usage_percent"] is None
    assert snapshot["memory"]["used_percent"] is None
    assert snapshot["temperature_c"] is None
    assert snapshot["network"]["addresses"] == []
    assert set(snapshot["unavailable"]) >= {
        "os_release",
        "hostname",
        "uptime",
        "load",
        "cpu",
        "memory",
        "temperature",
    }


def test_snapshot_does_not_expose_process_environment(tmp_path, monkeypatch):
    _host_tree(tmp_path)
    data_path = tmp_path / "data"
    data_path.mkdir()
    monkeypatch.setenv("ROSY_ADMIN_TOKEN", "must-not-leak")
    probe = HostRuntimeProbe(host_root=tmp_path, data_path=data_path)

    snapshot_text = repr(probe.snapshot())

    assert "ROSY_ADMIN_TOKEN" not in snapshot_text
    assert "must-not-leak" not in snapshot_text


def test_default_address_lookup_uses_routes_without_hostname_dns(monkeypatch):
    class FakeSocket:
        def __init__(self, family, _kind):
            self.family = family

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def connect(self, _target):
            return None

        def getsockname(self):
            if self.family == socket.AF_INET:
                return ("192.168.0.42", 54321)
            return ("2001:db8::42", 54321, 0, 0)

    def fail_dns(*_args, **_kwargs):
        raise AssertionError("hostname DNS must not block runtime telemetry")

    monkeypatch.setattr(socket, "socket", FakeSocket)
    monkeypatch.setattr(socket, "getaddrinfo", fail_dns)

    assert HostRuntimeProbe._resolve_addresses("unresolvable-host") == [
        "192.168.0.42",
        "2001:db8::42",
    ]
