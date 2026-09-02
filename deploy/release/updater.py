"""Release activation, rollback and power-loss recovery (WP-2).

Activation is the moment an update can leave a robot unbootable, so the order
here is deliberate and the journal is written before anything moves.

The sequence, matching the design's activation procedure:

1. Record the old activation, the candidate activation and the display
   pointers in the journal, and flush it.
2. Stop the running runtime.
3. Replace ``activation.json`` atomically with the candidate.
4. Repoint the cosmetic ``current``/``previous`` symlinks.
5. Start the candidate in ``core`` mode and health-check it under a bound.
6. On success, mark ``previous`` and complete the journal.
7. On failure, restore the old activation record atomically, restore the
   pointers and bring the previous release back up in ``core``.

If power is lost anywhere in the middle, :meth:`Updater.recover` reads the
journal on the next boot and finishes the story before the runtime is allowed
to start. That ordering is why ``rosy-release-recover.service`` must run
before ``rosy-runtime.service``, with the runtime depending on it — otherwise
a half-activated device boots a candidate nobody ever health-checked.

Neither activation nor rollback ever restores ``motor`` or ``hardware``. Both
end core-only, and returning to a hardware mode is a separate field approval.

Runtime control and health checking are injected so the whole sequence runs
in a temporary directory, including the failure paths that are impractical to
provoke on real hardware.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from layout import (
    ACTIVATION_RUNTIME_MODE,
    ActivationRecord,
    ActivationUnreadable,
    Layout,
    read_activation,
    update_display_pointers,
    write_activation,
    write_json_atomic,
)

JOURNAL_SCHEMA_VERSION = 1

#: The health check is bounded so a candidate that never comes up cannot hold
#: the device in an unusable state indefinitely.
DEFAULT_HEALTH_TIMEOUT_S = 90.0


class UpdateState(str, Enum):
    """States recorded in release-state.json and the journal."""

    RECEIVED = "RECEIVED"
    SIGNATURE_VERIFIED = "SIGNATURE_VERIFIED"
    CHECKSUM_VERIFIED = "CHECKSUM_VERIFIED"
    COMPATIBILITY_CHECKED = "COMPATIBILITY_CHECKED"
    STAGED = "STAGED"
    CONFIG_BACKED_UP = "CONFIG_BACKED_UP"
    MIGRATION_VALIDATED = "MIGRATION_VALIDATED"
    ACTIVATING_CORE_ONLY = "ACTIVATING_CORE_ONLY"
    CORE_HEALTHY = "CORE_HEALTHY"
    ACTIVATED_CORE_ONLY = "ACTIVATED_CORE_ONLY"
    COMMISSIONING_REQUIRED = "COMMISSIONING_REQUIRED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK_CORE_ONLY = "ROLLED_BACK_CORE_ONLY"
    RECOVERY_HOLD = "RECOVERY_HOLD"


@dataclass
class JournalEntry:
    state: str
    at: str
    detail: str = ""


@dataclass
class Journal:
    """What an interrupted activation left behind.

    Written and flushed *before* the activation record moves, so a device that
    loses power mid-update always has enough to decide what to do.
    """

    schema_version: int
    release_id: str
    candidate_activation: dict
    old_activation: dict | None
    old_current: str | None
    old_previous: str | None
    backup_path: str | None = None
    complete: bool = False
    states: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Outcome:
    """The result of an activation, rollback or recovery."""

    state: UpdateState
    release_id: str | None
    detail: str

    @property
    def ok(self) -> bool:
        return self.state in {
            UpdateState.ACTIVATED_CORE_ONLY,
            UpdateState.ROLLED_BACK_CORE_ONLY,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Updater:
    """Drives activation, rollback and recovery against a :class:`Layout`."""

    def __init__(
        self,
        layout: Layout,
        *,
        stop_runtime: Callable[[], None],
        start_runtime: Callable[[str], None],
        health_check: Callable[[], bool],
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.layout = layout
        self._stop_runtime = stop_runtime
        self._start_runtime = start_runtime
        self._health_check = health_check
        self._clock = clock or (lambda: 0.0)

    # --- recorded state ---------------------------------------------------

    def record_state(self, state: UpdateState, release_id: str | None, detail: str = "") -> None:
        """Publish the current step for the dashboard and the audit trail."""
        write_json_atomic(
            self.layout.release_state,
            {
                "schema_version": JOURNAL_SCHEMA_VERSION,
                "state": state.value,
                "release_id": release_id,
                "detail": detail,
                "at": _now(),
            },
        )
        journal = self.read_journal()
        if journal is not None and not journal.complete:
            journal.states.append(asdict(JournalEntry(state=state.value, at=_now(), detail=detail)))
            self._write_journal(journal)

    def read_state(self) -> dict | None:
        path = self.layout.release_state
        if not path.is_file():
            return None
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    # --- journal ----------------------------------------------------------

    def _write_journal(self, journal: Journal) -> None:
        write_json_atomic(self.layout.journal, asdict(journal))

    def read_journal(self) -> Journal | None:
        path = self.layout.journal
        if not path.is_file():
            return None
        import json

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("schema_version") != JOURNAL_SCHEMA_VERSION:
            return None
        return Journal(
            schema_version=data["schema_version"],
            release_id=data["release_id"],
            candidate_activation=data["candidate_activation"],
            old_activation=data.get("old_activation"),
            old_current=data.get("old_current"),
            old_previous=data.get("old_previous"),
            backup_path=data.get("backup_path"),
            complete=data.get("complete", False),
            states=data.get("states", []),
        )

    def _clear_journal(self) -> None:
        self.layout.journal.unlink(missing_ok=True)

    def _current_activation(self) -> ActivationRecord | None:
        try:
            return read_activation(self.layout)
        except ActivationUnreadable:
            return None

    # --- activation -------------------------------------------------------

    def activate(
        self,
        candidate: ActivationRecord,
        *,
        backup_path: Path | None = None,
        health_timeout_s: float = DEFAULT_HEALTH_TIMEOUT_S,
    ) -> Outcome:
        """Activate ``candidate``, rolling back if its CORE does not come up."""
        if candidate.runtime_mode != ACTIVATION_RUNTIME_MODE:
            raise ValueError(
                f"an activation must install {ACTIVATION_RUNTIME_MODE!r}, got {candidate.runtime_mode!r}"
            )

        old = self._current_activation()

        journal = Journal(
            schema_version=JOURNAL_SCHEMA_VERSION,
            release_id=candidate.release_id,
            candidate_activation=asdict(candidate),
            old_activation=asdict(old) if old else None,
            old_current=old.release_id if old else None,
            old_previous=self._link_target_id(self.layout.previous_link),
            backup_path=str(backup_path) if backup_path else None,
        )
        self._write_journal(journal)

        self.record_state(UpdateState.ACTIVATING_CORE_ONLY, candidate.release_id)

        self._stop_runtime()
        write_activation(self.layout, candidate)
        update_display_pointers(
            self.layout,
            current=candidate.release_id,
            previous=old.release_id if old else None,
        )
        self._start_runtime(candidate.runtime_mode)

        if self._await_health(health_timeout_s):
            self.record_state(UpdateState.CORE_HEALTHY, candidate.release_id)
            journal = self.read_journal() or journal
            journal.complete = True
            self._write_journal(journal)
            self.record_state(UpdateState.ACTIVATED_CORE_ONLY, candidate.release_id)
            self._clear_journal()
            return Outcome(
                UpdateState.ACTIVATED_CORE_ONLY,
                candidate.release_id,
                "candidate CORE reached health within the bound",
            )

        return self._roll_back(
            journal,
            detail=f"candidate CORE did not become healthy within {health_timeout_s:g}s",
        )

    def _await_health(self, timeout_s: float) -> bool:
        """Poll the injected health check until it passes or the bound expires."""
        deadline = self._clock() + timeout_s
        while True:
            if self._health_check():
                return True
            if self._clock() >= deadline:
                return False

    def _link_target_id(self, link: Path) -> str | None:
        try:
            if link.is_symlink():
                return Path(link.readlink()).name
        except OSError:
            pass
        return None

    # --- rollback ---------------------------------------------------------

    def _roll_back(self, journal: Journal, *, detail: str) -> Outcome:
        """Restore the previous activation set and bring it up core-only."""
        self.record_state(UpdateState.ROLLING_BACK, journal.release_id, detail)

        self._stop_runtime()

        if journal.old_activation is None:
            # Nothing to go back to — a failed first activation.
            self.layout.activation.unlink(missing_ok=True)
            update_display_pointers(self.layout, current=None, previous=None)
            journal.complete = True
            self._write_journal(journal)
            self.record_state(
                UpdateState.RECOVERY_HOLD,
                journal.release_id,
                f"{detail}; no previous release to fall back to",
            )
            return Outcome(UpdateState.RECOVERY_HOLD, journal.release_id, detail)

        previous = ActivationRecord(**journal.old_activation)
        write_activation(self.layout, previous)
        update_display_pointers(self.layout, current=previous.release_id, previous=journal.old_previous)
        self._start_runtime(previous.runtime_mode)

        if not self._await_health(DEFAULT_HEALTH_TIMEOUT_S):
            journal.complete = True
            self._write_journal(journal)
            self.record_state(
                UpdateState.RECOVERY_HOLD,
                previous.release_id,
                "the previous release also failed its health check; runtime left disabled",
            )
            return Outcome(
                UpdateState.RECOVERY_HOLD,
                previous.release_id,
                "rollback target is unhealthy",
            )

        journal.complete = True
        self._write_journal(journal)
        self.record_state(UpdateState.ROLLED_BACK_CORE_ONLY, previous.release_id, detail)
        self._clear_journal()
        return Outcome(UpdateState.ROLLED_BACK_CORE_ONLY, previous.release_id, detail)

    # --- recovery ---------------------------------------------------------

    def recover(self) -> Outcome:
        """Finish an interrupted activation before the runtime may start.

        Called by ``rosy-release-recover.service`` on every boot. With no
        journal there is nothing to do. With an unfinished one, the device
        goes back to the activation set that was known good rather than
        booting a candidate whose health was never established.
        """
        journal = self.read_journal()
        if journal is None:
            return Outcome(UpdateState.ACTIVATED_CORE_ONLY, None, "no interrupted update")

        if journal.complete:
            self._clear_journal()
            return Outcome(
                UpdateState.ACTIVATED_CORE_ONLY,
                journal.release_id,
                "journal was already complete; cleaned up",
            )

        return self._roll_back(
            journal,
            detail="update was interrupted before the candidate was confirmed healthy",
        )


def prunable_image_digests(
    all_digests: set[str],
    *,
    activation_records: list[ActivationRecord | None],
    manifests_by_release: dict[str, dict],
) -> set[str]:
    """Digests safe to delete: everything no live activation set refers to.

    Rollback works by pointing the activation record back at the previous
    release, which is only possible while that release's container images
    still exist. A plain ``docker image prune`` does not know that, so image
    cleanup must subtract the digests named by every activation the device
    can still return to — current and previous at minimum.
    """
    protected: set[str] = set()
    for record in activation_records:
        if record is None:
            continue
        manifest = manifests_by_release.get(record.release_id)
        if manifest is None:
            # An activation whose manifest is unreadable protects nothing by
            # name, so protect conservatively: refuse to prune at all.
            return set()
        protected.update(str(d) for d in manifest.get("containers", {}).values())

    return all_digests - protected


def releases_to_keep(
    installed: list[str],
    *,
    keep_last: int,
    protected: set[str],
) -> set[str]:
    """Which release directories survive retention.

    ``protected`` holds the releases an activation record still points at.
    Those are kept regardless of age: deleting the release a device can roll
    back to converts a recoverable failure into a site visit.
    """
    ordered = sorted(installed, reverse=True)
    return set(ordered[:keep_last]) | (protected & set(installed))
