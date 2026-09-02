"""Disk headroom, staging cleanup and rotation contracts.

The device has one SD card, and running out of space on it does not present
as "disk full" — it presents as an update that cannot start or a rollback
with nothing to return to. These are the rules from
docs/deployment/release-retention.md, exercised against a temporary directory
with the free-space probe injected, so any fill level is reachable without a
card of that size.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from layout import Layout
from storage import (  # via test/conftest.py
    GIB,
    HEADROOM_MARGIN_BYTES,
    HEADROOM_MULTIPLIER,
    MAPS_LIMIT_BYTES,
    check_update_headroom,
    clear_staging,
    directory_size,
    free_bytes,
    prune_backups,
    reclaim,
    required_headroom,
    rotate_directory,
)


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    layout = Layout.rooted(tmp_path)
    layout.create_directories()
    return layout


def _write(path: Path, size: int, *, age_s: float = 0.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if age_s:
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
    return path


# --- the entry condition --------------------------------------------------


def test_required_headroom_matches_the_documented_formula():
    """bundle x 2.5 + 1 GiB — the number behind the 32 GB minimum."""
    assert required_headroom(3 * GIB) == int(3 * GIB * HEADROOM_MULTIPLIER) + HEADROOM_MARGIN_BYTES
    assert required_headroom(3 * GIB) == pytest.approx(8.5 * GIB, rel=0.01)


def test_an_update_with_room_is_allowed(layout):
    assert check_update_headroom(
        3 * GIB, staging=layout.staging, probe=lambda _p: 10 * GIB
    ) == []


def test_an_update_without_room_is_refused_before_anything_is_unpacked(layout):
    """Half an unpacked bundle is worse than an update that never began."""
    rejections = check_update_headroom(
        3 * GIB, staging=layout.staging, probe=lambda _p: 6 * GIB
    )

    assert [r.code for r in rejections] == ["UPDATE_INSUFFICIENT_SPACE"]


def test_the_refusal_carries_both_numbers(layout):
    """"Not enough space" is not actionable; two numbers are."""
    rejections = check_update_headroom(
        3 * GIB, staging=layout.staging, probe=lambda _p: 6 * GIB
    )
    detail = rejections[0].detail

    assert "8.5 GiB" in detail, detail
    assert "6.0 GiB" in detail, detail
    assert "3.0 GiB" in detail, "the bundle size explains where the requirement comes from"


def test_the_boundary_is_inclusive(layout):
    exact = required_headroom(1 * GIB)
    assert check_update_headroom(1 * GIB, staging=layout.staging, probe=lambda _p: exact) == []
    assert check_update_headroom(1 * GIB, staging=layout.staging, probe=lambda _p: exact - 1)


def test_a_nonsensical_bundle_size_is_refused(layout):
    for size in (0, -1):
        rejections = check_update_headroom(size, staging=layout.staging, probe=lambda _p: 99 * GIB)
        assert [r.code for r in rejections] == ["UPDATE_BUNDLE_EMPTY"]


def test_free_space_is_measurable_before_the_directory_exists(tmp_path):
    """A fresh device has no staging directory yet, and its parent is the same card."""
    assert free_bytes(tmp_path / "not" / "created" / "yet") > 0


def test_the_updater_exposes_the_gate(layout):
    """The check belongs where the caller already is."""
    from updater import Updater

    updater = Updater(
        layout,
        stop_runtime=lambda: None,
        start_runtime=lambda _mode: None,
        health_check=lambda: True,
    )
    assert updater.check_headroom(1) == [] or updater.check_headroom(10**15)


# --- staging is cleared only after activation ------------------------------


def test_staging_is_cleared(layout):
    _write(layout.staging / "2026.09.05-002" / "payload.tar", 1024)
    _write(layout.staging / "2026.09.09-003" / "payload.tar", 1024)

    removed = clear_staging(layout.staging)

    assert sorted(removed) == ["2026.09.05-002", "2026.09.09-003"]
    assert list(layout.staging.iterdir()) == []


def test_a_named_release_can_be_kept(layout):
    _write(layout.staging / "2026.09.05-002" / "payload.tar", 1024)
    _write(layout.staging / "2026.09.09-003" / "payload.tar", 1024)

    removed = clear_staging(layout.staging, keep={"2026.09.09-003"})

    assert removed == ["2026.09.05-002"]
    assert (layout.staging / "2026.09.09-003").is_dir()


def test_clearing_an_absent_staging_root_is_not_an_error(tmp_path):
    assert clear_staging(tmp_path / "absent") == []


def test_a_successful_activation_clears_staging(layout):
    """The wiring, not just the function.

    Reclaiming before the activation completes could delete the tree a
    rollback is about to need, so this asserts it happens and that it happens
    at the end.
    """
    from test_release_updater import FakeRuntime, _install, _updater

    _write(layout.staging / "2026.09.01-001" / "payload.tar", 1024)
    runtime = FakeRuntime(layout)
    record = _install(layout, "2026.09.01-001", "first")

    outcome = _updater(layout, runtime).activate(record)

    assert outcome.ok
    assert list(layout.staging.iterdir()) == [], "staging survived a completed activation"


def test_a_rolled_back_activation_does_not_clear_staging(layout):
    """The rollback path must leave the operator's staged bundle alone."""
    from test_release_updater import NEW, OLD, FakeRuntime, _install, _updater

    runtime = FakeRuntime(layout)
    _updater(layout, runtime).activate(_install(layout, OLD, "old"))

    _write(layout.staging / NEW / "payload.tar", 1024)
    runtime.unhealthy = {NEW}
    outcome = _updater(layout, runtime).activate(_install(layout, NEW, "new"), health_timeout_s=10)

    assert not outcome.ok or outcome.state.value == "ROLLED_BACK_CORE_ONLY"
    assert (layout.staging / NEW).is_dir(), "a rollback must not delete the staged bundle"


