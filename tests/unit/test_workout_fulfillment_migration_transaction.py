import json

import pytest

from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.migration import (
    MIGRATION_TARGET_PATHS,
    WorkoutFulfillmentMigrationError,
    migrate_workout_fulfillment_state,
)
from resilio.core.workout_fulfillment.migration_transaction import (
    MIGRATION_TRANSACTION_PATH,
    commit_workout_fulfillment_migration,
    recover_workout_fulfillment_migration,
)


def test_process_interruption_is_recovered_from_hash_verified_backups(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication_path = repo.resolve_path(MIGRATION_TARGET_PATHS[0])
    completion_path = repo.resolve_path(MIGRATION_TARGET_PATHS[1])
    fulfillment_path = repo.resolve_path(MIGRATION_TARGET_PATHS[2])
    publication_path.parent.mkdir(parents=True)
    publication_path.write_text('{"schema_version": 6}\n')
    completion_path.write_text('{"schema_version": 3, "matches": {}}\n')
    original_publication_bytes = publication_path.read_bytes()

    def interrupted_apply() -> None:
        fulfillment_path.write_text('{"schema_version": 1}\n')
        publication_path.write_text('{"schema_version": 7}\n')
        raise KeyboardInterrupt("simulated process termination")

    with pytest.raises(KeyboardInterrupt, match="simulated process termination"):
        commit_workout_fulfillment_migration(
            repo,
            run_id="workout-fulfillment-v1-crash",
            backup_relative_path="data/backups/workout-fulfillment-v1-crash",
            target_relative_paths=MIGRATION_TARGET_PATHS,
            apply_state=interrupted_apply,
        )

    assert repo.resolve_path(MIGRATION_TRANSACTION_PATH).exists()
    partial_bytes = publication_path.read_bytes()
    with pytest.raises(WorkoutFulfillmentMigrationError, match="dry-run mode never mutates"):
        migrate_workout_fulfillment_state(repo, apply=False)
    assert publication_path.read_bytes() == partial_bytes

    assert recover_workout_fulfillment_migration(
        repo,
        allowed_relative_paths=set(MIGRATION_TARGET_PATHS),
    )
    assert publication_path.read_bytes() == original_publication_bytes
    assert completion_path.exists()
    assert not fulfillment_path.exists()
    audit = json.loads(
        repo.resolve_path("data/backups/workout-fulfillment-v1-crash/recovered.json").read_text()
    )
    assert all(item["before_sha256"] for item in audit["files"] if item["existed"])


def test_recovery_accepts_exact_managed_proposal_targets(tmp_path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    proposal_relative_path = "data/plans/proposals/week-1.json"
    proposal_path = repo.resolve_path(proposal_relative_path)
    proposal_path.parent.mkdir(parents=True)
    proposal_path.write_text('{"version":"before"}\n')

    def interrupted_apply() -> None:
        proposal_path.write_text('{"version":"after"}\n')
        raise KeyboardInterrupt("simulated proposal rewrite interruption")

    with pytest.raises(KeyboardInterrupt):
        commit_workout_fulfillment_migration(
            repo,
            run_id="workout-fulfillment-v1-proposal-crash",
            backup_relative_path=("data/backups/workout-fulfillment-v1-proposal-crash"),
            target_relative_paths=(proposal_relative_path,),
            apply_state=interrupted_apply,
        )

    assert recover_workout_fulfillment_migration(repo)
    assert proposal_path.read_text() == '{"version":"before"}\n'


@pytest.mark.parametrize(
    ("field_name", "tampered_value", "error_pattern"),
    [
        ("backup_relative_path", "../outside", "backup path"),
        ("backup_name", "../publication.json", "backup name"),
    ],
)
def test_recovery_rejects_tampered_backup_paths_before_mutation(
    tmp_path,
    monkeypatch,
    field_name: str,
    tampered_value: str,
    error_pattern: str,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication_path = repo.resolve_path(MIGRATION_TARGET_PATHS[0])
    publication_path.parent.mkdir(parents=True)
    publication_path.write_text('{"schema_version": 6}\n')

    def interrupted_apply() -> None:
        publication_path.write_text('{"schema_version": 7}\n')
        raise KeyboardInterrupt("simulated process termination")

    with pytest.raises(KeyboardInterrupt):
        commit_workout_fulfillment_migration(
            repo,
            run_id="workout-fulfillment-v1-tamper",
            backup_relative_path="data/backups/workout-fulfillment-v1-tamper",
            target_relative_paths=MIGRATION_TARGET_PATHS,
            apply_state=interrupted_apply,
        )
    transaction_path = repo.resolve_path(MIGRATION_TRANSACTION_PATH)
    transaction = json.loads(transaction_path.read_text())
    if field_name == "backup_name":
        transaction["files"][0][field_name] = tampered_value
    else:
        transaction[field_name] = tampered_value
    transaction_path.write_text(json.dumps(transaction))
    partial_bytes = publication_path.read_bytes()

    with pytest.raises(OSError, match=error_pattern):
        recover_workout_fulfillment_migration(
            repo,
            allowed_relative_paths=set(MIGRATION_TARGET_PATHS),
        )

    assert publication_path.read_bytes() == partial_bytes


def test_recovery_validates_every_backup_before_removing_any_target(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication_path = repo.resolve_path(MIGRATION_TARGET_PATHS[0])
    publication_path.parent.mkdir(parents=True)
    publication_path.write_text('{"schema_version": 6}\n')

    def interrupted_apply() -> None:
        publication_path.write_text('{"schema_version": 7}\n')
        raise KeyboardInterrupt("simulated process termination")

    with pytest.raises(KeyboardInterrupt):
        commit_workout_fulfillment_migration(
            repo,
            run_id="workout-fulfillment-v1-missing-backup",
            backup_relative_path=("data/backups/workout-fulfillment-v1-missing-backup"),
            target_relative_paths=MIGRATION_TARGET_PATHS,
            apply_state=interrupted_apply,
        )
    transaction = json.loads(repo.resolve_path(MIGRATION_TRANSACTION_PATH).read_text())
    backup_name = transaction["files"][0]["backup_name"]
    backup_path = repo.resolve_path(
        f"data/backups/workout-fulfillment-v1-missing-backup/{backup_name}"
    )
    backup_path.unlink()
    partial_bytes = publication_path.read_bytes()

    with pytest.raises(OSError, match="backup is missing or changed"):
        recover_workout_fulfillment_migration(
            repo,
            allowed_relative_paths=set(MIGRATION_TARGET_PATHS),
        )

    assert publication_path.read_bytes() == partial_bytes


def test_commit_rejects_preexisting_backup_directory_before_any_write(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    publication_path = repo.resolve_path(MIGRATION_TARGET_PATHS[0])
    publication_path.parent.mkdir(parents=True)
    publication_path.write_text('{"schema_version": 6}\n')
    original_bytes = publication_path.read_bytes()
    backup_root = repo.resolve_path("data/backups/collision-run")
    backup_root.mkdir(parents=True)
    marker = backup_root / "user-owned.txt"
    marker.write_text("preserve me")

    with pytest.raises(OSError, match="backup directory already exists"):
        commit_workout_fulfillment_migration(
            repo,
            run_id="collision-run",
            backup_relative_path="data/backups/collision-run",
            target_relative_paths=MIGRATION_TARGET_PATHS,
            apply_state=lambda: publication_path.write_text("changed"),
        )

    assert publication_path.read_bytes() == original_bytes
    assert marker.read_text() == "preserve me"
    assert not repo.resolve_path(MIGRATION_TRANSACTION_PATH).exists()
