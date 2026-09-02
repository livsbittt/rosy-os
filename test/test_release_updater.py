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
    RecoveryHeld,
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
        self.disables = 0
        self.running: str | None = None
        self.fail_on_stop = False
        self.fail_on_start = False
        self.fail_on_health = False
        self.time = 0.0

    def disable(self) -> None:
        self.disables += 1
        self.running = None

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
        disable_runtime=runtime.disable,
        clock=runtime.clock,
        sleep=lambda _seconds: None,
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
    assert "also failed its health check" in outcome.detail
    assert runtime.disables >= 1, "a hold must take the runtime down"


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


# --- rollback never restores a hardware mode ------------------------------


def _commission(layout: Layout, record: ActivationRecord, mode: str) -> None:
    """Put a non-core activation on disk, the way commissioning would."""
    from dataclasses import replace as _replace

    from layout import write_activation

    write_activation(layout, _replace(record, runtime_mode=mode))


@pytest.mark.parametrize("mode", ["motor", "hardware"])
def test_rollback_from_a_commissioned_robot_lands_in_core(layout, runtime, installed, mode):
    """The wheels must not come back live on a release that just failed.

    A robot approved for motor or hardware keeps that mode in its activation
    record. Restoring the previous record verbatim on a failed update brought
    the hardware back up while still reporting ROLLED_BACK_CORE_ONLY.
    """
    old, new = installed
    _commission(layout, old, mode)
    runtime.unhealthy = {NEW}

    outcome = _updater(layout, runtime).activate(new, health_timeout_s=10)

    assert outcome.state is UpdateState.ROLLED_BACK_CORE_ONLY
    assert read_activation(layout).release_id == OLD
    assert read_activation(layout).runtime_mode == "core", "rollback must force core"
    assert set(runtime.started) == {"core"}, f"rollback started {mode}"


@pytest.mark.parametrize("mode", ["motor", "hardware"])
def test_recovery_from_a_commissioned_robot_lands_in_core(layout, runtime, installed, mode):
    old, new = installed
    _commission(layout, old, mode)
    runtime.fail_on_start = True

    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    rebooted = FakeRuntime(layout)
    _updater(layout, rebooted).recover()

    assert read_activation(layout).runtime_mode == "core"
    assert set(rebooted.started) == {"core"}


def test_a_journal_this_build_cannot_read_is_reported_not_crashed(layout, runtime, installed):
    """A schema-drifted journal must not raise TypeError inside the boot path."""
    _old, new = installed
    runtime.fail_on_start = True
    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    journal = json.loads(layout.journal.read_text(encoding="utf-8"))
    journal["old_activation"]["unexpected_field"] = "from a newer build"
    layout.journal.write_text(json.dumps(journal), encoding="utf-8")

    with pytest.raises(ActivationUnreadable, match="cannot read"):
        _updater(layout, FakeRuntime(layout)).recover()


# --- a recovery hold outlives the reboot ----------------------------------


def test_recovery_hold_persists_across_a_reboot(layout, runtime):
    """A hold that lives only in a return value is gone by the next boot."""
    first = _install(layout, OLD, "old")
    runtime.unhealthy = {OLD}

    outcome = _updater(layout, runtime).activate(first, health_timeout_s=10)
    assert outcome.state is UpdateState.RECOVERY_HOLD

    rebooted = FakeRuntime(layout)
    after_reboot = _updater(layout, rebooted).recover()

    assert after_reboot.state is UpdateState.RECOVERY_HOLD
    assert not after_reboot.ok, "a held device must not report a successful recovery"
    assert rebooted.started == [], "the runtime must not start while held"
    assert rebooted.disables >= 1


def test_a_hold_is_only_released_deliberately(layout, runtime):
    first = _install(layout, OLD, "old")
    runtime.unhealthy = {OLD}
    updater = _updater(layout, runtime)
    updater.activate(first, health_timeout_s=10)

    assert updater.read_recovery_hold() is not None
    updater.clear_recovery_hold()
    assert updater.read_recovery_hold() is None

    # The hold is gone, but this device never completed a first activation, so
    # there is still no activation record and nothing to boot.
    after = _updater(layout, FakeRuntime(layout)).recover()
    assert after.state is UpdateState.RECOVERY_HOLD
    assert "nothing to boot" in after.detail


