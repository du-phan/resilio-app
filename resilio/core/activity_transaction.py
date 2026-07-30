"""Crash-safe transaction for the activity archive and coordinated state."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeAlias, cast

from resilio.core.state_permissions import (
    ensure_private_directory_tree,
    harden_sensitive_file,
)

ACTIVITY_MUTATION_LOCK_PATH = "data/state/.activity-mutation.lock"
TRANSACTION_SCHEMA_VERSION = 2

ReplaceFunction: TypeAlias = Callable[[str | Path, str | Path], None]


class ActivityMutationError(RuntimeError):
    """The coordinated archive/state transaction could not be proven safe."""


class MutationPhase(str, Enum):
    PREPARED = "prepared"
    OLD_ARCHIVE_MOVED = "old_archive_moved"
    NEW_ARCHIVE_ACTIVE = "new_archive_active"
    SIDECARS_APPLIED = "sidecars_applied"
    COMMITTED = "committed"


@dataclass(frozen=True)
class MutationSidecar:
    """A live state path that participates in an archive switch."""

    target: Path
    backup_name: str


def _synchronize_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _synchronize_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_file():
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _synchronize_directory(path.parent)
        return
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        _synchronize_path(child)
    _synchronize_directory(path)
    _synchronize_directory(path.parent)


def _synchronize_replace(source: Path, target: Path) -> None:
    _synchronize_directory(target.parent)
    if source.parent != target.parent:
        _synchronize_directory(source.parent)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Durably replace a deterministic JSON document."""
    ensure_private_directory_tree(path.parent, path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    harden_sensitive_file(path)
    _synchronize_directory(path.parent)


def _unlink_durably(path: Path) -> None:
    if not path.exists():
        return
    path.unlink()
    _synchronize_directory(path.parent)


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    parent = path.parent
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    _synchronize_directory(parent)


def _path_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(b"file\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()
    digest.update(b"directory\0")
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode())
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _backup_sidecars(
    run_root: Path,
    sidecars: list[MutationSidecar],
) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for sidecar in sidecars:
        backup = run_root / sidecar.backup_name
        if backup.exists():
            raise ActivityMutationError(f"Unresolved activity transaction backup: {backup.name}")
        existed = sidecar.target.exists()
        kind = "directory" if existed and sidecar.target.is_dir() else "file"
        if existed:
            if kind == "directory":
                shutil.copytree(sidecar.target, backup)
            else:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sidecar.target, backup)
            _synchronize_path(backup)
        manifest.append(
            {
                "target": str(sidecar.target),
                "backup_name": sidecar.backup_name,
                "existed": existed,
                "kind": kind,
                "before_sha256": _path_sha256(sidecar.target),
                "after_sha256": None,
            }
        )
    return manifest


