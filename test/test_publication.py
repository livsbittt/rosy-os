import importlib.util

import pytest

from release_fixture import archive, signed_tree


def test_publication_verifier_exists():
    assert importlib.util.find_spec("publication") is not None


def test_signed_payload_must_match_the_published_tag(tmp_path):
    from bundle import BundleError
    from publication import verify_publication
    root, key, _ = signed_tree(tmp_path / "input")
    packed = archive(root, tmp_path / "release.tar")
    result = verify_publication(packed, key, root.name, "a" * 40)
    assert result["release_id"] == root.name
    with pytest.raises(BundleError, match="PUBLICATION_IDENTITY"):
        verify_publication(packed, key, "2026.09.08-002", "a" * 40)
    with pytest.raises(BundleError, match="PUBLICATION_IDENTITY"):
        verify_publication(packed, key, root.name, "b" * 40)