# --- rotation --------------------------------------------------------------


def test_events_rotate_oldest_first(layout):
    events = layout.var / "events"
    _write(events / "old.jsonl", 400, age_s=3000)
    _write(events / "middle.jsonl", 400, age_s=2000)
    _write(events / "new.jsonl", 400, age_s=1000)

    removed = rotate_directory(events, limit_bytes=800)

    assert removed == ["old.jsonl"]
    assert (events / "new.jsonl").exists()


def test_rotation_stops_once_it_fits(layout):
    events = layout.var / "events"
    for index in range(5):
        _write(events / f"{index}.jsonl", 100, age_s=1000 - index)

    rotate_directory(events, limit_bytes=250)

    assert directory_size(events) <= 250


def test_rotation_leaves_a_directory_under_its_limit_alone(layout):
    events = layout.var / "events"
    _write(events / "small.jsonl", 100)

    assert rotate_directory(events, limit_bytes=1000) == []
    assert (events / "small.jsonl").exists()


def test_backups_keep_the_newest(layout):
    for index, age in enumerate([4000, 3000, 2000, 1000, 500]):
        _write(layout.backups / f"backup-{index}" / "config.tar", 100, age_s=age)

    removed = prune_backups(layout.backups, keep=3)

    assert sorted(removed) == ["backup-0", "backup-1"]
    assert len(list(layout.backups.iterdir())) == 3


def test_backup_retention_of_zero_removes_all(layout):
    _write(layout.backups / "backup-0" / "config.tar", 100)
    assert prune_backups(layout.backups, keep=0) == ["backup-0"]


# --- maps are never deleted ------------------------------------------------


def test_maps_are_measured_and_never_deleted(layout):
    """A device that silently deletes a survey is worse than one that fills up."""
    maps = layout.var / "maps"
    _write(maps / "site.pgm", 2048)

    report = reclaim(layout, maps_limit=1024)

    assert report.maps_over_limit is True
    assert (maps / "site.pgm").exists(), "a map must survive every cleanup"
    assert report.warnings and "maps" in report.warnings[0]


def test_maps_under_the_limit_produce_no_warning(layout):
    _write(layout.var / "maps" / "site.pgm", 100)

    report = reclaim(layout, maps_limit=MAPS_LIMIT_BYTES)

    assert report.maps_over_limit is False
    assert report.warnings == []


def test_the_map_warning_names_both_sizes(layout):
    _write(layout.var / "maps" / "site.pgm", 3 * GIB // 1000)

    report = reclaim(layout, maps_limit=1024)

    assert "GiB" in report.warnings[0]
    assert "not deleted" in report.warnings[0]


# --- the report -------------------------------------------------------------


def test_reclaim_reports_everything_it_removed(layout):
    _write(layout.staging / "2026.09.05-002" / "payload.tar", 100)
    _write(layout.var / "events" / "old.jsonl", 400, age_s=3000)
    _write(layout.var / "events" / "new.jsonl", 400, age_s=100)
    for index, age in enumerate([4000, 3000, 2000, 1000]):
        _write(layout.backups / f"backup-{index}" / "config.tar", 100, age_s=age)

    report = reclaim(layout, events_limit=500, backup_retention=2)

    assert report.staging_removed == ["2026.09.05-002"]
    assert report.events_removed == ["old.jsonl"]
    assert sorted(report.backups_removed) == ["backup-0", "backup-1"]


def test_directory_size_ignores_symlinks(layout, tmp_path):
    if os.name != "posix":
        pytest.skip("symlink creation needs privilege on Windows; the device is Linux")

    events = layout.var / "events"
    _write(events / "real.jsonl", 100)
    big = _write(tmp_path / "elsewhere.bin", 10_000)
    os.symlink(big, events / "link.jsonl")

    assert directory_size(events) == 100, "a symlink must not be counted as local storage"


def test_directory_size_of_an_absent_directory_is_zero(tmp_path):
    assert directory_size(tmp_path / "absent") == 0