def test_clearing_a_hold_lets_a_device_with_an_activation_boot(layout, runtime, installed):
    _old, new = installed
    runtime.unhealthy = {NEW, OLD}
    updater = _updater(layout, runtime)
    updater.activate(new, health_timeout_s=10)

    updater.clear_recovery_hold()

    after = _updater(layout, FakeRuntime(layout)).recover()
    assert after.state is UpdateState.ACTIVATED_CORE_ONLY
    assert after.release_id == OLD


def test_an_unreadable_hold_marker_still_holds(layout, runtime, installed):
    layout.recovery_hold.write_text("{ not json", encoding="utf-8")

    outcome = _updater(layout, runtime).recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert "unreadable" in outcome.detail


def test_the_hold_state_is_visible_to_the_dashboard(layout, runtime):
    first = _install(layout, OLD, "old")
    runtime.unhealthy = {OLD}
    updater = _updater(layout, runtime)
    updater.activate(first, health_timeout_s=10)

    assert updater.read_state()["state"] == UpdateState.RECOVERY_HOLD.value


# --- the audit trail survives a rollback ----------------------------------


def test_rollback_keeps_the_state_trail(layout, runtime, installed):
    """record_state appends to the journal; a stale write would erase it."""
    _old, new = installed
    runtime.unhealthy = {NEW, OLD}

    _updater(layout, runtime).activate(new, health_timeout_s=10)

    journal = json.loads(layout.journal.read_text(encoding="utf-8"))
    states = [entry["state"] for entry in journal["states"]]
    assert UpdateState.ACTIVATING_CORE_ONLY.value in states
    assert UpdateState.ROLLING_BACK.value in states


# --- the bound is real without an injected clock --------------------------


def _bounded_sleep(limit: int = 2000):
    """A sleep that gives up rather than letting the suite hang.

    Any test that exercises the *default* clock has to bound itself. A no-op
    sleep here meant a frozen clock spun forever and the suite hung — which
    is detection of a sort, but a hang is a worse signal than a failure and
    it masked the tests queued behind it.
    """
    import time as _time

    calls = 0

    def sleep(_seconds: float) -> None:
        nonlocal calls
        calls += 1
        if calls > limit:
            raise AssertionError(f"the health wait is not bounded; it looped {limit} times")
        _time.sleep(0.002)  # real time, so the default clock actually advances

    return sleep


def test_the_health_bound_holds_with_the_default_clock(layout, installed):
    """A stub clock that never advances made the bounded wait infinite."""
    _old, new = installed
    runtime = FakeRuntime(layout, unhealthy={NEW})

    updater = Updater(
        layout,
        stop_runtime=runtime.stop,
        start_runtime=runtime.start,
        health_check=runtime.check,
        disable_runtime=runtime.disable,
        sleep=_bounded_sleep(),
    )
    outcome = updater.activate(new, health_timeout_s=0.05)

    assert outcome.state is UpdateState.ROLLED_BACK_CORE_ONLY


# --- retention: a manifest naming no images protects nothing --------------


def test_a_manifest_without_containers_prunes_nothing():
    """Readable but empty is as uninformative as unreadable."""
    current = ActivationRecord.create(
        release_id=NEW, release_path=Path("/opt/rosy/releases") / NEW,
        config_generation=NEW, data_generation=NEW,
    )
    prunable = prunable_image_digests(
        {"sha256:a"},
        activation_records=[current],
        manifests_by_release={NEW: {"release_id": NEW}},
    )
    assert prunable == set()


# --- a held device refuses to be updated ----------------------------------


def _hold(layout: Layout, runtime: FakeRuntime) -> Updater:
    """Drive the device into RECOVERY HOLD and return a fresh updater."""
    first = _install(layout, OLD, "old")
    runtime.unhealthy = {OLD}
    updater = _updater(layout, runtime)
    assert updater.activate(first, health_timeout_s=10).state is UpdateState.RECOVERY_HOLD
    return updater


def test_a_held_device_refuses_to_activate(layout, runtime):
    """Succeeding here would be a lie the next boot contradicts.

    The hold is what recover() reads, so activating through it reported
    ok=True and then came back disabled — an operator recovering a robot in
    the field would be told it worked.
    """
    updater = _hold(layout, runtime)
    good = _install(layout, NEW, "new")

    with pytest.raises(RecoveryHeld, match="held for recovery"):
        updater.activate(good)


def test_the_refusal_names_the_way_out(layout, runtime):
    updater = _hold(layout, runtime)
    with pytest.raises(RecoveryHeld, match="clear the hold"):
        updater.activate(_install(layout, NEW, "new"))


