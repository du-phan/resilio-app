"""Validated, backed-up, crash-safe evidence-state cutover."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_transaction import (
    ACTIVITY_MUTATION_LOCK_PATH,
    MutationSidecar,
    commit_activity_mutation,
    remove_path,
)
from resilio.core.evidence_migration.transform import (
    invalidate_stale_activity_mapping,
    transform_activity_v4,
    transform_wellness_v1,
)
from resilio.core.locking import OperationLock
from resilio.core.repository import RepositoryIO
from resilio.core.state_permissions import (
    ensure_private_directory_tree,
    harden_sensitive_file,
)
from resilio.schemas.activity import ACTIVITY_CANONICAL_MAPPING_VERSION, CanonicalActivity
from resilio.schemas.training_state import WellnessDay

_WELLNESS_DAYS = TypeAdapter(list[WellnessDay])
_LEGACY_EVIDENCE_KEYS = {
    "canonical_activity_sha256",
    "external_fingerprint_sha256",
    "provider_activity_fingerprint_sha256",
    "source_external_fingerprint_sha256",
}


class EvidenceMigrationError(RuntimeError):
    """The cutover could not be proven complete and no live state was changed."""


@dataclass(frozen=True)
class EvidenceMigrationReport:
    run_id: str
    activity_count: int
    wellness_day_count: int
    changes_required: bool
    applied: bool
    backup_relative_path: str


def _tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_activities(root: Path) -> tuple[list[CanonicalActivity], bool]:
    activities: list[CanonicalActivity] = []
    changes_required = False
    for path in sorted(root.glob("*/*.yaml")):
        if path.is_symlink():
            raise EvidenceMigrationError(f"Activity source cannot be a symlink: {path}")
        try:
            raw = yaml.safe_load(path.read_text())
            version = raw.get("_schema", {}).get("version")
            mapping_version = raw.get("audit", {}).get("canonical_mapping_version")
            changes_required = changes_required or version == 4 or (
                version == 5
                and mapping_version not in {None, ACTIVITY_CANONICAL_MAPPING_VERSION}
            )
            activity = (
                transform_activity_v4(raw)
                if version == 4
                else invalidate_stale_activity_mapping(raw)
                if version == 5
                else None
            )
        except Exception as exc:
            raise EvidenceMigrationError(f"Invalid activity migration source: {path}") from exc
        if activity is None:
            raise EvidenceMigrationError(f"Unsupported activity schema version: {path}")
        activities.append(activity)
    return activities, changes_required


def _load_wellness(root: Path) -> tuple[list[WellnessDay], bool]:
    rows: list[WellnessDay] = []
    changes_required = False
    for path in sorted(root.glob("????-??.json")):
        if path.is_symlink():
            raise EvidenceMigrationError(f"Wellness source cannot be a symlink: {path}")
        try:
            payload = json.loads(path.read_text())
            for raw in payload:
                changes_required = changes_required or raw.get("schema_version") != 2
                rows.append(
                    WellnessDay.model_validate(raw)
                    if raw.get("schema_version") == 2
                    else transform_wellness_v1(raw)
                )
        except Exception as exc:
            raise EvidenceMigrationError(f"Invalid wellness migration source: {path}") from exc
    if len({row.local_date for row in rows}) != len(rows):
        raise EvidenceMigrationError("Wellness migration source has duplicate local dates")
    return rows, changes_required


def _legacy_evidence_paths(repo: RepositoryIO) -> list[Path]:
    plans_root = repo.resolve_path("data/plans")
    if not plans_root.exists():
        return []
    legacy: list[Path] = []
    for path in sorted(item for item in plans_root.rglob("*") if item.is_file()):
        if path.suffix not in {".json", ".yaml", ".yml"}:
            continue
        text = path.read_text()
        if any(key in text for key in _LEGACY_EVIDENCE_KEYS):
            legacy.append(path)
    return legacy


def _stage_activities(root: Path, activities: list[CanonicalActivity]) -> None:
    archive = ActivityArchive(root)
    for activity in activities:
        archive.write(activity)
    if len(archive.load_all()) != len(activities):
        raise EvidenceMigrationError("Staged activity count changed during validation")


def _stage_wellness(
    repo: RepositoryIO,
    root: Path,
    rows: list[WellnessDay],
) -> None:
    ensure_private_directory_tree(repo.resolve_path("data"), root)
    grouped: dict[str, list[WellnessDay]] = defaultdict(list)
    for row in rows:
        grouped[row.local_date.strftime("%Y-%m")].append(row)
    for year_month, month_rows in sorted(grouped.items()):
        payload = [
            row.model_dump(mode="json")
            for row in sorted(month_rows, key=lambda item: item.local_date)
        ]
        error = repo.write_json(root / f"{year_month}.json", payload)
        if error is not None:
            raise EvidenceMigrationError(f"Could not stage wellness {year_month}: {error}")
    validated = [
        row
        for path in sorted(root.glob("*.json"))
        for row in _WELLNESS_DAYS.validate_json(path.read_bytes())
    ]
    if len(validated) != len(rows):
        raise EvidenceMigrationError("Staged wellness count changed during validation")


def _copy_verified(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink():
        raise EvidenceMigrationError(f"Backup source cannot be a symlink: {source}")
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    source_digest = (
        _tree_sha256(source) if source.is_dir() else hashlib.sha256(source.read_bytes()).hexdigest()
    )
    target_digest = (
        _tree_sha256(target) if target.is_dir() else hashlib.sha256(target.read_bytes()).hexdigest()
    )
    if source_digest != target_digest:
        raise EvidenceMigrationError(f"Backup verification failed for {source}")


def _harden_tree(root: Path) -> None:
    for path in [root, *sorted(root.rglob("*"))]:
        if path.is_symlink():
            raise EvidenceMigrationError(f"Migration state cannot be a symlink: {path}")
        if path.is_dir():
            path.chmod(0o700)
        elif path.is_file():
            harden_sensitive_file(path)


def _backup_live_state(repo: RepositoryIO, backup_root: Path) -> None:
    data_root = repo.resolve_path("data")
    ensure_private_directory_tree(data_root, backup_root)
    for relative_path in ("activities", "wellness", "state", "plans", "athlete"):
        _copy_verified(data_root / relative_path, backup_root / relative_path)
    _harden_tree(backup_root)


def _run_id(timestamp: datetime) -> str:
    return "migration-" + timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def migrate_evidence_state(
    repo: RepositoryIO,
    *,
    apply: bool,
    migrated_at_utc: datetime | None = None,
) -> EvidenceMigrationReport:
    """Validate a dry run or atomically apply the v5/v2 coordinated cutover."""
    timestamp = migrated_at_utc or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise EvidenceMigrationError("Migration timestamp must be timezone-aware")
    activities_root = repo.resolve_path("data/activities")
    wellness_root = repo.resolve_path("data/wellness")
    activities, activity_changes_required = _load_activities(activities_root)
    wellness, wellness_changes_required = _load_wellness(wellness_root)
    changes_required = activity_changes_required or wellness_changes_required
    legacy_paths = _legacy_evidence_paths(repo)
    if legacy_paths:
        names = ", ".join(str(path.relative_to(repo.repo_root)) for path in legacy_paths)
        raise EvidenceMigrationError(
            "Immutable activity evidence requires an explicit evidence rebuild before "
            f"migration: {names}"
        )
    run_id = _run_id(timestamp)
    backup_relative = Path("data/backups/evidence-v5") / run_id
    report = EvidenceMigrationReport(
        run_id=run_id,
        activity_count=len(activities),
        wellness_day_count=len(wellness),
        changes_required=changes_required,
        applied=apply and changes_required,
        backup_relative_path=(
            backup_relative.as_posix() if apply and changes_required else ""
        ),
    )
    if not report.applied:
        return report
    data_root = repo.resolve_path("data")
    run_root = data_root / "migrations/evidence-v5" / run_id
    staged_activities = run_root / "staged-activities"
    staged_wellness = run_root / "staged-wellness"
    backup_root = repo.resolve_path(backup_relative)
    lock_path = repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH)
    with OperationLock(lock_path, "evidence-v5-migration"):
        if run_root.exists() or backup_root.exists():
            raise EvidenceMigrationError(f"Migration run ID already exists: {run_id}")
        ensure_private_directory_tree(data_root, run_root)
        try:
            _stage_activities(staged_activities, activities)
            _stage_wellness(repo, staged_wellness, wellness)
            _backup_live_state(repo, backup_root)
            _harden_tree(staged_activities)
            _harden_tree(staged_wellness)
            error = repo.write_json(run_root / "report.json", asdict(report))
            if error is not None:
                raise EvidenceMigrationError(f"Could not write migration report: {error}")

            def apply_wellness() -> None:
                remove_path(wellness_root)
                os.replace(staged_wellness, wellness_root)

            commit_activity_mutation(
                active_archive=activities_root,
                staged_archive=staged_activities,
                run_root=run_root,
                sidecars=[
                    MutationSidecar(
                        target=wellness_root,
                        backup_name="previous-wellness",
                    )
                ],
                apply_sidecars=apply_wellness,
            )
            return report
        except Exception:
            has_recovery_state = (run_root / "commit.json").exists() or (
                run_root / "committed.json"
            ).exists()
            if not has_recovery_state:
                remove_path(run_root)
                remove_path(backup_root)
            raise
