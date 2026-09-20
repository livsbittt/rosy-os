from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

import import_unsigned_payload as importer
from import_unsigned_payload import HandoffError, import_handoff


RELEASE_ID = "2026.09.21-001"
REVISION = "3" * 40
KEY_ID = "rosy-release-2026-01"
ROS_IMAGE = "ros:jazzy-ros-base@sha256:" + "a" * 64


def _add_bytes(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    member.mode = 0o644
    archive.addfile(member, io.BytesIO(content))


def _docker_archive(path: Path, *, architecture: str = "arm64") -> str:
    config = json.dumps(
        {"architecture": architecture, "os": "linux", "comment": path.stem},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(config).hexdigest()
    config_name = f"blobs/sha256/{digest}"
    docker_manifest = json.dumps(
        [{"Config": config_name, "RepoTags": [], "Layers": []}],
        separators=(",", ":"),
    ).encode()
    with tarfile.open(path, "w") as archive:
        _add_bytes(archive, "manifest.json", docker_manifest)
        _add_bytes(archive, config_name, config)
    return f"sha256:{digest}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _handoff(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    payload = source / "rosy-unsigned-payload"
    (payload / "images").mkdir(parents=True)
    (payload / "runtime").mkdir()
    (payload / "runtime" / "compose.yaml").write_text(
        "services: {}\n", encoding="utf-8"
    )
    core_id = _docker_archive(payload / "images" / "rosy-core.oci.tar")
    io_id = _docker_archive(payload / "images" / "rosy-io.oci.tar")
    provenance = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "source_revision": REVISION,
        "created_at": "2026-09-21T00:00:00Z",
        "build_architecture": "arm64",
        "docker_version": "29.7.2",
        "ros_base_image": ROS_IMAGE,
        "images": {
            "rosy_core": {"tag": "local/rosy-core:test", "image_id": core_id},
            "rosy_io": {"tag": "local/rosy-io:test", "image_id": io_id},
        },
    }
    (payload / "build-provenance.json").write_text(
        json.dumps(provenance), encoding="utf-8"
    )
    files = [
        {
            "path": path.relative_to(payload).as_posix(),
            "sha256": _sha256(path),
        }
        for path in sorted(payload.rglob("*"))
        if path.is_file()
    ]
    manifest = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "git_revision": REVISION,
        "created_at": "2026-09-21T00:00:00Z",
        "target": {
            "board": "raspberry-pi-5",
            "architecture": "arm64",
            "os_family": "raspberry-pi-os-lite",
            "os_suite": "trixie",
        },
        "runtime": {
            "config_schema": 1,
            "data_schema": 1,
            "minimum_bootloader": None,
        },
        "containers": {"rosy_core": core_id, "rosy_io": io_id},
        "defaults": {"runtime_mode": "core"},
        "signing_key_id": KEY_ID,
        "requires_recommissioning": True,
        "files": files,
    }
    (payload / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (source / "arm64-builder.json").write_text(
        json.dumps(
            {
                "ok": True,
                "output": "/tmp/rosy-unsigned-payload",
                "release_id": RELEASE_ID,
                "git_revision": REVISION,
                "signed": False,
            }
        ),
        encoding="utf-8",
    )
    archive_path = tmp_path / f"rosy-unsigned-{RELEASE_ID}-{REVISION}.tar.zst"
    with tarfile.open(archive_path, "w") as archive:
        archive.add(payload, arcname="rosy-unsigned-payload")
        archive.add(
            source / "arm64-builder.json", arcname="arm64-builder.json"
        )
    checksum_path = Path(f"{archive_path}.sha256")
    checksum_path.write_text(
        f"{_sha256(archive_path)}  {archive_path.name}\n", encoding="ascii"
    )
    return archive_path, checksum_path


def _copy_decompressor(source: Path, destination: Path) -> None:
    shutil.copyfile(source, destination)


def _rewrite_checksum(archive: Path, checksum: Path) -> None:
    checksum.write_text(
        f"{_sha256(archive)}  {archive.name}\n", encoding="ascii"
    )


def _repack_source(archive: Path, checksum: Path) -> None:
    source = archive.parent / "source"
    archive.unlink()
    with tarfile.open(archive, "w") as handoff:
        handoff.add(
            source / "rosy-unsigned-payload",
            arcname="rosy-unsigned-payload",
        )
        handoff.add(
            source / "arm64-builder.json", arcname="arm64-builder.json"
        )
    _rewrite_checksum(archive, checksum)


def _refresh_manifest_files(payload: Path) -> None:
    manifest_path = payload / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = [
        {"path": path.relative_to(payload).as_posix(), "sha256": _sha256(path)}
        for path in sorted(payload.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _assert_failed_cleanly(tmp_path: Path, output: Path) -> None:
    assert not output.exists()
    assert not list(tmp_path.glob(f".{output.name}.*"))


def _append_member(
    archive: Path,
    checksum: Path,
    name: str,
    *,
    kind: bytes = tarfile.REGTYPE,
    linkname: str = "",
) -> None:
    with tarfile.open(archive, "a") as handoff:
        member = tarfile.TarInfo(name)
        member.type = kind
        member.linkname = linkname
        if kind == tarfile.REGTYPE:
            member.size = 1
            handoff.addfile(member, io.BytesIO(b"x"))
        else:
            handoff.addfile(member)
    _rewrite_checksum(archive, checksum)


def _import(archive: Path, checksum: Path, output: Path) -> dict:
    return import_handoff(
        archive,
        checksum,
        output,
        expected_release_id=RELEASE_ID,
        expected_revision=REVISION,
        expected_signing_key_id=KEY_ID,
        decompressor=_copy_decompressor,
    )


def test_imports_verified_arm64_handoff(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"

    report = _import(archive, checksum, output)

    assert report == {
        "ok": True,
        "output": str(output.resolve()),
        "release_id": RELEASE_ID,
        "git_revision": REVISION,
        "signing_key_id": KEY_ID,
        "signed": False,
        "files_verified": 4,
        "images": {"rosy_core": "linux/arm64", "rosy_io": "linux/arm64"},
    }
    assert (output / "rosy-unsigned-payload" / "manifest.json").is_file()
    assert (output / "arm64-builder.json").is_file()


def test_rejects_outer_checksum_tampering_before_decompression(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    archive.write_bytes(archive.read_bytes() + b"tampered")

    with pytest.raises(HandoffError, match="CHECKSUM_MISMATCH"):
        _import(archive, checksum, output)

    assert not output.exists()


@pytest.mark.parametrize(
    "name,kind,linkname,code",
    [
        ("../escape", tarfile.REGTYPE, "", "ARCHIVE_PATH"),
        ("/absolute", tarfile.REGTYPE, "", "ARCHIVE_PATH"),
        ("rosy-unsigned-payload\\escape", tarfile.REGTYPE, "", "ARCHIVE_PATH"),
        (
            "rosy-unsigned-payload/link",
            tarfile.SYMTYPE,
            "manifest.json",
            "ARCHIVE_TYPE",
        ),
        (
            "rosy-unsigned-payload/hard",
            tarfile.LNKTYPE,
            "manifest.json",
            "ARCHIVE_TYPE",
        ),
        ("rosy-unsigned-payload/fifo", tarfile.FIFOTYPE, "", "ARCHIVE_TYPE"),
        ("unexpected.txt", tarfile.REGTYPE, "", "ARCHIVE_LAYOUT"),
    ],
)
def test_rejects_unsafe_archive_members(tmp_path, name, kind, linkname, code):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    _append_member(archive, checksum, name, kind=kind, linkname=linkname)

    with pytest.raises(HandoffError, match=code):
        _import(archive, checksum, output)

    assert not output.exists()
    assert not (tmp_path / "escape").exists()


def test_rejects_duplicate_archive_member_names(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    _append_member(archive, checksum, "arm64-builder.json")

    with pytest.raises(HandoffError, match="ARCHIVE_DUPLICATE"):
        _import(archive, checksum, output)

    assert not output.exists()


def test_rejects_archive_member_count_limit(tmp_path, monkeypatch):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    monkeypatch.setattr(importer, "MAX_ARCHIVE_MEMBERS", 1)

    with pytest.raises(HandoffError, match="ARCHIVE_LIMIT"):
        _import(archive, checksum, output)

    assert not output.exists()


def test_rejects_archive_expanded_size_limit(tmp_path, monkeypatch):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    monkeypatch.setattr(importer, "MAX_EXPANDED_BYTES", 1)

    with pytest.raises(HandoffError, match="ARCHIVE_LIMIT"):
        _import(archive, checksum, output)

    assert not output.exists()


def test_refuses_to_replace_existing_output(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    output.mkdir()
    marker = output / "operator-data"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(HandoffError, match="OUTPUT_EXISTS"):
        _import(archive, checksum, output)

    assert marker.read_text(encoding="utf-8") == "keep"


def test_requires_canonical_archive_filename(tmp_path):
    archive, checksum = _handoff(tmp_path)
    renamed = tmp_path / "unsigned-payload.tar.zst"
    archive.rename(renamed)
    checksum = tmp_path / "unsigned-payload.tar.zst.sha256"
    _rewrite_checksum(renamed, checksum)

    with pytest.raises(HandoffError, match="ARCHIVE_IDENTITY"):
        _import(renamed, checksum, tmp_path / "verified-handoff")


def test_rejects_builder_unknown_fields(tmp_path):
    archive, checksum = _handoff(tmp_path)
    builder_path = tmp_path / "source" / "arm64-builder.json"
    builder = json.loads(builder_path.read_text(encoding="utf-8"))
    builder["trusted"] = True
    builder_path.write_text(json.dumps(builder), encoding="utf-8")
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="BUILDER_SCHEMA"):
        _import(archive, checksum, tmp_path / "verified-handoff")


def test_rejects_relative_builder_output(tmp_path):
    archive, checksum = _handoff(tmp_path)
    builder_path = tmp_path / "source" / "arm64-builder.json"
    builder = json.loads(builder_path.read_text(encoding="utf-8"))
    builder["output"] = "relative/payload"
    builder_path.write_text(json.dumps(builder), encoding="utf-8")
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="BUILDER_SCHEMA"):
        _import(archive, checksum, tmp_path / "verified-handoff")


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("created_at", "2026-09-22T00:00:00Z"),
        ("ros_base_image", "ros:jazzy-ros-base@sha256:" + "g" * 64),
        ("docker_version", ""),
    ],
)
def test_rejects_invalid_provenance_identity(tmp_path, field, value):
    archive, checksum = _handoff(tmp_path)
    payload = tmp_path / "source" / "rosy-unsigned-payload"
    provenance_path = payload / "build-provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance[field] = value
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    _refresh_manifest_files(payload)
    _repack_source(archive, checksum)

    with pytest.raises(
        HandoffError, match="PROVENANCE_(IDENTITY|BASE|SCHEMA)"
    ):
        _import(archive, checksum, tmp_path / "verified-handoff")


def test_rejects_builder_identity_mismatch(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    builder_path = tmp_path / "source" / "arm64-builder.json"
    builder = json.loads(builder_path.read_text(encoding="utf-8"))
    builder["git_revision"] = "4" * 40
    builder_path.write_text(json.dumps(builder), encoding="utf-8")
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="BUILDER_IDENTITY"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


@pytest.mark.parametrize(
    "field,value",
    [("release_id", "2026.09.21-999"), ("git_revision", "4" * 40),
     ("signing_key_id", "rosy-release-2099-99")],
)
def test_rejects_manifest_identity_mismatch(tmp_path, field, value):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    manifest_path = (
        tmp_path / "source" / "rosy-unsigned-payload" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="MANIFEST_IDENTITY"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


def test_rejects_signing_files_in_unsigned_handoff(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    payload = tmp_path / "source" / "rosy-unsigned-payload"
    (payload / "SHA256SUMS").write_text("not trusted\n", encoding="utf-8")
    (payload / "SHA256SUMS.sig").write_text("not trusted\n", encoding="utf-8")
    _refresh_manifest_files(payload)
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="UNEXPECTED_SIGNATURE"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


@pytest.mark.parametrize("change", ["undeclared", "missing", "tampered"])
def test_rejects_payload_set_or_digest_changes(tmp_path, change):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    payload = tmp_path / "source" / "rosy-unsigned-payload"
    runtime = payload / "runtime" / "compose.yaml"
    if change == "undeclared":
        (payload / "runtime" / "extra.txt").write_text(
            "extra", encoding="utf-8"
        )
        code = "MANIFEST_PAYLOAD"
    elif change == "missing":
        runtime.unlink()
        code = "MANIFEST_PAYLOAD"
    else:
        runtime.write_text("services:\n  changed: {}\n", encoding="utf-8")
        code = "PAYLOAD_HASH"
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match=code):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


def test_rejects_one_image_reused_for_core_and_io(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    payload = tmp_path / "source" / "rosy-unsigned-payload"
    core = payload / "images" / "rosy-core.oci.tar"
    io_image = payload / "images" / "rosy-io.oci.tar"
    shutil.copyfile(core, io_image)
    manifest_path = payload / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    core_id = manifest["containers"]["rosy_core"]
    manifest["containers"]["rosy_io"] = core_id
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    provenance_path = payload / "build-provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["images"]["rosy_io"]["image_id"] = core_id
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    _refresh_manifest_files(payload)
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="IMAGE_COLLISION"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


def test_rejects_non_arm64_container_config(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    payload = tmp_path / "source" / "rosy-unsigned-payload"
    io_id = _docker_archive(
        payload / "images" / "rosy-io.oci.tar", architecture="amd64"
    )
    manifest_path = payload / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["containers"]["rosy_io"] = io_id
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    provenance_path = payload / "build-provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["images"]["rosy_io"]["image_id"] = io_id
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    _refresh_manifest_files(payload)
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="IMAGE_PLATFORM"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


def test_rejects_oversized_container_metadata(tmp_path, monkeypatch):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    monkeypatch.setattr(importer, "MAX_IMAGE_METADATA_BYTES", 1)

    with pytest.raises(HandoffError, match="IMAGE_LIMIT"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


def test_cli_imports_handoff_and_emits_json(tmp_path, capsys):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"

    exit_code = importer.main(
        [
            str(archive),
            "--checksum", str(checksum),
            "--output", str(output),
            "--release-id", RELEASE_ID,
            "--git-revision", REVISION,
            "--signing-key-id", KEY_ID,
        ],
        decompressor=_copy_decompressor,
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["signed"] is False
    assert report["output"] == str(output.resolve())


def test_cli_reports_coded_json_failure_without_private_key_interface(
    tmp_path, capsys
):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    archive.write_bytes(archive.read_bytes() + b"tampered")

    exit_code = importer.main(
        [
            str(archive),
            "--checksum", str(checksum),
            "--output", str(output),
            "--release-id", RELEASE_ID,
            "--git-revision", REVISION,
            "--signing-key-id", KEY_ID,
        ],
        decompressor=_copy_decompressor,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "ok": False,
        "code": "CHECKSUM_MISMATCH",
        "detail": "archive SHA-256 does not match its handoff checksum",
    }
    assert "private" not in importer.build_parser().format_help().lower()
    _assert_failed_cleanly(tmp_path, output)


@pytest.mark.skipif(
    shutil.which("zstd") is None, reason="zstd CLI is unavailable"
)
def test_default_zstd_decompressor_round_trips_real_cli(tmp_path):
    source = tmp_path / "source.tar"
    compressed = tmp_path / "source.tar.zst"
    restored = tmp_path / "restored.tar"
    source.write_bytes(b"real zstd handoff bytes\n" * 100)
    subprocess.run(
        [shutil.which("zstd"), "-q", "-f", str(source), "-o", str(compressed)],
        check=True,
    )

    importer._zstd_decompress(compressed, restored)

    assert restored.read_bytes() == source.read_bytes()


def test_cli_reports_missing_input_as_coded_json(tmp_path, capsys):
    missing = tmp_path / f"rosy-unsigned-{RELEASE_ID}-{REVISION}.tar.zst"

    exit_code = importer.main(
        [
            str(missing),
            "--checksum", f"{missing}.sha256",
            "--output", str(tmp_path / "verified-handoff"),
            "--release-id", RELEASE_ID,
            "--git-revision", REVISION,
            "--signing-key-id", KEY_ID,
        ]
    )

    assert exit_code == 2
    assert json.loads(capsys.readouterr().err)["code"] == "INPUT_IO"


def test_rejects_malformed_provenance_image_record(tmp_path):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    payload = tmp_path / "source" / "rosy-unsigned-payload"
    provenance_path = payload / "build-provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["images"]["rosy_io"] = "not-an-object"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    _refresh_manifest_files(payload)
    _repack_source(archive, checksum)

    with pytest.raises(HandoffError, match="PROVENANCE_SCHEMA"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


def test_atomic_commit_failure_is_coded_and_cleans_staging(
    tmp_path, monkeypatch
):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"

    def refuse_replace(_source, _destination):
        raise PermissionError("operator-controlled destination is unavailable")

    monkeypatch.setattr(importer.os, "replace", refuse_replace)

    with pytest.raises(HandoffError, match="OUTPUT_COMMIT"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


@pytest.mark.skipif(
    shutil.which("zstd") is None, reason="zstd CLI is unavailable"
)
def test_default_decompressor_enforces_output_limit(tmp_path, monkeypatch):
    source = tmp_path / "source.tar"
    compressed = tmp_path / "source.tar.zst"
    restored = tmp_path / "restored.tar"
    source.write_bytes(b"expanded bytes\n" * 100)
    subprocess.run(
        [shutil.which("zstd"), "-q", "-f", str(source), "-o", str(compressed)],
        check=True,
    )
    monkeypatch.setattr(importer, "MAX_DECOMPRESSED_TAR_BYTES", 10)

    with pytest.raises(HandoffError, match="ARCHIVE_LIMIT"):
        importer._zstd_decompress(compressed, restored)

    assert not restored.exists()


def test_rejects_oversized_json_before_reading(tmp_path, monkeypatch):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    monkeypatch.setattr(importer, "MAX_JSON_BYTES", 1)

    with pytest.raises(HandoffError, match="JSON_LIMIT"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)


def test_rejects_oversized_checksum_before_reading(tmp_path, monkeypatch):
    archive, checksum = _handoff(tmp_path)
    output = tmp_path / "verified-handoff"
    monkeypatch.setattr(importer, "MAX_CHECKSUM_BYTES", 1)

    with pytest.raises(HandoffError, match="CHECKSUM_LIMIT"):
        _import(archive, checksum, output)

    _assert_failed_cleanly(tmp_path, output)
