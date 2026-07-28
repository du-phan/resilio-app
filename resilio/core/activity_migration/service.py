"""Restartable backup, stage, reconcile, apply, and rollback state machine."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import yaml

from resilio.core.activity_migration.transform import transform_activity
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.migration import (
    ArchiveTotals,
    MigrationReconciliation,
    MigrationRunEnvelope,
)


class MigrationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _atomic_yaml(path: Path, activity: CanonicalActivity) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = activity.model_dump(mode="json", by_alias=True)
    content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _manifest(files: Iterable[Path], root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(files)
        if path.is_file()
    }


def _manifest_digest(manifest: dict[str, str]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _quantized(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def _source_totals(records: list[dict[str, Any]]) -> ArchiveTotals:
    dates = [date.fromisoformat(str(item["date"])) for item in records]
    sports = Counter(str(item["sport_type"]) for item in records)
    screenshots = [
        item
        for item in records
        if str(item.get("id", "")).startswith("manual_screenshot_")
    ]
    screenshot_dates = [date.fromisoformat(str(item["date"])) for item in screenshots]
    distance = sum(
        (Decimal(str(item.get("distance_meters") or 0)) for item in records),
        Decimal(),
    )
    elevation = sum(
        (Decimal(str(item.get("elevation_gain_m") or 0)) for item in records),
        Decimal(),
    )
    systemic = sum(
        (
            Decimal(str((item.get("calculated") or {}).get("systemic_load_au") or 0))
            for item in records
        ),
        Decimal(),
    )
    lower = sum(
        (
            Decimal(str((item.get("calculated") or {}).get("lower_body_load_au") or 0))
            for item in records
        ),
        Decimal(),
    )
    return ArchiveTotals(
        record_count=len(records),
        earliest_date=min(dates) if dates else None,
        latest_date=max(dates) if dates else None,
        sport_counts=dict(sorted(sports.items())),
        duration_seconds=sum(int(item["duration_seconds"]) for item in records),
        distance_meters=_quantized(distance),
        elevation_gain_meters=_quantized(elevation),
        systemic_load_au=_quantized(systemic),
        lower_body_load_au=_quantized(lower),
        screenshot_record_count=len(screenshots),
        screenshot_sport_counts=dict(
            sorted(Counter(str(item["sport_type"]) for item in screenshots).items())
        ),
        screenshot_earliest_date=min(screenshot_dates) if screenshot_dates else None,
        screenshot_latest_date=max(screenshot_dates) if screenshot_dates else None,
    )


def _candidate_totals(records: list[CanonicalActivity]) -> ArchiveTotals:
    dates = [item.date for item in records]
    screenshots = [
        item
        for item in records
        if item.origin.recording_provider == "manual"
        and item.audit.external_fingerprint_sha256 is None
        and item.date >= date(2026, 4, 7)
    ]
    return ArchiveTotals(
        record_count=len(records),
        earliest_date=min(dates) if dates else None,
        latest_date=max(dates) if dates else None,
        sport_counts=dict(sorted(Counter(item.sport_type for item in records).items())),
        duration_seconds=sum(item.duration_seconds for item in records),
        distance_meters=_quantized(
            sum((Decimal(str(item.distance_meters or 0)) for item in records), Decimal())
        ),
        elevation_gain_meters=_quantized(
            sum(
                (Decimal(str(item.elevation_gain_meters or 0)) for item in records),
                Decimal(),
            )
        ),
        systemic_load_au=_quantized(
            sum(
                (
                    Decimal(str(item.calculated.systemic_load_au))
                    if item.calculated
                    else Decimal()
                    for item in records
                ),
                Decimal(),
            )
        ),
        lower_body_load_au=_quantized(
            sum(
                (
                    Decimal(str(item.calculated.lower_body_load_au))
                    if item.calculated
                    else Decimal()
                    for item in records
                ),
                Decimal(),
            )
        ),
        screenshot_record_count=len(screenshots),
        screenshot_sport_counts=dict(
            sorted(Counter(item.sport_type for item in screenshots).items())
        ),
        screenshot_earliest_date=min((item.date for item in screenshots), default=None),
        screenshot_latest_date=max((item.date for item in screenshots), default=None),
    )


def _restore_historical_facts(
    baseline: CanonicalActivity,
    linked: CanonicalActivity,
) -> CanonicalActivity:
    """Restore immutable migrated facts while retaining safe external enrichment."""
    if baseline.local_activity_id != linked.local_activity_id:
        raise MigrationError("Historical repair local IDs do not match")
    if (
        baseline.origin.kind != "historical_import"
        or linked.origin.kind != "historical_import"
    ):
        raise MigrationError("Historical repair requires historical_import records")
    repaired = baseline.model_copy(
        update={
            "status": linked.status,
            "source_sport_type": linked.source_sport_type,
            "source_sport_subtype": (
                baseline.source_sport_subtype
                or linked.source_sport_subtype
            ),
            "distance_meters": (
                baseline.distance_meters
                if baseline.distance_meters is not None
                else linked.distance_meters
            ),
            "elevation_gain_meters": (
                baseline.elevation_gain_meters
                if baseline.elevation_gain_meters is not None
                else linked.elevation_gain_meters
            ),
            "heart_rate": baseline.heart_rate or linked.heart_rate,
            "power": baseline.power or linked.power,
            "cadence": baseline.cadence or linked.cadence,
            "perceived_effort": (
                baseline.perceived_effort or linked.perceived_effort
            ),
            "device": baseline.device.model_copy(
                update={
                    "name": baseline.device.name or linked.device.name,
                    "gear_external_id": (
                        baseline.device.gear_external_id
                        or linked.device.gear_external_id
                    ),
                }
            ),
            "segments": baseline.segments or linked.segments,
            "origin": linked.origin.model_copy(
                update={
                    "recording_provider": (
                        baseline.origin.recording_provider
                        if baseline.origin.recording_provider == "manual"
                        else linked.origin.recording_provider
                    )
                }
            ),
            "audit": baseline.audit.model_copy(
                update={
                    "external_created_at_utc": (
                        linked.audit.external_created_at_utc
                    ),
                    "external_sync_at_utc": linked.audit.external_sync_at_utc,
                    "external_fingerprint_sha256": (
                        linked.audit.external_fingerprint_sha256
                    ),
                }
            ),
            "calculated_load": baseline.calculated_load,
        }
    )
    return CanonicalActivity.model_validate(
        repaired.model_dump(mode="json", by_alias=True)
    )


class ActivityV2Migrator:
    BACKUP_ROOT_NAMES = ("activities", "metrics", "athlete", "plans", "state")

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.data_root = self.repo_root / "data"
        self.source_root = self.data_root / "activities"

    def _source_files(self) -> list[Path]:
        return sorted(self.source_root.rglob("*.yaml"))

    def _load_sources(self) -> list[tuple[Path, dict[str, Any]]]:
        result: list[tuple[Path, dict[str, Any]]] = []
        for path in self._source_files():
            try:
                raw = yaml.safe_load(path.read_text())
            except Exception as exc:
                relative = path.relative_to(self.repo_root)
                raise MigrationError(f"Invalid source YAML: {relative}") from exc
            if not isinstance(raw, dict):
                raise MigrationError(
                    f"Invalid source record: {path.relative_to(self.repo_root)}"
                )
            # The pure transformer is the authoritative validation.
            transform_activity(raw)
            result.append((path, raw))
        if not result:
            raise MigrationError("No activity source files found")
        return result

    def _paths(self, run_id: str) -> dict[str, Path]:
        run_root = self.data_root / "migrations" / "activity-v2" / run_id
        return {
            "run": run_root,
            "candidate": run_root / "candidate",
            "rollback": run_root / "rollback-activities-v1",
            "state": run_root / "run.json",
            "report": run_root / "report.json",
            "report_md": run_root / "report.md",
            "backup": self.data_root / "backups" / "activity-v2" / run_id,
            "lock": self.data_root / ".activity-v2-migration.lock",
        }

    def _ensure_exclusive(self, lock_path: Path) -> None:
        competing = [
            self.repo_root / "config/.workflow_lock",
            self.repo_root / "config/.sync_lock",
            self.repo_root / "config/.sync_progress.json",
            self.repo_root / "data/state/.activity-sync.lock",
        ]
        active = [str(path.relative_to(self.repo_root)) for path in competing if path.exists()]
        if active:
            raise MigrationError(f"Migration cannot start while workflow state exists: {active}")
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise MigrationError("Another activity-v2 migration holds the lock") from exc
        os.close(fd)

    def _write_envelope(self, path: Path, envelope: MigrationRunEnvelope) -> None:
        _atomic_json(path, envelope.model_dump(mode="json"))

    def _backup(self, backup_root: Path) -> dict[str, str]:
        if backup_root.exists():
            manifest_path = backup_root / "manifest.json"
            if not manifest_path.exists():
                raise MigrationError("Existing backup is missing its manifest")
            return json.loads(manifest_path.read_text())["files"]

        backup_root.mkdir(parents=True, mode=0o700)
        included = [self.data_root / name for name in self.BACKUP_ROOT_NAMES]
        for source in included:
            if source.is_dir():
                shutil.copytree(source, backup_root / source.name, copy_function=shutil.copy2)
            elif source.is_file():
                shutil.copy2(source, backup_root / source.name)

        files = _manifest(
            [path for path in backup_root.rglob("*") if path.is_file()],
            backup_root,
        )
        _atomic_json(
            backup_root / "manifest.json",
            {"schema_version": 1, "files": files},
        )
        verified = _manifest(
            [
                path
                for path in backup_root.rglob("*")
                if path.is_file() and path.name != "manifest.json"
            ],
            backup_root,
        )
        if files != verified:
            raise MigrationError("Backup hash verification failed")
        return files

    def dry_run(self) -> MigrationReconciliation:
        source_pairs = self._load_sources()
        source_manifest = _manifest((path for path, _ in source_pairs), self.repo_root)
        input_digest = _manifest_digest(source_manifest)
        run_id = f"migration-{input_digest[:12]}"
        paths = self._paths(run_id)
        self._ensure_exclusive(paths["lock"])
        try:
            envelope = MigrationRunEnvelope(
                run_id=run_id,
                input_manifest_sha256=input_digest,
                created_at_utc=datetime.now(timezone.utc),
                source_validated=True,
            )
            paths["run"].mkdir(parents=True, exist_ok=True)
            self._write_envelope(paths["state"], envelope)

            self._backup(paths["backup"])
            envelope.backup_verified = True
            self._write_envelope(paths["state"], envelope)

            candidate = paths["candidate"]
            if candidate.exists():
                shutil.rmtree(candidate)
            transformed: list[CanonicalActivity] = []
            ledger: dict[str, str] = {}
            for _source_path, raw in source_pairs:
                activity = transform_activity(raw)
                destination = (
                    candidate
                    / activity.date.strftime("%Y-%m")
                    / f"{activity.local_activity_id}.yaml"
                )
                if destination.exists():
                    raise MigrationError(
                        f"Duplicate deterministic local ID: {activity.local_activity_id}"
                    )
                _atomic_yaml(destination, activity)
                transformed.append(activity)
                legacy_hash = hashlib.sha256(str(raw["id"]).encode()).hexdigest()
                ledger[activity.local_activity_id] = legacy_hash

            envelope.candidate_built = True
            self._write_envelope(paths["state"], envelope)

            candidate_files = sorted(candidate.rglob("*.yaml"))
            validated = [
                CanonicalActivity.model_validate(yaml.safe_load(path.read_text()))
                for path in candidate_files
            ]
            source_totals = _source_totals([raw for _, raw in source_pairs])
            candidate_totals = _candidate_totals(validated)
            rounded_segment_count = sum(
                1
                for _, raw in source_pairs
                for segment in (raw.get("laps") or [])
                if int(segment.get("moving_time_seconds") or 0)
                > int(segment.get("elapsed_time_seconds") or 0)
            )
            mismatches: list[str] = []
            if source_totals != candidate_totals:
                source_data = source_totals.model_dump(mode="json")
                candidate_data = candidate_totals.model_dump(mode="json")
                for key in sorted(source_data):
                    if source_data[key] != candidate_data[key]:
                        mismatches.append(
                            f"{key}: source={source_data[key]!r} candidate={candidate_data[key]!r}"
                        )

            report = MigrationReconciliation(
                input_manifest_sha256=input_digest,
                source=source_totals,
                candidate=candidate_totals,
                source_file_sha256=source_manifest,
                candidate_file_sha256=_manifest(candidate_files, candidate),
                local_id_ledger_sha256=dict(sorted(ledger.items())),
                all_records_valid=len(validated) == len(source_pairs),
                totals_match=not mismatches,
                normalizations=(
                    [
                        f"{rounded_segment_count} historical segment moving durations "
                        "were clamped to elapsed duration (maximum observed delta: 1 second)"
                    ]
                    if rounded_segment_count
                    else []
                ),
                mismatches=mismatches,
            )
            _atomic_json(paths["report"], report.model_dump(mode="json"))
            paths["report_md"].write_text(
                "# Activity v2 migration reconciliation\n\n"
                f"- Input manifest: `{input_digest}`\n"
                f"- Records: {report.source.record_count}\n"
                f"- Valid candidates: {report.candidate.record_count}\n"
                f"- Totals match: {str(report.totals_match).lower()}\n"
                f"- Mismatches: {len(report.mismatches)}\n"
            )
            envelope.reconciliation_passed = report.all_records_valid and report.totals_match
            self._write_envelope(paths["state"], envelope)
            if not envelope.reconciliation_passed:
                raise MigrationError(
                    "Candidate reconciliation failed: " + "; ".join(mismatches)
                )
            return report
        finally:
            paths["lock"].unlink(missing_ok=True)

    def apply(self, input_manifest_sha256: str) -> Path:
        paths = self._paths(f"migration-{input_manifest_sha256[:12]}")
        self._ensure_exclusive(paths["lock"])
        try:
            envelope = MigrationRunEnvelope.model_validate_json(paths["state"].read_text())
            if envelope.input_manifest_sha256 != input_manifest_sha256:
                raise MigrationError("Apply input manifest does not match dry-run")
            if not envelope.reconciliation_passed:
                raise MigrationError("Apply requires a successful reconciliation")
            if paths["rollback"].exists():
                raise MigrationError("Rollback directory already exists")
            os.replace(self.source_root, paths["rollback"])
            try:
                os.replace(paths["candidate"], self.source_root)
            except Exception:
                os.replace(paths["rollback"], self.source_root)
                raise
            envelope.applied = True
            self._write_envelope(paths["state"], envelope)
            return self.source_root
        finally:
            paths["lock"].unlink(missing_ok=True)

    def repair_linked_history(
        self,
        input_manifest_sha256: str,
    ) -> dict[str, Any]:
        """Restore migrated facts changed by the retired reconciliation merge."""
        paths = self._paths(f"migration-{input_manifest_sha256[:12]}")
        self._ensure_exclusive(paths["lock"])
        try:
            envelope = MigrationRunEnvelope.model_validate_json(
                paths["state"].read_text()
            )
            if (
                envelope.input_manifest_sha256 != input_manifest_sha256
                or not envelope.applied
                or not paths["rollback"].is_dir()
            ):
                raise MigrationError(
                    "Historical repair requires the applied migration and "
                    "its retained v1 rollback archive"
                )

            baselines: dict[str, CanonicalActivity] = {}
            for source in sorted(paths["rollback"].rglob("*.yaml")):
                raw = yaml.safe_load(source.read_text())
                baseline = transform_activity(raw)
                if baseline.local_activity_id in baselines:
                    raise MigrationError(
                        "Historical repair found a duplicate deterministic ID"
                    )
                baselines[baseline.local_activity_id] = baseline

            current = [
                CanonicalActivity.model_validate(yaml.safe_load(path.read_text()))
                for path in sorted(self.source_root.rglob("*.yaml"))
            ]
            current_by_id = {row.local_activity_id: row for row in current}
            missing = sorted(set(baselines) - set(current_by_id))
            if missing:
                raise MigrationError(
                    f"Historical repair is missing {len(missing)} migrated records"
                )

            repaired: list[CanonicalActivity] = []
            repaired_linked = 0
            for row in current:
                baseline = baselines.get(row.local_activity_id)
                if baseline is None:
                    repaired.append(row)
                    continue
                restored = _restore_historical_facts(baseline, row)
                repaired.append(restored)
                if restored.origin.intervals_icu_activity_id:
                    repaired_linked += 1

            expected = _candidate_totals(list(baselines.values()))
            historical = [
                row for row in repaired if row.origin.kind == "historical_import"
            ]
            actual = _candidate_totals(historical)
            if actual != expected:
                raise MigrationError(
                    "Historical repair does not reconcile to migration totals"
                )

            repair_root = paths["run"] / "linked-history-repair"
            candidate = repair_root / "candidate"
            previous = repair_root / "pre-repair-v2"
            report_path = repair_root / "report.json"
            if previous.exists():
                if not report_path.exists():
                    raise MigrationError(
                        "Historical repair has an incomplete prior transaction"
                    )
                return json.loads(report_path.read_text())
            if candidate.exists():
                shutil.rmtree(candidate)
            for row in repaired:
                _atomic_yaml(
                    candidate
                    / row.date.strftime("%Y-%m")
                    / f"{row.local_activity_id}.yaml",
                    row,
                )

            staged = [
                CanonicalActivity.model_validate(yaml.safe_load(path.read_text()))
                for path in sorted(candidate.rglob("*.yaml"))
            ]
            if len(staged) != len(current):
                raise MigrationError("Historical repair candidate count changed")

            before_historical = _candidate_totals(
                [row for row in current if row.origin.kind == "historical_import"]
            )
            report = {
                "schema_version": 1,
                "input_manifest_sha256": input_manifest_sha256,
                "repaired_linked_records": repaired_linked,
                "external_records_preserved": len(repaired) - len(historical),
                "before_historical": before_historical.model_dump(mode="json"),
                "after_historical": actual.model_dump(mode="json"),
                "migration_totals_restored": actual == expected,
            }

            os.replace(self.source_root, previous)
            try:
                os.replace(candidate, self.source_root)
                # A final load enforces stable paths, IDs, and external refs.
                from resilio.core.activity_sync.archive import ActivityArchive

                ActivityArchive(self.source_root).load_all()
            except Exception:
                if self.source_root.exists():
                    os.replace(self.source_root, candidate)
                os.replace(previous, self.source_root)
                raise
            _atomic_json(report_path, report)
            return report
        finally:
            paths["lock"].unlink(missing_ok=True)

    def rollback(self, input_manifest_sha256: str) -> Path:
        paths = self._paths(f"migration-{input_manifest_sha256[:12]}")
        self._ensure_exclusive(paths["lock"])
        try:
            envelope = MigrationRunEnvelope.model_validate_json(paths["state"].read_text())
            if not envelope.applied or not paths["rollback"].is_dir():
                raise MigrationError("No applied migration rollback is available")
            displaced_root = paths["run"] / "rolled-back-v2"
            restore_root = paths["run"] / "rollback-restore"
            if displaced_root.exists() or restore_root.exists():
                raise MigrationError("A prior rolled-back v2 archive already exists")

            restore_root.mkdir()
            for name in self.BACKUP_ROOT_NAMES:
                source = paths["backup"] / name
                destination = restore_root / name
                if source.is_dir():
                    shutil.copytree(source, destination, copy_function=shutil.copy2)
                elif source.is_file():
                    shutil.copy2(source, destination)

            # The original activity archive was already moved during apply.
            # Place it in the restore staging tree so every root follows the
            # same transactional swap and reverse-on-failure path.
            staged_activities = restore_root / "activities"
            if staged_activities.exists():
                shutil.rmtree(staged_activities)
            os.replace(paths["rollback"], staged_activities)

            displaced_root.mkdir()
            swapped: list[str] = []
            try:
                for name in self.BACKUP_ROOT_NAMES:
                    active = self.data_root / name
                    displaced = displaced_root / name
                    restored = restore_root / name
                    if active.exists():
                        os.replace(active, displaced)
                    # Record the root after the active move so a failure in
                    # the restore move still reverses the displaced state.
                    swapped.append(name)
                    if restored.exists():
                        os.replace(restored, active)

                expected = json.loads(
                    (paths["backup"] / "manifest.json").read_text()
                )["files"]
                restored_files = [
                    path
                    for name in self.BACKUP_ROOT_NAMES
                    for path in (self.data_root / name).rglob("*")
                    if path.is_file()
                ]
                actual = _manifest(restored_files, self.data_root)
                if actual != expected:
                    raise MigrationError(
                        "Rollback backup-manifest verification failed"
                    )
            except Exception:
                for name in reversed(swapped):
                    active = self.data_root / name
                    displaced = displaced_root / name
                    restored = restore_root / name
                    if active.exists():
                        restored.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(active, restored)
                    if displaced.exists():
                        os.replace(displaced, active)
                if staged_activities.exists():
                    os.replace(staged_activities, paths["rollback"])
                raise

            restore_root.rmdir()
            envelope.applied = False
            envelope.rollback_verified = True
            self._write_envelope(paths["state"], envelope)
            return self.source_root
        finally:
            paths["lock"].unlink(missing_ok=True)
