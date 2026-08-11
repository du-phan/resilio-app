"""One-shot workout completion/publication cutover to native-pairing fulfillment v2."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import TypeVar
from uuid import uuid4
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH, remove_path
from resilio.core.locking import OperationLock
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import read_sync_progress
from resilio.core.workout_fulfillment.current_fulfillment_migration import (
    migrate_current_fulfillment_manifest as _migrate_current_fulfillment_manifest,
)
from resilio.core.workout_fulfillment.cutover_guard import MIGRATION_TRANSACTION_PATH
from resilio.core.workout_fulfillment.legacy_contracts import (
    LegacyWorkoutCompletionManifest,
)
from resilio.core.workout_fulfillment.migration_authority import (
    MigrationWorkoutAuthority as _MigrationWorkoutAuthority,
)
from resilio.core.workout_fulfillment.migration_authority import (
    load_migration_authorities_unlocked as _load_authorities_unlocked,
)
from resilio.core.workout_fulfillment.migration_authority import (
    validate_migrated_fulfillment_authority,
)
from resilio.core.workout_fulfillment.migration_preflight import (
    athlete_local_migration_date as _athlete_local_migration_date,
)
from resilio.core.workout_fulfillment.migration_preflight import (
    recover_activity_sync_before_migration as _recover_activity_sync_before_migration,
)
from resilio.core.workout_fulfillment.migration_report import (
    WorkoutFulfillmentMigrationReport,
)
from resilio.core.workout_fulfillment.migration_transaction import (
    commit_workout_fulfillment_migration,
    recover_workout_fulfillment_migration,
    validate_migration_target_paths,
)
from resilio.core.workout_fulfillment.migration_validation import (
    WorkoutFulfillmentMigrationError as WorkoutFulfillmentMigrationError,
)
from resilio.core.workout_fulfillment.migration_validation import (
    parse_aware_legacy_datetime as _parse_aware_legacy_datetime,
)
from resilio.core.workout_fulfillment.planning_evidence_migration import (
    PlanningEvidenceMigrationError,
    prepare_planning_evidence_migration,
)
from resilio.core.workout_fulfillment.planning_evidence_migration_models import (
    PlanningEvidenceMigrationResult,
)
from resilio.core.workout_fulfillment.publication_migration import (
    migrate_publication_manifest as _migrate_publication_manifest,
)
from resilio.core.workout_fulfillment.repository import (
    LEGACY_WORKOUT_COMPLETIONS_PATH,
    WORKOUT_FULFILLMENTS_PATH,
    save_fulfillment_manifest,
)
from resilio.core.workout_publication.locking import coordinated_publication_plan_lock
from resilio.core.workout_publication.manifest import (
    PUBLICATION_MANIFEST_PATH,
    save_manifest,
)
from resilio.schemas.activity import ActivityStatus, CanonicalActivity, is_running_sport
from resilio.schemas.publication import (
    HistoricalLegacyWorkoutPublication,
    PublicationManifest,
    PublishedWorkout,
)
from resilio.schemas.workout_fulfillment import (
    HistoricalLegacyWorkoutFulfillment,
    ProviderPairedFulfillmentEvidence,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)

LEGACY_COMPLETIONS_PATH = LEGACY_WORKOUT_COMPLETIONS_PATH
MIGRATION_TARGET_PATHS = (
    PUBLICATION_MANIFEST_PATH,
    LEGACY_COMPLETIONS_PATH,
    WORKOUT_FULFILLMENTS_PATH,
)


def _read_json_object(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    if path.is_symlink():
        raise WorkoutFulfillmentMigrationError(f"Migration source cannot be a symlink: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise WorkoutFulfillmentMigrationError(
            f"Migration source is not valid JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise WorkoutFulfillmentMigrationError(f"Migration source must be a JSON object: {path}")
    return payload


def _execution_local_date(
    activity: CanonicalActivity,
    schedule_timezone: str,
) -> date:
    if activity.occurrence.start_time_utc is not None:
        return activity.occurrence.start_time_utc.astimezone(ZoneInfo(schedule_timezone)).date()
    if activity.occurrence.timezone == schedule_timezone:
        return activity.occurrence.local_date
    raise WorkoutFulfillmentMigrationError(
        "Legacy paired activity has no unambiguous execution date"
    )


PublicationRecord = TypeVar(
    "PublicationRecord",
    PublishedWorkout,
    HistoricalLegacyWorkoutPublication,
)


def _publications_by_identity(
    publications: Iterable[PublicationRecord],
) -> dict[tuple[str, str, int, str], PublicationRecord]:
    return {
        (
            publication.workout_identity.plan_id,
            publication.workout_identity.plan_revision_id,
            publication.workout_identity.week_number,
            publication.workout_identity.local_workout_id,
        ): publication
        for publication in publications
    }


def _migrate_fulfillment_manifest(
    repo: RepositoryIO,
    raw: dict[str, object] | None,
    publication_manifest: PublicationManifest,
    authorities: list[_MigrationWorkoutAuthority],
) -> WorkoutFulfillmentManifest:
    if raw is None:
        return WorkoutFulfillmentManifest()
    try:
        legacy_manifest = LegacyWorkoutCompletionManifest.model_validate(raw)
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Legacy completion manifest violates its version 3 contract"
        ) from exc
    publications_by_identity = _publications_by_identity(
        publication_manifest.workouts.values()
    )
    historical_publications_by_identity = _publications_by_identity(
        publication_manifest.historical_legacy_workouts.values()
    )
    archive = ActivityArchive(repo.resolve_path("data/activities"))
    fulfillments: dict[str, WorkoutFulfillmentRecord] = {}
    historical_fulfillments: dict[str, HistoricalLegacyWorkoutFulfillment] = {}
    for local_activity_id, legacy_match in legacy_manifest.matches.items():
        identity = legacy_match.workout_identity
        identity_key = (
            identity.plan_id,
            identity.plan_revision_id,
            identity.week_number,
            identity.local_workout_id,
        )
        publication = publications_by_identity.get(identity_key)
        historical_publication = historical_publications_by_identity.get(identity_key)
        activity = archive.load(local_activity_id)
        if (publication is None and historical_publication is None) or activity is None:
            raise WorkoutFulfillmentMigrationError(
                "Legacy completion lacks its publication or canonical activity"
            )
        if not is_running_sport(activity.sport):
            raise WorkoutFulfillmentMigrationError(
                "Legacy completion activity is not a running activity"
            )
        if publication is not None and activity.status != ActivityStatus.ACTIVE:
            raise WorkoutFulfillmentMigrationError(
                "Active legacy completion references a non-active canonical activity"
            )
        observed_at_utc = _parse_aware_legacy_datetime(
            legacy_match.matched_at_utc,
            field_name="matched_at_utc",
        )
        owned_publication = publication or historical_publication
        assert owned_publication is not None
        provider_pair = ProviderPairedFulfillmentEvidence(
            provenance="provider_observed",
            event_id=owned_publication.event_id,
            observed_at_utc=observed_at_utc,
        )
        if publication is None:
            assert historical_publication is not None
            execution_local_date = activity.occurrence.local_date
            if execution_local_date != historical_publication.occurrence_date:
                raise WorkoutFulfillmentMigrationError(
                    "Historical completion timing differs across unavailable schedule authority"
                )
            historical_fulfillments[str(local_activity_id)] = HistoricalLegacyWorkoutFulfillment(
                local_activity_id=str(local_activity_id),
                workout_identity=historical_publication.workout_identity,
                activity_performance_evidence_sha256=(
                    activity_performance_evidence_sha256(activity)
                ),
                scheduled_local_date=historical_publication.occurrence_date,
                execution_local_date=execution_local_date,
                schedule_offset_days=0,
                provider_pair=provider_pair,
                matched_at_utc=observed_at_utc,
            )
            continue
        execution_local_date = _execution_local_date(
            activity,
            publication.schedule_timezone,
        )
        migrated_fulfillment = WorkoutFulfillmentRecord(
            local_activity_id=str(local_activity_id),
            workout_identity=publication.workout_identity,
            applied_week_approval_id=publication.applied_week_approval_id,
            applied_running_workouts_sha256=(publication.applied_running_workouts_sha256),
            workout_prescription_sha256=publication.workout_prescription_sha256,
            activity_performance_evidence_sha256=(activity_performance_evidence_sha256(activity)),
            schedule_timezone=publication.schedule_timezone,
            scheduled_local_date=publication.occurrence_date,
            execution_local_date=execution_local_date,
            schedule_offset_days=(execution_local_date - publication.occurrence_date).days,
            provider_pair=provider_pair,
            recorded_at_utc=observed_at_utc,
        )
        try:
            validate_migrated_fulfillment_authority(
                migrated_fulfillment,
                authorities,
            )
        except ValueError as exc:
            raise WorkoutFulfillmentMigrationError(
                "Legacy completion conflicts with schedule-time workout authority"
            ) from exc
        fulfillments[str(local_activity_id)] = migrated_fulfillment
    return WorkoutFulfillmentManifest(
        fulfillments=fulfillments,
        historical_legacy_fulfillments=historical_fulfillments,
    )


def _finish_migration(
    repo: RepositoryIO,
    *,
    run_id: str,
    apply: bool,
    publication_manifest: PublicationManifest,
    fulfillment_manifest: WorkoutFulfillmentManifest,
    planning_migration: PlanningEvidenceMigrationResult,
    manifests_changed: bool,
) -> WorkoutFulfillmentMigrationReport:
    changes_required = manifests_changed or planning_migration.changes_required
    target_relative_paths = (
        *MIGRATION_TARGET_PATHS,
        *planning_migration.target_relative_paths,
    )
    if changes_required:
        validate_migration_target_paths(target_relative_paths)
    backup_relative_path = None
    if apply and changes_required:
        backup_relative_path = f"data/backups/{run_id}"

        def apply_state() -> None:
            save_fulfillment_manifest(repo, fulfillment_manifest)
            save_manifest(repo, publication_manifest)
            remove_path(repo.resolve_path(LEGACY_COMPLETIONS_PATH))
            planning_migration.apply(repo)

        commit_workout_fulfillment_migration(
            repo,
            run_id=run_id,
            backup_relative_path=backup_relative_path,
            target_relative_paths=target_relative_paths,
            apply_state=apply_state,
        )
    return WorkoutFulfillmentMigrationReport(
        run_id=run_id,
        active_publication_count=len(publication_manifest.workouts),
        pending_publication_count=len(publication_manifest.pending),
        historical_publication_count=len(publication_manifest.historical_legacy_workouts),
        active_fulfillment_count=len(fulfillment_manifest.fulfillments),
        historical_fulfillment_count=len(
            fulfillment_manifest.historical_legacy_fulfillments
        ),
        migrated_planning_artifact_count=planning_migration.migrated_artifact_count,
        migrated_plan_count=planning_migration.migrated_plan_count,
        changes_required=changes_required,
        applied=apply and changes_required,
        backup_relative_path=backup_relative_path,
    )


def migrate_workout_fulfillment_state(
    repo: RepositoryIO,
    *,
    apply: bool,
) -> WorkoutFulfillmentMigrationReport:
    """Validate the complete cutover; mutate only after an explicit apply flag."""
    run_id = f"workout-fulfillment-v2-{uuid4().hex[:12]}"
    publication_path = repo.resolve_path(PUBLICATION_MANIFEST_PATH)
    legacy_completion_path = repo.resolve_path(LEGACY_COMPLETIONS_PATH)
    fulfillment_path = repo.resolve_path(WORKOUT_FULFILLMENTS_PATH)
    with coordinated_publication_plan_lock(repo, "migrate_workout_fulfillment_v2"):
        with OperationLock(
            repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH),
            "migrate_workout_fulfillment_v2",
        ):
            recovery_required = repo.file_exists(MIGRATION_TRANSACTION_PATH) or (
                read_sync_progress(repo) is not None
            )
            if recovery_required and not apply:
                raise WorkoutFulfillmentMigrationError(
                    "Migration recovery is required; dry-run mode never mutates state, "
                    "so rerun with --apply to recover before cutover"
                )
            if apply:
                recover_workout_fulfillment_migration(
                    repo,
                )
                _recover_activity_sync_before_migration(repo)
            publication_raw = _read_json_object(publication_path)
            completion_raw = _read_json_object(legacy_completion_path)
            current_fulfillment_raw = _read_json_object(fulfillment_path)
            if current_fulfillment_raw is not None and completion_raw is not None:
                raise WorkoutFulfillmentMigrationError(
                    "Current fulfillment and legacy completion state cannot coexist"
                )
            active_fulfillment_raw = (
                current_fulfillment_raw.get("fulfillments", {})
                if current_fulfillment_raw is not None
                else {}
            )
            revoked_fulfillment_raw = (
                current_fulfillment_raw.get("revoked_fulfillments", [])
                if current_fulfillment_raw is not None
                else []
            )
            activities_by_local_id = {
                activity.local_activity_id: activity
                for activity in ActivityArchive(
                    repo.resolve_path("data/activities")
                ).load_all()
            }
            authorities = (
                _load_authorities_unlocked(repo)
                if (
                    publication_raw is not None
                    and publication_raw.get("schema_version") in {6, 7}
                )
                or bool(active_fulfillment_raw)
                or bool(revoked_fulfillment_raw)
                else []
            )
            publication_manifest, publication_changed = _migrate_publication_manifest(
                publication_raw,
                authorities,
                migration_date=_athlete_local_migration_date(repo),
            )
            if current_fulfillment_raw is not None:
                fulfillment_manifest, fulfillment_changed = (
                    _migrate_current_fulfillment_manifest(
                        current_fulfillment_raw,
                        publication_manifest,
                        authorities,
                        activities_by_local_id,
                    )
                )
            else:
                fulfillment_manifest = _migrate_fulfillment_manifest(
                    repo,
                    completion_raw,
                    publication_manifest,
                    authorities,
                )
                fulfillment_changed = completion_raw is not None
            try:
                planning_migration = prepare_planning_evidence_migration(
                    repo,
                    fulfillment_manifest=fulfillment_manifest,
                    publication_manifest=publication_manifest,
                    legacy_completion_raw=completion_raw,
                    legacy_publication_raw=publication_raw,
                    pre_migration_fulfillment_raw=current_fulfillment_raw,
                )
            except (PlanningEvidenceMigrationError, RuntimeError) as exc:
                raise WorkoutFulfillmentMigrationError(
                    f"Planning evidence migration failed: {exc}"
                ) from exc
            return _finish_migration(
                repo,
                run_id=run_id,
                apply=apply,
                publication_manifest=publication_manifest,
                fulfillment_manifest=fulfillment_manifest,
                planning_migration=planning_migration,
                manifests_changed=publication_changed or fulfillment_changed,
            )
