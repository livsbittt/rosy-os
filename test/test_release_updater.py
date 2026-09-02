"""Activation, rollback and power-loss recovery contracts (WP-2).

Every path runs against a temporary directory with runtime control injected,
including the ones that are impractical to provoke on a real robot: a
candidate whose CORE never comes up, and power cut at each step of the
activation.

The recurring assertion is that both endings are core-only. An update that
succeeds and an update that rolls back both leave the device running CORE
alone; nothing here restores motor or hardware.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from layout import (
    ActivationRecord,
    ActivationUnreadable,
    Layout,
    read_activation,
    resolve_activation,
)
from updater import (
    Updater,
    UpdateState,
    prunable_image_digests,
    releases_to_keep,
)

OLD = "2026.09.01-001"
NEW = "2026.09.05-002"


class PowerLoss(Exception):
    """Simulates the device losing power partway through an activation."""


class FakeRuntime:
    """Records what the updater asked the runtime to do.

    Health is decided by reading ``activation.json``, the way the real check
    probes whichever CORE is actually running. That distinction matters: a
    fake with one ``healthy`` flag would report the rollback target unhealthy
    for the same reason the candidate was, and every rollback would look like
    an unrecoverable device.
    """

    def __init__(self, layout: Layout, *, unhealthy: set[str] | None = None) -> None:
        self.layout = layout
        self.unhealthy = set(unhealthy or ())
        self.started: list[str] = []
        self.stops = 0
        self.running: str | None = None
        self.fail_on_stop = False
        self.fail_on_start = False
        self.fail_on_health = False
        self.time = 0.0

    def stop(self) -> None:
        if self.fail_on_stop:
            raise PowerLoss("power lost while stopping the runtime")
        self.stops += 1
        self.running = None

    def start(self, mode: str) -> None:
        if self.fail_on_start:
            raise PowerLoss("power lost while starting the candidate")
        self.started.append(mode)
        self.running = mode

    def check(self) -> bool:
        if self.fail_on_health:
            raise PowerLoss("power lost during the health check")
        self.time += 5.0
        try:
            live = read_activation(self.layout).release_id
        except ActivationUnreadable:
            return False
        return live not in self.unhealthy

    def clock(self) -> float:
        return self.time


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    layout = Layout.rooted(tmp_path)
    layout.create_directories()
    return layout


@pytest.fixture
def runtime(layout: Layout) -> FakeRuntime:
    return FakeRuntime(layout)


def _updater(layout: Layout, runtime: FakeRuntime) -> Updater:
    return Updater(
        layout,
        stop_runtime=runtime.stop,
        start_runtime=runtime.start,
        health_check=runtime.check,
        clock=runtime.clock,
    )


def _install(layout: Layout, release_id: str, marker: str) -> ActivationRecord:
    release = layout.release(release_id)
    release.mkdir(parents=True, exist_ok=True)
    (release / "compose.yaml").write_text(f"# {marker}\n", encoding="utf-8")

    config = layout.config_generation(release_id)
    config.mkdir(parents=True, exist_ok=True)
    (config / "rosy.yaml").write_text(f"marker: {marker}\n", encoding="utf-8")

    data = layout.data_generation(release_id)
    data.mkdir(parents=True, exist_ok=True)

    return ActivationRecord.create(
        release_id=release_id,
        release_path=release,
        config_generation=release_id,
        data_generation=release_id,
    )


@pytest.fixture
def installed(layout: Layout, runtime: FakeRuntime) -> tuple[ActivationRecord, ActivationRecord]:
    """An activated OLD release and a staged NEW candidate."""
    old = _install(layout, OLD, "old")
    _updater(layout, runtime).activate(old)
    runtime.started.clear()
    runtime.stops = 0
    return old, _install(layout, NEW, "new")


# --- successful update ----------------------------------------------------


def test_successful_update_activates_the_candidate(layout, runtime, installed):
    _old, new = installed
    outcome = _updater(layout, runtime).activate(new)

    assert outcome.state is UpdateState.ACTIVATED_CORE_ONLY
    assert outcome.ok
    assert read_activation(layout).release_id == NEW


def test_successful_update_moves_the_whole_set(layout, runtime, installed):
    _old, new = installed
    _updater(layout, runtime).activate(new)

    resolved = resolve_activation(layout, read_activation(layout))
    assert resolved.release == layout.release(NEW)
    assert (resolved.config_generation / "rosy.yaml").read_text(encoding="utf-8") == "marker: new\n"


def test_successful_update_ends_core_only(layout, runtime, installed):
    _old, new = installed
    _updater(layout, runtime).activate(new)

    assert read_activation(layout).runtime_mode == "core"
    assert runtime.started == ["core"]


def test_successful_update_clears_the_journal(layout, runtime, installed):
    _old, new = installed
    _updater(layout, runtime).activate(new)
    assert not layout.journal.exists()


def test_successful_update_records_its_states(layout, runtime, installed):
    _old, new = installed
    updater = _updater(layout, runtime)
    updater.activate(new)

    state = updater.read_state()
    assert state["state"] == UpdateState.ACTIVATED_CORE_ONLY.value
    assert state["release_id"] == NEW


def test_an_activation_must_install_core(layout, runtime, installed):
    hardware = ActivationRecord.create(
        release_id=NEW,
        release_path=layout.release(NEW),
        config_generation=NEW,
        data_generation=NEW,
        runtime_mode="hardware",
    )
    with pytest.raises(ValueError, match="must install 'core'"):
        _updater(layout, runtime).activate(hardware)


# --- health-failure rollback ---------------------------------------------


def test_unhealthy_candidate_rolls_back(layout, runtime, installed):
    _old, new = installed
    runtime.unhealthy = {NEW}

    outcome = _updater(layout, runtime).activate(new, health_timeout_s=10)

    assert outcome.state is UpdateState.ROLLED_BACK_CORE_ONLY
    assert read_activation(layout).release_id == OLD


def test_rollback_restores_the_previous_configuration(layout, runtime, installed):
    _old, new = installed
    runtime.unhealthy = {NEW}

    _updater(layout, runtime).activate(new, health_timeout_s=10)

    resolved = resolve_activation(layout, read_activation(layout))
    assert (resolved.config_generation / "rosy.yaml").read_text(encoding="utf-8") == "marker: old\n"


def test_rollback_ends_core_only(layout, runtime, installed):
    _old, new = installed
    runtime.unhealthy = {NEW}

    _updater(layout, runtime).activate(new, health_timeout_s=10)

    assert read_activation(layout).runtime_mode == "core"
    assert set(runtime.started) == {"core"}, "rollback must not restore motor or hardware"


def test_rollback_is_bounded_not_indefinite(layout, runtime, installed):
    """A candidate that never comes up must not hold the device forever."""
    _old, new = installed
    runtime.unhealthy = {NEW}

    _updater(layout, runtime).activate(new, health_timeout_s=30)

    assert runtime.time >= 30, "the health check must observe its deadline"


def test_rollback_records_why(layout, runtime, installed):
    _old, new = installed
    runtime.unhealthy = {NEW}

    updater = _updater(layout, runtime)
    updater.activate(new, health_timeout_s=10)

    state = updater.read_state()
    assert state["state"] == UpdateState.ROLLED_BACK_CORE_ONLY.value
    assert "did not become healthy" in state["detail"]


def test_a_first_activation_that_fails_leaves_recovery_hold(layout, runtime):
    """With no previous release there is nothing to roll back to."""
    first = _install(layout, OLD, "old")
    runtime.unhealthy = {OLD}

    outcome = _updater(layout, runtime).activate(first, health_timeout_s=10)

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert not outcome.ok
    with pytest.raises(ActivationUnreadable):
        read_activation(layout)


def test_recovery_hold_when_the_rollback_target_is_also_unhealthy(layout, runtime, installed):
    """Nothing left to fall back to: the device holds instead of pretending."""
    _old, new = installed
    runtime.unhealthy = {NEW, OLD}

    outcome = _updater(layout, runtime).activate(new, health_timeout_s=10)

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert not outcome.ok
    assert "unhealthy" in outcome.detail


# --- power loss -----------------------------------------------------------


@pytest.mark.parametrize("interrupt", ["fail_on_stop", "fail_on_start", "fail_on_health"])
def test_power_loss_during_activation_recovers_to_the_previous_release(
    layout, runtime, installed, interrupt
):
    """Whatever step the power cut lands on, the device comes back on OLD."""
    _old, new = installed
    setattr(runtime, interrupt, True)

    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    # Reboot: a fresh updater with a working runtime runs recovery first.
    rebooted = FakeRuntime(layout)
    outcome = _updater(layout, rebooted).recover()

    assert outcome.state is UpdateState.ROLLED_BACK_CORE_ONLY
    assert read_activation(layout).release_id == OLD
    assert rebooted.started == ["core"]


def test_power_loss_leaves_a_journal_to_recover_from(layout, runtime, installed):
    _old, new = installed
    runtime.fail_on_start = True

    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    journal = _updater(layout, runtime).read_journal()
    assert journal is not None
    assert journal.complete is False
    assert journal.release_id == NEW
    assert journal.old_activation["release_id"] == OLD


def test_the_journal_is_written_before_the_activation_record_moves(layout, runtime, installed):
    """Power cut before the journal exists must not strand the device."""
    _old, new = installed
    runtime.fail_on_stop = True

    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    # The runtime was never stopped, so activation.json cannot have moved.
    assert read_activation(layout).release_id == OLD
    assert layout.journal.is_file(), "the journal must exist before anything moves"


def test_recovery_is_a_no_op_without_a_journal(layout, runtime, installed):
    outcome = _updater(layout, runtime).recover()
    assert outcome.detail == "no interrupted update"
    assert read_activation(layout).release_id == OLD


def test_recovery_cleans_up_a_completed_journal(layout, runtime, installed):
    _old, new = installed
    updater = _updater(layout, runtime)
    updater.activate(new)

    # A journal left behind by a crash after completion but before cleanup.
    layout.journal.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": NEW,
                "candidate_activation": {},
                "old_activation": None,
                "old_current": None,
                "old_previous": None,
                "complete": True,
                "states": [],
            }
        ),
        encoding="utf-8",
    )

    outcome = updater.recover()
    assert outcome.ok
    assert not layout.journal.exists()


def test_recovery_ends_core_only(layout, runtime, installed):
    _old, new = installed
    runtime.fail_on_health = True
    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    rebooted = FakeRuntime(layout)
    _updater(layout, rebooted).recover()

    assert read_activation(layout).runtime_mode == "core"
    assert set(rebooted.started) == {"core"}


def test_recovery_is_repeatable(layout, runtime, installed):
    """Power lost again during recovery must not make things worse."""
    _old, new = installed
    runtime.fail_on_start = True
    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    rebooted = FakeRuntime(layout)
    first = _updater(layout, rebooted).recover()
    second = _updater(layout, rebooted).recover()

    assert first.state is UpdateState.ROLLED_BACK_CORE_ONLY
    assert second.detail == "no interrupted update"
    assert read_activation(layout).release_id == OLD


# --- image retention ------------------------------------------------------


def _manifest(core: str, io: str) -> dict:
    return {"containers": {"rosy_core": core, "rosy_io": io}}


def test_images_of_the_current_and_previous_releases_are_never_pruned():
    """Pruning the previous release's images turns rollback into a site visit."""
    current = ActivationRecord.create(
        release_id=NEW, release_path=Path("/opt/rosy/releases") / NEW,
        config_generation=NEW, data_generation=NEW,
    )
    previous = ActivationRecord.create(
        release_id=OLD, release_path=Path("/opt/rosy/releases") / OLD,
        config_generation=OLD, data_generation=OLD,
    )
    all_digests = {"sha256:new-core", "sha256:new-io", "sha256:old-core", "sha256:old-io", "sha256:ancient"}

    prunable = prunable_image_digests(
        all_digests,
        activation_records=[current, previous],
        manifests_by_release={
            NEW: _manifest("sha256:new-core", "sha256:new-io"),
            OLD: _manifest("sha256:old-core", "sha256:old-io"),
        },
    )

    assert prunable == {"sha256:ancient"}


