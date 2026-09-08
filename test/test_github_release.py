import hashlib
import importlib.util
import io

import pytest


def metadata(content=b"bundle"):
    return {"draft": False, "prerelease": False, "tag_name": "2026.09.08-002",
            "assets": [{"name": "rosy-release-2026.09.08-002.tar.zst", "size": len(content),
                        "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
                        "browser_download_url": "https://github.com/team/rosy/releases/download/"
                                                "2026.09.08-002/rosy-release-2026.09.08-002.tar.zst"}]}


def test_github_client_exists():
    assert importlib.util.find_spec("github_release") is not None


@pytest.mark.parametrize("repo", ["https://github.com/a/b", "../rosy", "team/rosy?x", "team/rosy/extra"])
def test_repository_is_only_an_owner_and_name(repo):
    from github_release import repository
    with pytest.raises(ValueError):
        repository(repo)


def test_only_new_stable_release_is_selected():
    from github_release import select_release
    assert select_release(metadata(), "team/rosy", "2026.09.08-001").release_id == "2026.09.08-002"
    assert select_release(metadata(), "team/rosy", "2026.09.08-002") is None
    assert select_release(metadata(), "team/rosy", "2026.09.09-001") is None
    for field in ("draft", "prerelease"):
        data = metadata()
        data[field] = True
        assert select_release(data, "team/rosy", None) is None


def test_download_url_cannot_be_replaced_with_a_different_host():
    from github_release import select_release
    data = metadata()
    data["assets"][0]["browser_download_url"] = "http://127.0.0.1/private"
    with pytest.raises(ValueError, match="URL"):
        select_release(data, "team/rosy", None)


def test_download_is_atomic_and_checks_bytes(tmp_path):
    from github_release import download, select_release
    candidate = select_release(metadata(), "team/rosy", None)
    result = download(candidate, tmp_path, opener=lambda url: io.BytesIO(b"bundle"))
    assert result.read_bytes() == b"bundle"
    with pytest.raises(ValueError, match="DIGEST"):
        download(candidate, tmp_path, opener=lambda url: io.BytesIO(b"broken"))
    assert result.read_bytes() == b"bundle"
    assert not list(tmp_path.glob("*.part"))


def test_short_download_never_becomes_an_installable_file(tmp_path):
    from github_release import download, select_release
    candidate = select_release(metadata(), "team/rosy", None)
    with pytest.raises(ValueError, match="SIZE"):
        download(candidate, tmp_path, opener=lambda url: io.BytesIO(b"short"))
    assert not list(tmp_path.glob("*.tar.zst"))
