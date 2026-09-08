import importlib.util
import io
import json
import tarfile

import pytest

from release_fixture import archive, resign, signed_tree


def test_bundle_boundary_exists():
    assert importlib.util.find_spec("bundle") is not None


def test_signed_bundle_stages_without_touching_activation(tmp_path):
    from bundle import stage_archive
    from layout import Layout
    root, key, _ = signed_tree(tmp_path / "input")
    layout = Layout.rooted(tmp_path / "device")
    staged = stage_archive(archive(root, tmp_path / "release.tar"), layout, key,
                           device_target={"os_suite": "trixie"})
    assert staged.name == "2026.09.08-001"
    assert (staged / "manifest.json").is_file()
    assert not layout.activation.exists()
    assert not layout.release(staged.name).exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "a\\b", "a/../b"])
def test_archive_cannot_escape_staging(tmp_path, name):
    from bundle import BundleError, stage_archive
    from layout import Layout
    bundle = tmp_path / "bad.tar"
    with tarfile.open(bundle, "w") as tar:
        member = tarfile.TarInfo(name)
        member.size = 1
        tar.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(BundleError, match="ARCHIVE_PATH"):
        stage_archive(bundle, Layout.rooted(tmp_path / "device"), tmp_path / "key.pem")


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_links_and_special_files_are_refused(tmp_path, kind):
    from bundle import BundleError, stage_archive
    from layout import Layout
    bundle = tmp_path / "bad.tar"
    with tarfile.open(bundle, "w") as tar:
        member = tarfile.TarInfo("link")
        member.type = kind
        member.linkname = "elsewhere"
        tar.addfile(member)
    with pytest.raises(BundleError, match="ARCHIVE_TYPE"):
        stage_archive(bundle, Layout.rooted(tmp_path / "device"), tmp_path / "key.pem")


def test_duplicate_members_are_refused(tmp_path):
    from bundle import BundleError, stage_archive
    from layout import Layout
    bundle = tmp_path / "bad.tar"
    with tarfile.open(bundle, "w") as tar:
        for _ in range(2):
            member = tarfile.TarInfo("duplicate")
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(BundleError, match="ARCHIVE_DUPLICATE"):
        stage_archive(bundle, Layout.rooted(tmp_path / "device"), tmp_path / "key.pem")


def test_tampering_cannot_replace_a_staged_release(tmp_path):
    from bundle import BundleError, stage_archive
    from layout import Layout
    root, key, _ = signed_tree(tmp_path / "input")
    layout = Layout.rooted(tmp_path / "device")
    packed = archive(root, tmp_path / "release.tar")
    staged = stage_archive(packed, layout, key)
    before = (staged / "runtime/compose.yaml").read_bytes()
    (root / "runtime/compose.yaml").write_bytes(b"changed")
    archive(root, packed)
    with pytest.raises(BundleError, match="CHECKSUM_MISMATCH"):
        stage_archive(packed, layout, key)
    assert (staged / "runtime/compose.yaml").read_bytes() == before


def test_manifest_payload_digests_must_match_signed_files(tmp_path):
    from bundle import BundleError, stage_archive
    from layout import Layout
    root, key, private = signed_tree(tmp_path / "input")
    manifest_path = root / "manifest.json"
    data = json.loads(manifest_path.read_text())
    data["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(data))
    resign(root, private)
    with pytest.raises(BundleError, match="MANIFEST_PAYLOAD"):
        stage_archive(archive(root, tmp_path / "r.tar"), Layout.rooted(tmp_path / "device"), key)


def test_extracted_size_is_bounded(tmp_path):
    from bundle import BundleError, stage_archive
    from layout import Layout
    root, key, _ = signed_tree(tmp_path / "input")
    with pytest.raises(BundleError, match="ARCHIVE_SIZE"):
        stage_archive(archive(root, tmp_path / "r.tar"), Layout.rooted(tmp_path / "device"), key,
                      max_bytes=10)


def test_signed_zstd_package_round_trips(tmp_path):
    from bundle import stage_archive
    from layout import Layout
    from package_release import pack_signed
    root, key, _ = signed_tree(tmp_path / "input")
    output = tmp_path / "rosy-release-2026.09.08-001.tar.zst"
    pack_signed(root, output, key)
    assert output.read_bytes()[:4] == b"\x28\xb5\x2f\xfd"
    staged = stage_archive(output, Layout.rooted(tmp_path / "device"), key)
    assert (staged / "SHA256SUMS").read_bytes() == (root / "SHA256SUMS").read_bytes()


def test_spooling_preserves_disk_margin_before_writing(tmp_path, monkeypatch):
    import bundle
    from layout import Layout
    from storage import HEADROOM_MARGIN_BYTES
    root, key, _ = signed_tree(tmp_path / "input")
    monkeypatch.setattr(bundle, "free_bytes", lambda path: HEADROOM_MARGIN_BYTES + 1, raising=False)
    with pytest.raises(bundle.BundleError, match="UPDATE_INSUFFICIENT_SPACE"):
        bundle.stage_archive(archive(root, tmp_path / "r.tar"), Layout.rooted(tmp_path / "device"), key)