def test_clearing_the_hold_allows_the_recovery_install(layout, runtime):
    """One deliberate act, then the ordinary path works."""
    updater = _hold(layout, runtime)
    good = _install(layout, NEW, "new")

    updater.clear_recovery_hold()
    healthy = FakeRuntime(layout)
    outcome = _updater(layout, healthy).activate(good)

    assert outcome.state is UpdateState.ACTIVATED_CORE_ONLY
    assert read_activation(layout).release_id == NEW

    # And the next boot agrees with what the operator was told.
    rebooted = FakeRuntime(layout)
    after = _updater(layout, rebooted).recover()
    assert after.state is UpdateState.ACTIVATED_CORE_ONLY
    assert after.ok


def test_a_device_with_nothing_to_boot_leaves_a_marker(layout, runtime):
    """Every hold is inspectable in /var/lib/rosy, not only derived."""
    updater = _hold(layout, runtime)
    updater.clear_recovery_hold()

    outcome = _updater(layout, FakeRuntime(layout)).recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert layout.recovery_hold.is_file(), "the hold must be persisted, not just returned"


# --- activation freezes what rollback will need ---------------------------


def test_activation_freezes_the_release_and_its_generations(layout, runtime, installed):
    """Rollback rests on the previous set still being what was activated."""
    import os
    import stat as stat_module

    if os.name != "posix":
        pytest.skip("POSIX permission bits; the device and CI are Linux")

    _old, new = installed
    _updater(layout, runtime).activate(new)

    write_bits = stat_module.S_IWUSR | stat_module.S_IWGRP | stat_module.S_IWOTH
    for root in (
        layout.release(NEW),
        layout.config_generation(NEW),
        layout.data_generation(NEW),
    ):
        for entry in [root, *root.rglob("*")]:
            assert not entry.stat().st_mode & write_bits, f"still writable after activation: {entry}"


# --- a device out of the box is not a device in trouble -------------------


def test_a_factory_fresh_device_does_not_hold_itself(layout, runtime):
    """recover() runs before the runtime on every boot, including the first.

    Treating "no activation record" as a hold bricked an unprovisioned robot:
    it held itself on boot one and then refused its own first activation. A
    device with no history has nothing to recover, it just has nothing
    installed.
    """
    outcome = _updater(layout, runtime).recover()

    assert outcome.state is UpdateState.NOT_INSTALLED
    assert not layout.recovery_hold.exists(), "a fresh device must not mark itself held"
    assert runtime.disables == 0


def test_a_factory_fresh_device_can_complete_its_first_activation(layout, runtime):
    """The whole point: out of the box, provisioning works with no intervention."""
    _updater(layout, runtime).recover()

    first = _install(layout, OLD, "old")
    outcome = _updater(layout, runtime).activate(first)

    assert outcome.state is UpdateState.ACTIVATED_CORE_ONLY
    assert read_activation(layout).release_id == OLD


def test_a_device_that_lost_its_record_is_still_held(layout, runtime, installed):
    """The case the hold exists for, kept separate from the fresh one."""
    layout.activation.unlink()

    outcome = _updater(layout, runtime).recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert layout.recovery_hold.is_file()
    assert runtime.disables >= 1


def test_the_discriminator_is_how_far_the_state_got(layout, runtime):
    """Fresh and lost are separated by the recorded step, not by a file's existence.

    Keying on "release-state.json exists" was right only while nothing wrote
    the seven steps before an activation. The boundary is
    ACTIVATING_CORE_ONLY — the first moment the device has something to lose.
    """
    fresh = _updater(layout, runtime)
    assert fresh.read_state() is None
    assert fresh.recover().state is UpdateState.NOT_INSTALLED

    fresh.record_state(UpdateState.STAGED, OLD)
    assert fresh.read_state() is not None, "a state was recorded"
    assert fresh.recover().state is UpdateState.NOT_INSTALLED, (
        "a staged first install has lost nothing"
    )

    fresh.record_state(UpdateState.ACTIVATING_CORE_ONLY, OLD)
    assert _updater(layout, runtime).recover().state is UpdateState.RECOVERY_HOLD


# --- the bounded wait fails rather than hanging ---------------------------


def test_the_health_wait_cannot_loop_unboundedly(layout, installed):
    """A frozen clock used to make this spin forever; the suite hung.

    Asserting on the collaborator instead of the wall clock turns that into a
    failure without reimplementing the timeout in the test.
    """
    _old, new = installed
    runtime = FakeRuntime(layout, unhealthy={NEW})

    updater = Updater(
        layout,
        stop_runtime=runtime.stop,
        start_runtime=runtime.start,
        health_check=runtime.check,
        disable_runtime=runtime.disable,
        sleep=_bounded_sleep(),
    )
    outcome = updater.activate(new, health_timeout_s=1.0)

    assert outcome.state is UpdateState.ROLLED_BACK_CORE_ONLY


