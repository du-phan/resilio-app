"""Crash-recovery specifications for coordinated activity-state mutation."""

from pathlib import Path

import pytest

from resilio.core.activity_transaction import (
    MutationPhase,
    MutationSidecar,
    commit_activity_mutation,
    recover_activity_mutation,
)


def _write_marker(directory: Path, value: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "marker.txt").write_text(value)


def test_recovery_rolls_forward_after_crash_during_post_commit_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_archive = tmp_path / "activities"
    staged_archive = tmp_path / "staged-activities"
    run_root = tmp_path / "transaction"
    sidecar = tmp_path / "activity-sync.json"
    _write_marker(active_archive, "old")
    _write_marker(staged_archive, "new")
    sidecar.write_text("old-sidecar")

    from resilio.core import activity_transaction

    original_rmtree = activity_transaction.shutil.rmtree
    crashed = False

    def crash_after_delete(path: Path) -> None:
        nonlocal crashed
        original_rmtree(path)
        if Path(path).name == "previous-archive" and not crashed:
            crashed = True
            raise RuntimeError("injected crash after previous archive deletion")

    monkeypatch.setattr(activity_transaction.shutil, "rmtree", crash_after_delete)

    with pytest.raises(RuntimeError, match="injected crash"):
        commit_activity_mutation(
            active_archive=active_archive,
            staged_archive=staged_archive,
            run_root=run_root,
            sidecars=[
                MutationSidecar(
                    target=sidecar,
                    backup_name="previous-sync-state",
                )
            ],
            apply_sidecars=lambda: sidecar.write_text("new-sidecar"),
        )

    monkeypatch.setattr(activity_transaction.shutil, "rmtree", original_rmtree)

    assert recover_activity_mutation(
        active_archive=active_archive,
        run_root=run_root,
    )
    assert (active_archive / "marker.txt").read_text() == "new"
    assert sidecar.read_text() == "new-sidecar"
    assert not recover_activity_mutation(
        active_archive=active_archive,
        run_root=run_root,
    )


@pytest.mark.parametrize(
    ("crash_phase", "expected_marker", "expected_sidecar"),
    [
        (MutationPhase.OLD_ARCHIVE_MOVED, "old", "old-sidecar"),
        (MutationPhase.NEW_ARCHIVE_ACTIVE, "old", "old-sidecar"),
        (MutationPhase.SIDECARS_APPLIED, "old", "old-sidecar"),
        (MutationPhase.COMMITTED, "new", "new-sidecar"),
    ],
)
def test_every_durable_phase_recovers_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_phase: MutationPhase,
    expected_marker: str,
    expected_sidecar: str,
) -> None:
    active_archive = tmp_path / "activities"
    staged_archive = tmp_path / "staged-activities"
    run_root = tmp_path / "transaction"
    sidecar = tmp_path / "activity-sync.json"
    _write_marker(active_archive, "old")
    _write_marker(staged_archive, "new")
    sidecar.write_text("old-sidecar")

    from resilio.core import activity_transaction

    original_record_phase = activity_transaction._record_phase

    def crash_after_phase(path, transaction, phase):
        original_record_phase(path, transaction, phase)
        if phase is crash_phase:
            raise KeyboardInterrupt(f"injected crash after {phase.value}")

    monkeypatch.setattr(
        activity_transaction,
        "_record_phase",
        crash_after_phase,
    )

    with pytest.raises(KeyboardInterrupt, match=crash_phase.value):
        commit_activity_mutation(
            active_archive=active_archive,
            staged_archive=staged_archive,
            run_root=run_root,
            sidecars=[
                MutationSidecar(
                    target=sidecar,
                    backup_name="previous-sync-state",
                )
            ],
            apply_sidecars=lambda: sidecar.write_text("new-sidecar"),
        )

    monkeypatch.setattr(
        activity_transaction,
        "_record_phase",
        original_record_phase,
    )

    assert recover_activity_mutation(
        active_archive=active_archive,
        run_root=run_root,
    )
    assert (active_archive / "marker.txt").read_text() == expected_marker
    assert sidecar.read_text() == expected_sidecar
    assert not recover_activity_mutation(
        active_archive=active_archive,
        run_root=run_root,
    )


def test_prepared_phase_recovers_when_first_archive_move_never_occurs(
    tmp_path: Path,
) -> None:
    active_archive = tmp_path / "activities"
    staged_archive = tmp_path / "staged-activities"
    run_root = tmp_path / "transaction"
    sidecar = tmp_path / "activity-sync.json"
    _write_marker(active_archive, "old")
    _write_marker(staged_archive, "new")
    sidecar.write_text("old-sidecar")

    def crash_before_replace(_source, _target):
        raise KeyboardInterrupt("injected crash before first archive move")

    with pytest.raises(KeyboardInterrupt, match="first archive move"):
        commit_activity_mutation(
            active_archive=active_archive,
            staged_archive=staged_archive,
            run_root=run_root,
            sidecars=[
                MutationSidecar(
                    target=sidecar,
                    backup_name="previous-sync-state",
                )
            ],
            apply_sidecars=lambda: sidecar.write_text("new-sidecar"),
            replace=crash_before_replace,
        )

    assert recover_activity_mutation(
        active_archive=active_archive,
        run_root=run_root,
    )
    assert (active_archive / "marker.txt").read_text() == "old"
    assert sidecar.read_text() == "old-sidecar"
