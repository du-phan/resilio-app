"""One-shot workout completion/publication cutover to fulfillment v1."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH, remove_path
from resilio.core.locking import OperationLock
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import read_sync_progress
from resilio.core.workout_fulfillment.legacy_contracts import (
    LegacyPublicationManifest,
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
    MIGRATION_TRANSACTION_PATH,
    commit_workout_fulfillment_migration,
    recover_workout_fulfillment_migration,
)
from resilio.core.workout_fulfillment.planning_evidence_migration import (
    PlanningEvidenceMigrationError,
    prepare_planning_evidence_migration,
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
from resilio.core.workout_publication.preparation import rendered_workout_sha256
from resilio.schemas.activity import ActivityStatus, CanonicalActivity, is_running_sport
from resilio.schemas.publication import (
    HistoricalLegacyWorkoutPublication,
    PendingWorkoutPublication,
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


class WorkoutFulfillmentMigrationError(RuntimeError):
    """Legacy state cannot be transformed without losing exact authority."""


def _parse_aware_legacy_datetime(value: object, *, field_name: str) -> datetime:
    """Parse legacy audit time without consulting the host machine timezone."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            f"Legacy {field_name} is not a valid timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkoutFulfillmentMigrationError(f"Legacy {field_name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


MigrationAuthorityIndex = dict[
    tuple[str, str, int, str],
    list[_MigrationWorkoutAuthority],
]


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


def _identity_key(payload: dict[str, object]) -> tuple[str, str, int, str]:
    try:
        week_number = payload["week_number"]
        if not isinstance(week_number, int) or isinstance(week_number, bool):
            raise TypeError("week_number must be an integer")
        return (
            str(payload["plan_id"]),
            str(payload["plan_revision_id"]),
            week_number,
            str(payload["local_workout_id"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkoutFulfillmentMigrationError(
            "Legacy publication has an invalid workout identity"
        ) from exc


def _index_migration_authorities(
    authorities: list[_MigrationWorkoutAuthority],
) -> MigrationAuthorityIndex:
    indexed: MigrationAuthorityIndex = {}
    for item in authorities:
        identity = item.workout.identity
        indexed.setdefault(
            (
                identity.plan_id,
                identity.plan_revision_id,
                identity.week_number,
                identity.local_workout_id,
            ),
            [],
        ).append(item)
    return indexed


def _authority_for_legacy_publication(
    payload: object,
    *,
    pending: bool,
    authorities_by_identity: MigrationAuthorityIndex,
    migration_date: date,
) -> AuthoritativeWorkout | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("workout_identity"), dict):
        raise WorkoutFulfillmentMigrationError("Legacy publication record lacks a workout identity")
    observed_field = "prepared_at_utc" if pending else "verified_at_utc"
    try:
        observed_at_utc = _parse_aware_legacy_datetime(
            payload[observed_field],
            field_name=observed_field,
        )
    except (KeyError, WorkoutFulfillmentMigrationError) as exc:
        raise WorkoutFulfillmentMigrationError(
            "Legacy publication lacks a valid authority observation time"
        ) from exc
    identity_candidates = authorities_by_identity.get(
        _identity_key(payload["workout_identity"]),
        [],
    )
    candidates = [
        item
        for item in identity_candidates
        if item.valid_from_utc <= observed_at_utc
        and (item.valid_until_utc is None or observed_at_utc < item.valid_until_utc)
        and payload.get("occurrence_date") == item.workout.prescription.date.isoformat()
        and payload.get("rendered_workout_sha256")
        == rendered_workout_sha256(item.workout.prescription)
    ]
    if len(candidates) == 1:
        return candidates[0].workout
    if candidates or identity_candidates:
        raise WorkoutFulfillmentMigrationError(
            "Legacy publication does not identify exactly one applied-workout authority"
        )
    occurrence_date = date.fromisoformat(str(payload.get("occurrence_date")))
    if pending or occurrence_date >= migration_date:
        raise WorkoutFulfillmentMigrationError(
            "Current or pending legacy publication lacks exact applied-workout authority"
        )
    return None


def _enriched_publication_record(
    payload: object,
    authority: AuthoritativeWorkout,
    *,
    pending: bool,
) -> PublishedWorkout | PendingWorkoutPublication:
    assert isinstance(payload, dict)
    enriched = {
        **payload,
        "applied_week_approval_id": authority.applied_week_approval_id,
        "applied_running_workouts_sha256": authority.applied_running_workouts_sha256,
        "workout_prescription_sha256": canonical_data_sha256(authority.prescription),
        "schedule_timezone": authority.schedule_timezone,
    }
    model = PendingWorkoutPublication if pending else PublishedWorkout
    return model.model_validate(enriched)


def _migrate_publication_manifest(
    raw: dict[str, object] | None,
    authorities: list[_MigrationWorkoutAuthority],
    *,
    migration_date: date,
) -> tuple[PublicationManifest, bool]:
    if raw is None:
        return PublicationManifest(), False
    if raw.get("schema_version") == 7:
        return PublicationManifest.model_validate(raw), False
    if raw.get("schema_version") != 6:
        raise WorkoutFulfillmentMigrationError(
            "Publication migration requires schema version 6 or 7"
        )
    try:
        raw = LegacyPublicationManifest.model_validate(raw).model_dump(mode="json")
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Legacy publication manifest violates its version 6 contract"
        ) from exc
    authorities_by_identity = _index_migration_authorities(authorities)
    workouts_raw = raw.get("workouts", {})
    pending_raw = raw.get("pending", {})
    drift_raw = raw.get("drift_resolutions", [])
    if not isinstance(workouts_raw, dict) or not isinstance(pending_raw, dict):
        raise WorkoutFulfillmentMigrationError(
            "Legacy publication ownership collections must be objects"
        )
    if not isinstance(drift_raw, list):
        raise WorkoutFulfillmentMigrationError(
            "Legacy publication drift resolutions must be a list"
        )
    historical_legacy_drifts = [
        {**item, "strategy": "restore_local"}
        if isinstance(item, dict) and "strategy" not in item
        else item
        for item in drift_raw
    ]
    migrated_workouts: dict[str, PublishedWorkout] = {}
    historical_workouts: dict[str, HistoricalLegacyWorkoutPublication] = {}
    for local_id, payload in workouts_raw.items():
        authority = _authority_for_legacy_publication(
            payload,
            pending=False,
            authorities_by_identity=authorities_by_identity,
            migration_date=migration_date,
        )
        if authority is None:
            historical_workouts[str(local_id)] = HistoricalLegacyWorkoutPublication.model_validate(
                payload
            )
        else:
            record = _enriched_publication_record(payload, authority, pending=False)
            assert isinstance(record, PublishedWorkout)
            migrated_workouts[str(local_id)] = record
    migrated_pending: dict[str, PendingWorkoutPublication] = {}
    for local_id, payload in pending_raw.items():
        authority = _authority_for_legacy_publication(
            payload,
            pending=True,
            authorities_by_identity=authorities_by_identity,
            migration_date=migration_date,
        )
        assert authority is not None
        record = _enriched_publication_record(payload, authority, pending=True)
        assert isinstance(record, PendingWorkoutPublication)
        migrated_pending[str(local_id)] = record
    migrated = PublicationManifest.model_validate(
        {
            "workouts": migrated_workouts,
            "pending": migrated_pending,
            "historical_legacy_workouts": historical_workouts,
            "drift_resolutions": [],
            "historical_legacy_drift_resolutions": historical_legacy_drifts,
        }
    )
    return (
        migrated,
        True,
    )


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
    publications_by_identity = {
        (
            publication.workout_identity.plan_id,
            publication.workout_identity.plan_revision_id,
            publication.workout_identity.week_number,
            publication.workout_identity.local_workout_id,
        ): publication
        for publication in publication_manifest.workouts.values()
    }
    historical_publications_by_identity = {
        (
            publication.workout_identity.plan_id,
            publication.workout_identity.plan_revision_id,
            publication.workout_identity.week_number,
            publication.workout_identity.local_workout_id,
        ): publication
        for publication in publication_manifest.historical_legacy_workouts.values()
    }
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


def migrate_workout_fulfillment_state(
    repo: RepositoryIO,
    *,
    apply: bool,
) -> WorkoutFulfillmentMigrationReport:
    """Validate the complete cutover; mutate only after an explicit apply flag."""
    run_id = f"workout-fulfillment-v1-{uuid4().hex[:12]}"
    publication_path = repo.resolve_path(PUBLICATION_MANIFEST_PATH)
    legacy_completion_path = repo.resolve_path(LEGACY_COMPLETIONS_PATH)
    fulfillment_path = repo.resolve_path(WORKOUT_FULFILLMENTS_PATH)
    with coordinated_publication_plan_lock(repo, "migrate_workout_fulfillment_v1"):
        with OperationLock(
            repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH),
            "migrate_workout_fulfillment_v1",
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
            authorities = (
                _load_authorities_unlocked(repo)
                if publication_raw is not None and publication_raw.get("schema_version") == 6
                else []
            )
            publication_manifest, publication_changed = _migrate_publication_manifest(
                publication_raw,
                authorities,
                migration_date=_athlete_local_migration_date(repo),
            )
            fulfillment_manifest = (
                WorkoutFulfillmentManifest.model_validate(current_fulfillment_raw)
                if current_fulfillment_raw is not None
                else _migrate_fulfillment_manifest(
                    repo,
                    completion_raw,
                    publication_manifest,
                    authorities,
                )
            )
            try:
                planning_migration = prepare_planning_evidence_migration(
                    repo,
                    fulfillment_manifest=fulfillment_manifest,
                    publication_manifest=publication_manifest,
                    legacy_completion_raw=completion_raw,
                    legacy_publication_raw=publication_raw,
                )
            except (PlanningEvidenceMigrationError, RuntimeError) as exc:
                raise WorkoutFulfillmentMigrationError(
                    f"Planning evidence migration failed: {exc}"
                ) from exc
            changes_required = (
                publication_changed
                or completion_raw is not None
                or planning_migration.changes_required
            )
            backup_relative_path = None
            if apply and changes_required:
                backup_relative_path = f"data/backups/{run_id}"
                target_relative_paths = (
                    *MIGRATION_TARGET_PATHS,
                    *planning_migration.target_relative_paths,
                )

                def apply_state() -> None:
                    save_fulfillment_manifest(repo, fulfillment_manifest)
                    save_manifest(repo, publication_manifest)
                    remove_path(legacy_completion_path)
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
                migrated_planning_artifact_count=(planning_migration.migrated_artifact_count),
                migrated_plan_count=planning_migration.migrated_plan_count,
                changes_required=changes_required,
                applied=apply and changes_required,
                backup_relative_path=backup_relative_path,
            )