def _restore_sidecars(run_root: Path, sidecars: list[dict[str, Any]]) -> None:
    for sidecar in sidecars:
        target = Path(sidecar["target"])
        backup = run_root / sidecar["backup_name"]
        before_sha256 = sidecar["before_sha256"]
        if _path_sha256(target) == before_sha256:
            continue
        remove_path(target)
        if sidecar["existed"]:
            if not backup.exists():
                raise ActivityMutationError(
                    f"Activity transaction backup is missing: {backup.name}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            if sidecar["kind"] == "directory":
                shutil.copytree(backup, target)
            else:
                shutil.copy2(backup, target)
            _synchronize_path(target)
        if _path_sha256(target) != before_sha256:
            raise ActivityMutationError(f"Activity transaction could not restore {target}")


def _discard_sidecar_backups(
    run_root: Path,
    sidecars: list[dict[str, Any]],
) -> None:
    for sidecar in sidecars:
        remove_path(run_root / sidecar["backup_name"])


def _read_transaction(path: Path) -> dict[str, Any]:
    try:
        transaction = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ActivityMutationError(f"Activity mutation journal is unreadable: {exc}") from exc
    if transaction.get("schema_version") != TRANSACTION_SCHEMA_VERSION:
        raise ActivityMutationError("Unsupported activity mutation journal")
    try:
        MutationPhase(transaction["phase"])
    except (KeyError, ValueError) as exc:
        raise ActivityMutationError("Invalid activity mutation phase") from exc
    return cast(dict[str, Any], transaction)


def _record_phase(
    transaction_path: Path,
    transaction: dict[str, Any],
    phase: MutationPhase,
) -> None:
    transaction["phase"] = phase.value
    write_json(transaction_path, transaction)


def _rollback(
    *,
    active_archive: Path,
    run_root: Path,
    transaction: dict[str, Any],
    replace: ReplaceFunction,
) -> None:
    previous_archive = run_root / "previous-archive"
    interrupted_archive = run_root / "interrupted-archive"
    old_archive_sha256 = transaction["old_archive_sha256"]

    if _path_sha256(active_archive) != old_archive_sha256:
        if not previous_archive.exists():
            raise ActivityMutationError(
                "Rollback archive is absent and the active archive is not the old state"
            )
        remove_path(interrupted_archive)
        if active_archive.exists():
            replace(active_archive, interrupted_archive)
        replace(previous_archive, active_archive)
        _synchronize_replace(previous_archive, active_archive)
    if _path_sha256(active_archive) != old_archive_sha256:
        raise ActivityMutationError("Rollback did not restore the previous archive")
    _restore_sidecars(run_root, transaction["sidecars"])


def _verify_committed_state(
    *,
    active_archive: Path,
    transaction: dict[str, Any],
) -> None:
    if _path_sha256(active_archive) != transaction["new_archive_sha256"]:
        raise ActivityMutationError("Committed activity archive does not match its journal")
    for sidecar in transaction["sidecars"]:
        if _path_sha256(Path(sidecar["target"])) != sidecar["after_sha256"]:
            raise ActivityMutationError(
                f"Committed sidecar does not match its journal: {sidecar['target']}"
            )


def _finish_cleanup(
    *,
    run_root: Path,
    transaction_path: Path,
    transaction: dict[str, Any],
) -> None:
    remove_path(run_root / "previous-archive")
    _discard_sidecar_backups(run_root, transaction["sidecars"])
    write_json(run_root / "committed.json", transaction)
    _unlink_durably(transaction_path)


def recover_activity_mutation(
    *,
    active_archive: Path,
    run_root: Path,
    replace: ReplaceFunction = os.replace,
) -> bool:
    """Idempotently roll back an interrupted mutation or finish committed cleanup."""
    transaction_path = run_root / "commit.json"
    if not transaction_path.exists():
        return False
    transaction = _read_transaction(transaction_path)
    phase = MutationPhase(transaction["phase"])
    if phase is MutationPhase.COMMITTED:
        _verify_committed_state(
            active_archive=active_archive,
            transaction=transaction,
        )
        _finish_cleanup(
            run_root=run_root,
            transaction_path=transaction_path,
            transaction=transaction,
        )
        return True

    _rollback(
        active_archive=active_archive,
        run_root=run_root,
        transaction=transaction,
        replace=replace,
    )
    transaction["recovery_action"] = "rolled_back"
    write_json(run_root / "recovered.json", transaction)
    _discard_sidecar_backups(run_root, transaction["sidecars"])
    remove_path(run_root / "previous-archive")
    _unlink_durably(transaction_path)
    return True


def commit_activity_mutation(
    *,
    active_archive: Path,
    staged_archive: Path,
    run_root: Path,
    sidecars: list[MutationSidecar],
    apply_sidecars: Callable[[], None],
    replace: ReplaceFunction = os.replace,
) -> None:
    """Commit a staged state with a durable, recoverable decision point."""
    previous_archive = run_root / "previous-archive"
    transaction_path = run_root / "commit.json"
    if previous_archive.exists() or transaction_path.exists():
        raise ActivityMutationError("Activity mutation has unresolved commit state")
    if not active_archive.is_dir() or not staged_archive.is_dir():
        raise ActivityMutationError(
            "Activity mutation requires active and staged archive directories"
        )

    # The journal must never advertise bytes that have not reached stable
    # storage. This includes every staged archive file and directory entry.
    _synchronize_path(staged_archive)
    sidecar_manifest = _backup_sidecars(run_root, sidecars)
    transaction: dict[str, Any] = {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "phase": MutationPhase.PREPARED.value,
        "old_archive_sha256": _path_sha256(active_archive),
        "new_archive_sha256": _path_sha256(staged_archive),
        "sidecars": sidecar_manifest,
    }
    write_json(transaction_path, transaction)

    replace(active_archive, previous_archive)
    _synchronize_replace(active_archive, previous_archive)
    _record_phase(
        transaction_path,
        transaction,
        MutationPhase.OLD_ARCHIVE_MOVED,
    )
    try:
        replace(staged_archive, active_archive)
        _synchronize_replace(staged_archive, active_archive)
        _record_phase(
            transaction_path,
            transaction,
            MutationPhase.NEW_ARCHIVE_ACTIVE,
        )
        apply_sidecars()
        for sidecar in sidecar_manifest:
            _synchronize_path(Path(sidecar["target"]))
        for sidecar in sidecar_manifest:
            sidecar["after_sha256"] = _path_sha256(Path(sidecar["target"]))
        _record_phase(
            transaction_path,
            transaction,
            MutationPhase.SIDECARS_APPLIED,
        )
    except Exception:
        _rollback(
            active_archive=active_archive,
            run_root=run_root,
            transaction=transaction,
            replace=replace,
        )
        raise

    _record_phase(
        transaction_path,
        transaction,
        MutationPhase.COMMITTED,
    )
    _finish_cleanup(
        run_root=run_root,
        transaction_path=transaction_path,
        transaction=transaction,
    )
