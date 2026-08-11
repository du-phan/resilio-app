"""Crash-recoverable file transaction for the fulfillment cutover."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from resilio.core.activity_transaction import remove_path, write_json
from resilio.core.repository import RepositoryIO
from resilio.core.state_permissions import ensure_private_directory_tree, harden_sensitive_file
from resilio.core.workout_fulfillment.cutover_guard import MIGRATION_TRANSACTION_PATH
from resilio.schemas.repository import RepoError

_FIXED_MIGRATION_TARGETS = frozenset(
    {
        "data/state/workout_publications.json",
        "data/state/workout_completions.json",
        "data/state/workout_fulfillments.json",
        "data/state/workout-fulfillment-planning-evidence-migration.json",
        "data/plans/planning_state.yaml",
    }
)


class MigrationFileState(BaseModel):
    relative_path: str = Field(min_length=1)
    backup_name: str = Field(min_length=1)
    existed: bool
    before_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    after_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class WorkoutFulfillmentMigrationTransaction(BaseModel):
    schema_version: Literal[1] = 1
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    phase: Literal["prepared", "committed"]
    backup_relative_path: str = Field(min_length=1)
    files: list[MigrationFileState] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise OSError(f"Migration state path is not a regular file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synchronize_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory_descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _load_transaction(
    repo: RepositoryIO,
) -> WorkoutFulfillmentMigrationTransaction | None:
    result = repo.read_json(
        MIGRATION_TRANSACTION_PATH,
        WorkoutFulfillmentMigrationTransaction,
    )
    if result is None:
        return None
    if isinstance(result, RepoError):
        raise OSError(f"Fulfillment migration transaction is invalid: {result}")
    return result


def _write_transaction(
    repo: RepositoryIO,
    transaction: WorkoutFulfillmentMigrationTransaction,
) -> None:
    write_json(
        repo.resolve_path(MIGRATION_TRANSACTION_PATH),
        transaction.model_dump(mode="json"),
    )


def _validated_targets(
    repo: RepositoryIO,
    transaction: WorkoutFulfillmentMigrationTransaction,
    allowed_relative_paths: set[str] | None,
) -> list[tuple[MigrationFileState, Path, Path]]:
    relative_paths = [item.relative_path for item in transaction.files]
    if len(relative_paths) != len(set(relative_paths)):
        raise OSError("Fulfillment migration transaction targets must be unique")
    if allowed_relative_paths is not None and set(relative_paths) != allowed_relative_paths:
        raise OSError("Fulfillment migration transaction targets are not the expected state set")
    if allowed_relative_paths is None and any(
        not _is_safe_migration_target(path) for path in relative_paths
    ):
        raise OSError("Fulfillment migration transaction contains an unsafe state target")
    backup_root = _validated_backup_root(
        repo,
        run_id=transaction.run_id,
        backup_relative_path=transaction.backup_relative_path,
    )
    targets: list[tuple[MigrationFileState, Path, Path]] = []
    for item in transaction.files:
        expected_backup_name = _backup_name(item.relative_path)
        if (
            item.backup_name != expected_backup_name
            or Path(item.backup_name).name != item.backup_name
        ):
            raise OSError("Fulfillment migration backup name does not match its state target")
        targets.append(
            (
                item,
                repo.resolve_path(item.relative_path),
                backup_root / item.backup_name,
            )
        )
    return targets


def _is_safe_migration_target(relative_path: str) -> bool:
    if relative_path in _FIXED_MIGRATION_TARGETS:
        return True
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or str(path) != relative_path:
        return False
    if len(path.parts) == 4 and path.parts[:3] == ("data", "plans", "archive"):
        return bool(re.fullmatch(r"plan_[A-Za-z0-9_-]{1,120}\.json", path.name))
    if len(path.parts) == 4 and path.parts[:3] == ("data", "plans", "proposals"):
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json", path.name))
    if len(path.parts) == 5 and path.parts[:3] == ("data", "plans", "evidence"):
        return bool(
            re.fullmatch(r"[a-z_]+", path.parts[3])
            and re.fullmatch(r"[0-9a-f]{64}\.json", path.name)
        )
    return False


def validate_migration_target_paths(target_relative_paths: tuple[str, ...]) -> None:
    """Reject unsafe or duplicate transaction targets before any local write."""
    if not target_relative_paths:
        raise OSError("Fulfillment migration requires at least one state target")
    if len(target_relative_paths) != len(set(target_relative_paths)):
        raise OSError("Fulfillment migration state targets must be unique")
    unsafe_paths = [
        relative_path
        for relative_path in target_relative_paths
        if not _is_safe_migration_target(relative_path)
    ]
    if unsafe_paths:
        raise OSError(
            "Fulfillment migration contains an unsafe state target: "
            f"{unsafe_paths[0]}"
        )


def _backup_name(relative_path: str) -> str:
    path_digest = hashlib.sha256(relative_path.encode()).hexdigest()[:16]
    return f"{path_digest}-{Path(relative_path).name}"


def _validated_backup_root(
    repo: RepositoryIO,
    *,
    run_id: str,
    backup_relative_path: str,
) -> Path:
    expected_relative_path = f"data/backups/{run_id}"
    if backup_relative_path != expected_relative_path:
        raise OSError("Fulfillment migration backup path does not match its run ID")
    backups_root = repo.resolve_path("data/backups").resolve()
    backup_root = repo.resolve_path(backup_relative_path).resolve()
    if backup_root.parent != backups_root or backup_root.name != run_id:
        raise OSError("Fulfillment migration backup path escapes the backup directory")
    return backup_root


def recover_workout_fulfillment_migration(
    repo: RepositoryIO,
    *,
    allowed_relative_paths: set[str] | None = None,
) -> bool:
    """Rollback an interrupted cutover or verify a committed cutover."""
    transaction = _load_transaction(repo)
    if transaction is None:
        return False
    targets = _validated_targets(repo, transaction, allowed_relative_paths)
    if transaction.phase == "committed":
        for state, target, _ in targets:
            if _file_sha256(target) != state.after_sha256:
                raise OSError("Committed fulfillment migration state changed before recovery")
        audit_name = "committed.json"
    else:
        for state, _, backup in targets:
            if state.existed and (
                not backup.exists() or _file_sha256(backup) != state.before_sha256
            ):
                raise OSError("Fulfillment migration backup is missing or changed")
        for state, target, backup in targets:
            remove_path(target)
            if state.existed:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
                harden_sensitive_file(target)
                _synchronize_file(target)
            if _file_sha256(target) != state.before_sha256:
                raise OSError("Fulfillment migration rollback did not restore exact bytes")
        audit_name = "recovered.json"
    backup_root = _validated_backup_root(
        repo,
        run_id=transaction.run_id,
        backup_relative_path=transaction.backup_relative_path,
    )
    write_json(backup_root / audit_name, transaction.model_dump(mode="json"))
    remove_path(repo.resolve_path(MIGRATION_TRANSACTION_PATH))
    return True


def commit_workout_fulfillment_migration(
    repo: RepositoryIO,
    *,
    run_id: str,
    backup_relative_path: str,
    target_relative_paths: tuple[str, ...],
    apply_state: Callable[[], None],
) -> None:
    """Apply fixed state files behind a durable rollback decision point."""
    validate_migration_target_paths(target_relative_paths)
    if _load_transaction(repo) is not None:
        raise OSError("Fulfillment migration has unresolved transaction state")
    backup_root = _validated_backup_root(
        repo,
        run_id=run_id,
        backup_relative_path=backup_relative_path,
    )
    if backup_root.exists():
        raise OSError("Fulfillment migration backup directory already exists")
    ensure_private_directory_tree(repo.resolve_path("data"), backup_root)
    files: list[MigrationFileState] = []
    for relative_path in target_relative_paths:
        target = repo.resolve_path(relative_path)
        backup_name = _backup_name(relative_path)
        backup = backup_root / backup_name
        before_sha256 = _file_sha256(target)
        if target.exists():
            shutil.copy2(target, backup)
            harden_sensitive_file(backup)
            _synchronize_file(backup)
        files.append(
            MigrationFileState(
                relative_path=relative_path,
                backup_name=backup_name,
                existed=target.exists(),
                before_sha256=before_sha256,
            )
        )
    transaction = WorkoutFulfillmentMigrationTransaction(
        run_id=run_id,
        phase="prepared",
        backup_relative_path=backup_relative_path,
        files=files,
    )
    _write_transaction(repo, transaction)
    try:
        apply_state()
    except Exception:
        recover_workout_fulfillment_migration(
            repo,
            allowed_relative_paths=set(target_relative_paths),
        )
        raise
    committed = transaction.model_copy(
        update={
            "phase": "committed",
            "files": [
                state.model_copy(
                    update={"after_sha256": _file_sha256(repo.resolve_path(state.relative_path))}
                )
                for state in files
            ],
        }
    )
    _write_transaction(repo, committed)
    recover_workout_fulfillment_migration(
        repo,
        allowed_relative_paths=set(target_relative_paths),
    )
