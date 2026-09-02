"""Activation-record and immutable-layout contracts (WP-2).

The whole rollback story rests on two properties, both exercised here against
a temporary directory rather than a Raspberry Pi:

* the activation record moves as one unit, so no reader ever sees a release
  from one generation paired with config from another;
* an activated release and its generations are never edited in place, so the
  set rollback returns to is the set that was activated.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from layout import (  # via test/conftest.py
    ACTIVATION_RUNTIME_MODE,
    ACTIVATION_SCHEMA_VERSION,
    ActivationRecord,
    ActivationUnreadable,
    Layout,
    read_activation,
    resolve_activation,
    tree_fingerprint,
    update_display_pointers,
    write_activation,
    write_json_atomic,
)

posix_only = pytest.mark.skipif(
    os.name != "posix",
    reason="symlinks and POSIX permissions; the device and CI are Linux",
)


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    layout = Layout.rooted(tmp_path)
    layout.create_directories()
    return layout


def _install_release(layout: Layout, release_id: str, marker: str) -> ActivationRecord:
    """Create a release plus its config and data generations."""
    release = layout.release(release_id)
    release.mkdir(parents=True, exist_ok=True)
    (release / "compose.yaml").write_text(f"# {marker}\n", encoding="utf-8")

    config = layout.config_generation(release_id)
    config.mkdir(parents=True, exist_ok=True)
    (config / "rosy.yaml").write_text(f"marker: {marker}\n", encoding="utf-8")

    data = layout.data_generation(release_id)
    data.mkdir(parents=True, exist_ok=True)
    (data / "state.json").write_text(json.dumps({"marker": marker}), encoding="utf-8")

    return ActivationRecord.create(
        release_id=release_id,
        release_path=release,
        config_generation=release_id,
        data_generation=release_id,
    )


# --- layout shape ---------------------------------------------------------


def test_layout_matches_the_documented_paths():
    layout = Layout.default()
    assert layout.releases == Path("/opt/rosy/releases")
    assert layout.current_link == Path("/opt/rosy/current")
    assert layout.previous_link == Path("/opt/rosy/previous")
    assert layout.config_generations == Path("/etc/rosy/generations")
    assert layout.data_generations == Path("/var/lib/rosy/data-generations")
    assert layout.activation == Path("/var/lib/rosy/activation.json")
    assert layout.journal == Path("/var/lib/rosy/update-journal.json")
    assert layout.release_state == Path("/var/lib/rosy/release-state.json")
    assert layout.staging == Path("/var/cache/rosy/releases")


def test_device_identity_lives_outside_every_generation():
    """Identity, trusted keys and network profiles survive any release change."""
    layout = Layout.default()
    for path in (layout.identity, layout.trusted_keys, layout.network):
        assert layout.config_generations not in path.parents
        assert layout.releases not in path.parents


def test_create_directories_is_repeatable(layout):
    layout.create_directories()
    layout.create_directories()
    assert layout.releases.is_dir()
    assert layout.backups.is_dir()


# --- the activation record ------------------------------------------------


def test_activation_names_release_config_data_and_mode_together(layout):
    record = _install_release(layout, "2026.09.01-001", "first")
    write_activation(layout, record)

    stored = read_activation(layout)
    assert stored.release_id == "2026.09.01-001"
    assert stored.config_generation == "2026.09.01-001"
    assert stored.data_generation == "2026.09.01-001"
    assert stored.runtime_mode == "core"


def test_activation_defaults_to_core_only(layout):
    record = _install_release(layout, "2026.09.01-001", "first")
    assert record.runtime_mode == ACTIVATION_RUNTIME_MODE == "core"


def test_activation_rejects_an_unknown_runtime_mode(layout):
    with pytest.raises(ValueError, match="unknown runtime mode"):
        ActivationRecord.create(
            release_id="2026.09.01-001",
            release_path=layout.release("2026.09.01-001"),
            config_generation="g",
            data_generation="g",
            runtime_mode="turbo",
        )


def test_boot_paths_come_from_the_record(layout):
    record = _install_release(layout, "2026.09.01-001", "first")
    write_activation(layout, record)

    resolved = resolve_activation(layout, read_activation(layout))
    assert resolved.release == layout.release("2026.09.01-001")
    assert (resolved.config_generation / "rosy.yaml").read_text(encoding="utf-8") == "marker: first\n"
    assert resolved.runtime_mode == "core"


# --- rejecting an unusable record ----------------------------------------


def test_missing_activation_is_reported(layout):
    with pytest.raises(ActivationUnreadable):
        read_activation(layout)


def test_malformed_activation_is_reported(layout):
    layout.activation.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ActivationUnreadable, match="malformed JSON"):
        read_activation(layout)


def test_unknown_activation_schema_is_refused(layout):
    layout.activation.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(ActivationUnreadable, match="not implemented"):
        read_activation(layout)


def test_incomplete_activation_is_refused(layout):
    layout.activation.write_text(
        json.dumps({"schema_version": ACTIVATION_SCHEMA_VERSION, "release_id": "x"}),
        encoding="utf-8",
    )
    with pytest.raises(ActivationUnreadable, match="missing fields"):
        read_activation(layout)


def test_activation_with_an_unknown_mode_is_refused(layout):
    record = _install_release(layout, "2026.09.01-001", "first")
    payload = json.loads(json.dumps(record.__dict__))
    payload["runtime_mode"] = "turbo"
    layout.activation.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ActivationUnreadable, match="unknown runtime mode"):
        read_activation(layout)


# --- atomicity ------------------------------------------------------------


def test_replacement_is_all_or_nothing(layout):
    """A reader sees the old set or the new one, never a blend."""
    first = _install_release(layout, "2026.09.01-001", "first")
    second = _install_release(layout, "2026.09.05-002", "second")

    write_activation(layout, first)
    assert read_activation(layout).release_id == "2026.09.01-001"

    write_activation(layout, second)
    stored = read_activation(layout)
    assert (
        stored.release_id,
        stored.config_generation,
        stored.data_generation,
    ) == ("2026.09.05-002",) * 3, "release and generations must move as one set"


def test_a_failed_write_leaves_the_previous_record_intact(layout, monkeypatch):
    first = _install_release(layout, "2026.09.01-001", "first")
    write_activation(layout, first)

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError):
        write_activation(layout, _install_release(layout, "2026.09.05-002", "second"))

    assert read_activation(layout).release_id == "2026.09.01-001"


def test_a_failed_write_leaves_no_temporary_file_behind(layout, monkeypatch):
    write_activation(layout, _install_release(layout, "2026.09.01-001", "first"))

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError):
        write_activation(layout, _install_release(layout, "2026.09.05-002", "second"))

    leftovers = [p.name for p in layout.activation.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_atomic_write_creates_its_parent_directory(tmp_path):
    target = tmp_path / "deep" / "nested" / "state.json"
    write_json_atomic(target, {"ok": True})
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_atomic_write_stays_on_the_destination_filesystem(layout, monkeypatch):
    """The temporary file must be a sibling, or the rename is not atomic."""
    seen: list[str] = []
    real_replace = os.replace

    def record_replace(src, dst):
        seen.append(str(src))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", record_replace)
    write_activation(layout, _install_release(layout, "2026.09.01-001", "first"))

    assert seen
    assert Path(seen[0]).parent == layout.activation.parent


# --- symlinks are derived display, not a boot input -----------------------


@posix_only
def test_display_pointers_track_the_activated_releases(layout):
    _install_release(layout, "2026.09.01-001", "first")
    _install_release(layout, "2026.09.05-002", "second")
    update_display_pointers(layout, current="2026.09.05-002", previous="2026.09.01-001")

    assert layout.current_link.resolve() == layout.release("2026.09.05-002").resolve()
    assert layout.previous_link.resolve() == layout.release("2026.09.01-001").resolve()


@posix_only
def test_display_pointers_are_repointable(layout):
    _install_release(layout, "2026.09.01-001", "first")
    _install_release(layout, "2026.09.05-002", "second")
    update_display_pointers(layout, current="2026.09.01-001", previous=None)
    update_display_pointers(layout, current="2026.09.05-002", previous="2026.09.01-001")

    assert layout.current_link.resolve() == layout.release("2026.09.05-002").resolve()


@posix_only
def test_boot_still_resolves_with_the_symlinks_destroyed(layout):
    """The record is authoritative; the pointers are a convenience."""
    record = _install_release(layout, "2026.09.01-001", "first")
    write_activation(layout, record)
    update_display_pointers(layout, current="2026.09.01-001", previous=None)

    layout.current_link.unlink()
    os.symlink(layout.release("does-not-exist"), layout.previous_link, target_is_directory=True)

    resolved = resolve_activation(layout, read_activation(layout))
    assert (resolved.config_generation / "rosy.yaml").is_file()
    assert resolved.release == layout.release("2026.09.01-001")


@posix_only
def test_a_symlink_pointing_at_the_wrong_release_does_not_change_the_boot(layout):
    """The mixed state the record exists to prevent."""
    old = _install_release(layout, "2026.09.01-001", "first")
    _install_release(layout, "2026.09.05-002", "second")
    write_activation(layout, old)
    update_display_pointers(layout, current="2026.09.05-002", previous=None)

    resolved = resolve_activation(layout, read_activation(layout))
    assert resolved.release == layout.release("2026.09.01-001")
    assert (resolved.config_generation / "rosy.yaml").read_text(encoding="utf-8") == "marker: first\n"


def test_pointer_failure_does_not_raise(layout):
    """An activation must not fail because a cosmetic symlink could not be set."""
    update_display_pointers(layout, current="never-installed", previous=None)


# --- immutability ---------------------------------------------------------


def test_activated_release_and_generations_are_unchanged_by_a_later_activation(layout):
    first = _install_release(layout, "2026.09.01-001", "first")
    write_activation(layout, first)

    before_release = tree_fingerprint(layout.release("2026.09.01-001"))
    before_config = tree_fingerprint(layout.config_generation("2026.09.01-001"))
    before_data = tree_fingerprint(layout.data_generation("2026.09.01-001"))

    second = _install_release(layout, "2026.09.05-002", "second")
    write_activation(layout, second)
    update_display_pointers(layout, current="2026.09.05-002", previous="2026.09.01-001")

    assert tree_fingerprint(layout.release("2026.09.01-001")) == before_release
    assert tree_fingerprint(layout.config_generation("2026.09.01-001")) == before_config
    assert tree_fingerprint(layout.data_generation("2026.09.01-001")) == before_data


def test_rolling_back_restores_the_untouched_previous_set(layout):
    first = _install_release(layout, "2026.09.01-001", "first")
    write_activation(layout, first)
    fingerprint = tree_fingerprint(layout.config_generation("2026.09.01-001"))

    second = _install_release(layout, "2026.09.05-002", "second")
    write_activation(layout, second)

    write_activation(layout, first)  # rollback

    resolved = resolve_activation(layout, read_activation(layout))
    assert resolved.release == layout.release("2026.09.01-001")
    assert tree_fingerprint(resolved.config_generation) == fingerprint


def test_tree_fingerprint_detects_an_in_place_edit(layout):
    """Proof the immutability tests above are not vacuous."""
    _install_release(layout, "2026.09.01-001", "first")
    before = tree_fingerprint(layout.release("2026.09.01-001"))
    (layout.release("2026.09.01-001") / "compose.yaml").write_text("# edited\n", encoding="utf-8")
    assert tree_fingerprint(layout.release("2026.09.01-001")) != before


def test_tree_fingerprint_detects_an_added_file(layout):
    _install_release(layout, "2026.09.01-001", "first")
    before = tree_fingerprint(layout.release("2026.09.01-001"))
    (layout.release("2026.09.01-001") / "extra").write_text("x", encoding="utf-8")
    assert tree_fingerprint(layout.release("2026.09.01-001")) != before


@posix_only
def test_freezing_a_release_blocks_casual_writes(layout):
    from layout import freeze_tree

    _install_release(layout, "2026.09.01-001", "first")
    release = layout.release("2026.09.01-001")
    freeze_tree(release)

    if os.geteuid() == 0:
        pytest.skip("root ignores the write bit; the guard is against accident, not privilege")

    with pytest.raises(PermissionError):
        (release / "compose.yaml").write_text("# edited\n", encoding="utf-8")
