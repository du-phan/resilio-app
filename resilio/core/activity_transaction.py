"""Shared atomic transaction for canonical activity archive mutations."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeAlias

ACTIVITY_MUTATION_LOCK_PATH = "data/state/.activity-mutation.lock"

ReplaceFunction: TypeAlias = Callable[[str | Path, str | Path], None]


class ActivityMutationError(RuntimeError):
    """The coordinated archive/state transaction could not be proven safe."""


@dataclass(frozen=True)
class MutationSidecar:
    """A live state path that participates in an archive switch."""

    target: Path
    backup_name: str


def write_json(path: Path, payload: dict) -> None:
    """Atomically write a deterministic JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _backup_sidecars(run_root: Path, sidecars: list[MutationSidecar]) -> list[dict]:
    manifest: list[dict] = []
    for sidecar in sidecars:
        backup = run_root / sidecar.backup_name
        if backup.exists():
            raise ActivityMutationError(
                f"Unresolved activity transaction backup: {backup.name}"
            )
        existed = sidecar.target.exists()
        kind = "directory" if existed and sidecar.target.is_dir() else "file"
        if existed:
            if kind == "directory":
                shutil.copytree(sidecar.target, backup)
            else:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sidecar.target, backup)
        manifest.append(
            {
                "target": str(sidecar.target),
                "backup_name": sidecar.backup_name,
                "existed": existed,
                "kind": kind,
            }
        )
    return manifest


def _restore_sidecars(run_root: Path, sidecars: list[dict]) -> None:
    for sidecar in sidecars:
        target = Path(sidecar["target"])
        backup = run_root / sidecar["backup_name"]
        remove_path(target)
        if sidecar["existed"]:
            if not backup.exists():
                raise ActivityMutationError(
                    f"Activity transaction backup is missing: {backup.name}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, target)


def _discard_sidecar_backups(run_root: Path, sidecars: list[dict]) -> None:
    for sidecar in sidecars:
        remove_path(run_root / sidecar["backup_name"])


def recover_activity_mutation(
    *,
    active_archive: Path,
    run_root: Path,
    replace: ReplaceFunction = os.replace,
) -> bool:
    """Restore a displaced archive and coordinated state after interruption."""
    previous_archive = run_root / "previous-archive"
    transaction_path = run_root / "commit.json"
    if not previous_archive.exists():
        if transaction_path.exists():
            transaction = json.loads(transaction_path.read_text())
            if transaction.get("phase") != "rolled_back":
                raise ActivityMutationError(
                    "Activity mutation manifest exists without its previous archive"
                )
            _discard_sidecar_backups(run_root, transaction["sidecars"])
            transaction_path.unlink()
        return False
    if not transaction_path.exists():
        raise ActivityMutationError(
            "Interrupted activity mutation lacks its recovery manifest"
        )
    transaction = json.loads(transaction_path.read_text())
    interrupted_archive = run_root / "interrupted-archive"
    remove_path(interrupted_archive)
    if active_archive.exists():
        replace(active_archive, interrupted_archive)
    replace(previous_archive, active_archive)
    _restore_sidecars(run_root, transaction["sidecars"])
    transaction["phase"] = "recovered"
    write_json(run_root / "recovered.json", transaction)
    transaction_path.unlink()
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
    """Atomically switch a staged archive with rollback-proven sidecar writes."""
    previous_archive = run_root / "previous-archive"
    transaction_path = run_root / "commit.json"
    if previous_archive.exists() or transaction_path.exists():
        raise ActivityMutationError(
            "Activity mutation has unresolved commit state"
        )
    if not active_archive.is_dir() or not staged_archive.is_dir():
        raise ActivityMutationError(
            "Activity mutation requires active and staged archive directories"
        )

    sidecar_manifest = _backup_sidecars(run_root, sidecars)
    transaction = {
        "schema_version": 1,
        "phase": "prepared",
        "sidecars": sidecar_manifest,
    }
    write_json(transaction_path, transaction)

    replace(active_archive, previous_archive)
    try:
        replace(staged_archive, active_archive)
        apply_sidecars()
    except Exception:
        failed_archive = run_root / "failed-archive"
        remove_path(failed_archive)
        if active_archive.exists():
            replace(active_archive, failed_archive)
        replace(previous_archive, active_archive)
        _restore_sidecars(run_root, sidecar_manifest)
        transaction["phase"] = "rolled_back"
        write_json(transaction_path, transaction)
        raise

    shutil.rmtree(previous_archive)
    _discard_sidecar_backups(run_root, sidecar_manifest)
    transaction["phase"] = "committed"
    write_json(run_root / "committed.json", transaction)
    transaction_path.unlink()
