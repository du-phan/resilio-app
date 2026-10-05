import json

import pytest

from resilio.core.repository import RepositoryIO
from resilio.core.state_migration_transaction import (
    MIGRATION_TRANSACTION_PATH,
    commit_state_migration,
    recover_state_migration,
)
from resilio.core.workout_fulfillment.migration import (
    MIGRATION_TARGET_PATHS,
    WorkoutFulfillmentMigrationError,
    migrate_workout_fulfillment_state,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.manifest import load_manifest


def test_normal_state_access_is_blocked_during_incomplete_cutover(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    transaction_path = repo.resolve_path(MIGRATION_TRANSACTION_PATH)
    transaction_path.parent.mkdir(parents=True)
    transaction_path.write_text('{"state":"prepared"}\n')

    for loader in (load_manifest, load_fulfillment_manifest):
        with pytest.raises(ValueError, match="migration recovery is required"):
            loader(repo)


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
        publication_path.write_text('{"schema_version": 8}\n')
        raise KeyboardInterrupt("simulated process termination")

    with pytest.raises(KeyboardInterrupt, match="simulated process termination"):
        commit_state_migration(
            repo,
            run_id="workout-fulfillment-v2-crash",
            backup_relative_path="data/backups/workout-fulfillment-v2-crash",
            target_relative_paths=MIGRATION_TARGET_PATHS,
            apply_state=interrupted_apply,
        )

    assert repo.resolve_path(MIGRATION_TRANSACTION_PATH).exists()
    partial_bytes = publication_path.read_bytes()
    with pytest.raises(WorkoutFulfillmentMigrationError, match="dry-run mode never mutates"):
        migrate_workout_fulfillment_state(repo, apply=False)
    assert publication_path.read_bytes() == partial_bytes

    assert recover_state_migration(
        repo,
        allowed_relative_paths=set(MIGRATION_TARGET_PATHS),
    )
    assert publication_path.read_bytes() == original_publication_bytes
    assert completion_path.exists()
    assert not fulfillment_path.exists()
    audit = json.loads(
        repo.resolve_path("data/backups/workout-fulfillment-v2-crash/recovered.json").read_text()
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
        commit_state_migration(
            repo,
            run_id="workout-fulfillment-v2-proposal-crash",
            backup_relative_path=("data/backups/workout-fulfillment-v2-proposal-crash"),
            target_relative_paths=(proposal_relative_path,),
            apply_state=interrupted_apply,
        )

    assert recover_state_migration(repo)
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
        publication_path.write_text('{"schema_version": 8}\n')
        raise KeyboardInterrupt("simulated process termination")

    with pytest.raises(KeyboardInterrupt):
        commit_state_migration(
            repo,
            run_id="workout-fulfillment-v2-tamper",
            backup_relative_path="data/backups/workout-fulfillment-v2-tamper",
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
        recover_state_migration(
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
        publication_path.write_text('{"schema_version": 8}\n')
        raise KeyboardInterrupt("simulated process termination")

    with pytest.raises(KeyboardInterrupt):
        commit_state_migration(
            repo,
            run_id="workout-fulfillment-v2-missing-backup",
            backup_relative_path=("data/backups/workout-fulfillment-v2-missing-backup"),
            target_relative_paths=MIGRATION_TARGET_PATHS,
            apply_state=interrupted_apply,
        )
    transaction = json.loads(repo.resolve_path(MIGRATION_TRANSACTION_PATH).read_text())
    backup_name = transaction["files"][0]["backup_name"]
    backup_path = repo.resolve_path(
        f"data/backups/workout-fulfillment-v2-missing-backup/{backup_name}"
    )
    backup_path.unlink()
    partial_bytes = publication_path.read_bytes()

    with pytest.raises(OSError, match="backup is missing or changed"):
        recover_state_migration(
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
        commit_state_migration(
            repo,
            run_id="collision-run",
            backup_relative_path="data/backups/collision-run",
            target_relative_paths=MIGRATION_TARGET_PATHS,
            apply_state=lambda: publication_path.write_text("changed"),
        )

    assert publication_path.read_bytes() == original_bytes
    assert marker.read_text() == "preserve me"
    assert not repo.resolve_path(MIGRATION_TRANSACTION_PATH).exists()


def test_commit_rejects_unsafe_dynamic_target_before_backup_or_transaction(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    unsafe_relative_path = "data/plans/proposals/week 1.json"
    unsafe_path = repo.resolve_path(unsafe_relative_path)
    unsafe_path.parent.mkdir(parents=True)
    unsafe_path.write_text('{"preserve":"exact bytes"}\n')

    with pytest.raises(OSError, match="unsafe state target"):
        commit_state_migration(
            repo,
            run_id="unsafe-target-run",
            backup_relative_path="data/backups/unsafe-target-run",
            target_relative_paths=(unsafe_relative_path,),
            apply_state=lambda: unsafe_path.write_text("changed"),
        )

    assert unsafe_path.read_text() == '{"preserve":"exact bytes"}\n'
    assert not repo.resolve_path("data/backups/unsafe-target-run").exists()
    assert not repo.resolve_path(MIGRATION_TRANSACTION_PATH).exists()


@pytest.mark.parametrize(
    "location", ["target_parent", "dangling_leaf", "backup_parent", "journal_parent"]
)
def test_state_migration_rejects_symlink_paths_before_writes(tmp_path, monkeypatch, location):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = repo.resolve_path("data/plans/proposals/proposal.json")
    target.parent.mkdir(parents=True)
    if location == "target_parent":
        target.parent.rmdir()
        target.parent.symlink_to(outside, target_is_directory=True)
    elif location == "dangling_leaf":
        target.symlink_to(outside / "absent.json")
    elif location == "backup_parent":
        repo.resolve_path("data/backups").symlink_to(outside, target_is_directory=True)
    else:
        repo.resolve_path("data/state").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        commit_state_migration(
            repo,
            run_id="symlink-proof",
            backup_relative_path="data/backups/symlink-proof",
            target_relative_paths=("data/plans/proposals/proposal.json",),
            apply_state=lambda: target.write_text("changed"),
        )
    assert list(outside.iterdir()) == []


def test_commit_flushes_new_files_and_directory_links_before_committed_journal(
    tmp_path, monkeypatch
):
    from resilio.core import state_migration_transaction as transaction

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    relative_path = "data/plans/proposals/created.json"
    target = repo.resolve_path(relative_path)
    events = []
    original_synchronize = transaction._synchronize_file
    original_directory_synchronize = transaction._synchronize_directory
    original_write = transaction._write_transaction

    def synchronize(path):
        events.append(("synchronize", path))
        original_synchronize(path)

    def write(repo, value):
        events.append(("journal", value.phase))
        original_write(repo, value)

    def synchronize_directory(path):
        events.append(("directory", path))
        original_directory_synchronize(path)

    def apply():
        prepared_index = events.index(("journal", "prepared"))
        assert ("directory", repo.resolve_path("data")) in events[prepared_index + 1 :]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("new state")

    monkeypatch.setattr(transaction, "_synchronize_file", synchronize)
    monkeypatch.setattr(transaction, "_synchronize_directory", synchronize_directory)
    monkeypatch.setattr(transaction, "_write_transaction", write)
    commit_state_migration(
        repo,
        run_id="durable-target",
        backup_relative_path="data/backups/durable-target",
        target_relative_paths=(relative_path,),
        apply_state=apply,
    )
    assert ("synchronize", target) in events
    assert events.index(("synchronize", target)) < events.index(("journal", "committed"))


def test_normal_planning_reads_are_blocked_during_incomplete_state_migration(tmp_path, monkeypatch):
    from resilio.core.planning.state_repository import load_planning_aggregate

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    repo = RepositoryIO()
    journal = repo.resolve_path(MIGRATION_TRANSACTION_PATH)
    journal.parent.mkdir(parents=True)
    journal.write_text('{"phase":"prepared"}')
    with pytest.raises(ValueError, match="migration recovery is required"):
        load_planning_aggregate(repo)