# --- what the recover unit keys on ----------------------------------------


def test_a_fresh_device_does_not_block_its_own_boot(layout, runtime):
    """ok and blocks_runtime are not the same question.

    A fresh device has nothing activated, so ok is False — but nothing is
    wrong with it, and the first-boot flow needs the boot to proceed. Exiting
    the recover unit on ok would have stopped a new robot from provisioning.
    """
    outcome = _updater(layout, runtime).recover()

    assert not outcome.ok
    assert not outcome.blocks_runtime


def test_a_held_device_blocks_its_own_boot(layout, runtime, installed):
    layout.activation.unlink()
    outcome = _updater(layout, runtime).recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert outcome.blocks_runtime


def test_a_recovered_device_does_not_block_boot(layout, runtime, installed):
    _old, new = installed
    runtime.fail_on_start = True
    with pytest.raises(PowerLoss):
        _updater(layout, runtime).activate(new)

    outcome = _updater(layout, FakeRuntime(layout)).recover()

    assert outcome.state is UpdateState.ROLLED_BACK_CORE_ONLY
    assert not outcome.blocks_runtime


# --- how far the state got, not merely that one exists --------------------


@pytest.mark.parametrize(
    "state",
    [
        UpdateState.RECEIVED,
        UpdateState.SIGNATURE_VERIFIED,
        UpdateState.CHECKSUM_VERIFIED,
        UpdateState.COMPATIBILITY_CHECKED,
        UpdateState.STAGED,
        UpdateState.CONFIG_BACKED_UP,
        UpdateState.MIGRATION_VALIDATED,
    ],
)
def test_a_first_install_interrupted_before_activation_is_not_a_hold(layout, runtime, state):
    """Seven steps precede an activation, and none means anything was lost.

    Nothing records these yet, so keying the discriminator on "a state
    exists" was right by accident. The first time an install records STAGED
    and the download is interrupted, that device would have held itself and
    refused its own first install.
    """
    updater = _updater(layout, runtime)
    updater.record_state(state, NEW)

    outcome = updater.recover()

    assert outcome.state is UpdateState.NOT_INSTALLED
    assert not outcome.blocks_runtime
    assert not layout.recovery_hold.exists()


@pytest.mark.parametrize(
    "state",
    [
        UpdateState.ACTIVATING_CORE_ONLY,
        UpdateState.CORE_HEALTHY,
        UpdateState.ACTIVATED_CORE_ONLY,
        UpdateState.ROLLED_BACK_CORE_ONLY,
    ],
)
def test_a_lost_record_after_an_activation_attempt_is_a_hold(layout, runtime, state):
    """ACTIVATING_CORE_ONLY is where the device first has something to lose."""
    updater = _updater(layout, runtime)
    updater.record_state(state, NEW)

    outcome = updater.recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert outcome.blocks_runtime


# --- an unreadable state file is history, not absence ---------------------


def test_a_corrupt_state_file_holds_rather_than_reading_as_fresh(layout, runtime):
    """CORE can write this file; a bug there must not talk the device out of a hold.

    Mirroring read_journal and returning None on a corrupt file would flip a
    device that lost its activation record into "never installed" and let it
    boot with nothing.
    """
    layout.release_state.write_text("{ truncated", encoding="utf-8")

    outcome = _updater(layout, runtime).recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert outcome.blocks_runtime


def test_a_corrupt_state_file_does_not_crash_the_boot_path(layout, runtime):
    """A traceback with no recorded reason is worse than a hold with one."""
    layout.release_state.write_bytes(bytes([0xff, 0xfe]) + b" binary")

    outcome = _updater(layout, runtime).recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
    assert layout.recovery_hold.is_file()


def test_a_state_this_build_does_not_know_is_not_reassurance(layout, runtime):
    """An unrecognised state came from somewhere; assume it meant something."""
    layout.release_state.write_text(
        json.dumps({"schema_version": 1, "state": "FROM_A_NEWER_BUILD", "release_id": NEW}),
        encoding="utf-8",
    )

    outcome = _updater(layout, runtime).recover()

    assert outcome.state is UpdateState.RECOVERY_HOLD
