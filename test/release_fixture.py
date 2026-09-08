"""Small, genuinely signed bundles; no real robot data or release keys."""
import json
import subprocess
import tarfile
from pathlib import Path

from signing import build_sha256sums, sha256_file, sign_checksums


def signed_tree(tmp_path: Path, release_id="2026.09.08-001"):
    root = tmp_path / release_id
    root.mkdir(parents=True)
    keys = tmp_path / "keys"
    keys.mkdir(exist_ok=True)
    private, public = keys / "test.key", keys / "rosy-test-key.pem"
    if not private.exists():
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(private)],
                       check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                       check=True, capture_output=True)
    for name, content in {
        "runtime/compose.yaml": b"services: {}\n",
        "images/rosy-core.oci.tar": b"fake core archive, runtime port is injected",
        "images/rosy-io.oci.tar": b"fake io archive, runtime port is injected",
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = {
        "schema_version": 1, "release_id": release_id, "git_revision": "a" * 40,
        "created_at": "2026-09-08T00:00:00Z",
        "target": {"board": "raspberry-pi-5", "architecture": "arm64",
                   "os_family": "raspberry-pi-os-lite", "os_suite": "trixie"},
        "runtime": {"config_schema": 1, "data_schema": 1, "minimum_bootloader": None},
        "containers": {"rosy_core": "sha256:" + "a" * 64, "rosy_io": "sha256:" + "b" * 64},
        "defaults": {"runtime_mode": "core"}, "signing_key_id": "rosy-test-key",
        "requires_recommissioning": True,
        "files": [{"path": p.relative_to(root).as_posix(), "sha256": sha256_file(p)}
                  for p in sorted(root.rglob("*")) if p.is_file()],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    resign(root, private)
    return root, public, private


def resign(root, private):
    paths = [p.relative_to(root).as_posix() for p in sorted(root.rglob("*"))
             if p.is_file() and p.name not in {"SHA256SUMS", "SHA256SUMS.sig"}]
    sums = build_sha256sums(root, paths)
    (root / "SHA256SUMS").write_bytes(sums)
    (root / "SHA256SUMS.sig").write_text(sign_checksums(sums, private), encoding="utf-8")


def archive(root, destination):
    with tarfile.open(destination, "w") as tar:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(root).as_posix())
    return destination