def test_an_unreadable_manifest_prunes_nothing():
    """Not knowing what a live release needs is a reason to delete nothing."""
    current = ActivationRecord.create(
        release_id=NEW, release_path=Path("/opt/rosy/releases") / NEW,
        config_generation=NEW, data_generation=NEW,
    )
    prunable = prunable_image_digests(
        {"sha256:a", "sha256:b"},
        activation_records=[current],
        manifests_by_release={},
    )
    assert prunable == set()


def test_shared_digests_are_protected_by_either_release():
    """rosy_io is one image; two releases may name the same digest."""
    current = ActivationRecord.create(
        release_id=NEW, release_path=Path("/") / NEW, config_generation=NEW, data_generation=NEW,
    )
    previous = ActivationRecord.create(
        release_id=OLD, release_path=Path("/") / OLD, config_generation=OLD, data_generation=OLD,
    )
    prunable = prunable_image_digests(
        {"sha256:core-new", "sha256:core-old", "sha256:io-shared"},
        activation_records=[current, previous],
        manifests_by_release={
            NEW: _manifest("sha256:core-new", "sha256:io-shared"),
            OLD: _manifest("sha256:core-old", "sha256:io-shared"),
        },
    )
    assert prunable == set()


def test_retention_keeps_the_last_three_releases():
    installed = [
        "2026.09.01-001", "2026.09.05-002", "2026.09.09-003",
        "2026.09.12-004", "2026.09.15-005",
    ]
    kept = releases_to_keep(installed, keep_last=3, protected=set())
    assert kept == {"2026.09.09-003", "2026.09.12-004", "2026.09.15-005"}


def test_retention_never_deletes_a_release_an_activation_points_at():
    installed = [
        "2026.09.01-001", "2026.09.05-002", "2026.09.09-003",
        "2026.09.12-004", "2026.09.15-005",
    ]
    kept = releases_to_keep(installed, keep_last=3, protected={"2026.09.01-001"})
    assert "2026.09.01-001" in kept
    assert len(kept) == 4


def test_retention_ignores_protection_for_releases_that_are_gone():
    kept = releases_to_keep(["2026.09.15-005"], keep_last=3, protected={"2026.01.01-001"})
    assert kept == {"2026.09.15-005"}
