"""Strict version-1 to version-2 workout-fulfillment state migration."""

from resilio.canonical import canonical_data_sha256
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.workout_fulfillment.legacy_fulfillment_contracts import (
    legacy_v1_fulfillment_sha256,
    migrate_legacy_v1_manifest,
)
from resilio.core.workout_fulfillment.migration_authority import (
    MigrationWorkoutAuthority,
    validate_migrated_fulfillment_authority,
)
from resilio.core.workout_fulfillment.migration_validation import (
    WorkoutFulfillmentMigrationError,
)
from resilio.core.workout_fulfillment.remote_unpairing import stage_remote_unpairing
from resilio.core.workout_fulfillment.revocation_publication_authority import (
    revoked_pair_publication_authority,
)
from resilio.schemas.activity import ActivityStatus, CanonicalActivity, is_running_sport
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublishedWorkout,
)
from resilio.schemas.workout_fulfillment import (
    HistoricalLegacyWorkoutFulfillment,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)

PublicationAuthority = PublishedWorkout | PendingWorkoutPublication


def _add_provider_pair_provenance(
    value: object,
    *,
    field_name: str | None = None,
) -> object:
    if isinstance(value, list):
        return [_add_provider_pair_provenance(item) for item in value]
    if not isinstance(value, dict):
        return value
    migrated = {
        key: _add_provider_pair_provenance(item, field_name=key) for key, item in value.items()
    }
    if (
        field_name == "provider_pair"
        and "event_id" in migrated
        and "observed_at_utc" in migrated
        and "provenance" not in migrated
    ):
        migrated["provenance"] = "provider_observed"
    return migrated


def load_fulfillment_manifest_for_publication_migration(
    raw: dict[str, object],
    *,
    activities_by_local_id: dict[str, CanonicalActivity],
) -> tuple[WorkoutFulfillmentManifest, bool, dict[str, str]]:
    schema_version = raw.get("schema_version")
    if schema_version == 2:
        return WorkoutFulfillmentManifest.model_validate(raw), False, {}
    if schema_version != 1:
        raise WorkoutFulfillmentMigrationError(
            "Workout fulfillment migration requires schema version 1 or 2"
        )
    try:
        validated_v1, source_hashes = migrate_legacy_v1_manifest(
            raw,
            activities_by_local_id=activities_by_local_id,
        )
        migrated = _add_provider_pair_provenance(validated_v1)
        assert isinstance(migrated, dict)
        migrated["schema_version"] = 2
        migrated["remote_pairing_operations"] = {}
        return WorkoutFulfillmentManifest.model_validate(migrated), True, source_hashes
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Workout fulfillment manifest violates its version 1 contract"
        ) from exc


def _stage_revoked_unpairs(
    manifest: WorkoutFulfillmentManifest,
    *,
    publication_manifest: PublicationManifest,
    authorities: list[MigrationWorkoutAuthority],
    activities_by_local_id: dict[str, CanonicalActivity],
    source_fulfillment_sha256_by_local_id: dict[str, str],
) -> bool:
    changed = False
    for revocation in manifest.revoked_fulfillments:
        fulfillment = revocation.fulfillment
        provider_pair = fulfillment.provider_pair
        if provider_pair is None:
            continue
        if any(
            operation.action == "unpair" and operation.revocation_id == revocation.revocation_id
            for operation in manifest.remote_pairing_operations.values()
        ):
            continue
        accepted_fulfillment_sha256_values = {
            canonical_data_sha256(fulfillment),
            legacy_v1_fulfillment_sha256(fulfillment),
        }
        captured_source_sha256 = source_fulfillment_sha256_by_local_id.get(
            fulfillment.local_activity_id
        )
        if captured_source_sha256 is not None:
            accepted_fulfillment_sha256_values.add(captured_source_sha256)
        try:
            publication = revoked_pair_publication_authority(
                publication_manifest,
                fulfillment,
                accepted_fulfillment_sha256_values=(accepted_fulfillment_sha256_values),
            )
        except ValueError as exc:
            raise WorkoutFulfillmentMigrationError(
                "Revoked provider pair conflicts with publication authority"
            ) from exc
        if publication is None:
            continue
        try:
            validate_migrated_fulfillment_authority(fulfillment, authorities)
        except ValueError as exc:
            raise WorkoutFulfillmentMigrationError(
                "Revoked provider pair conflicts with schedule-time authority"
            ) from exc
        activity = activities_by_local_id.get(fulfillment.local_activity_id)
        if (
            activity is None
            or activity_performance_evidence_sha256(activity)
            != fulfillment.activity_performance_evidence_sha256
        ):
            raise WorkoutFulfillmentMigrationError(
                "Revoked provider pair lacks unchanged canonical activity evidence"
            )
        try:
            stage_remote_unpairing(
                manifest=manifest,
                publication=publication,
                revocation=revocation,
                activity=activity,
            )
            changed = True
        except ValueError as exc:
            raise WorkoutFulfillmentMigrationError(
                "Revoked provider pair lacks exact native-unpair authority"
            ) from exc
    return changed


def _publication_candidates(
    manifest: PublicationManifest,
    fulfillment: WorkoutFulfillmentRecord,
    *,
    migrated_from_v1: bool,
    source_fulfillment_sha256_values: set[str],
) -> list[tuple[PublicationAuthority, int | None]]:
    local_workout_id = fulfillment.workout_identity.local_workout_id
    candidates: list[tuple[PublicationAuthority, int | None]] = []
    active_publication = manifest.workouts.get(local_workout_id)
    if active_publication is not None:
        candidates.append((active_publication, active_publication.event_id))
    pending_publication = manifest.pending.get(local_workout_id)
    if pending_publication is not None and (
        active_publication is None
        or (
            pending_publication.workout_identity,
            pending_publication.applied_week_approval_id,
            pending_publication.applied_running_workouts_sha256,
            pending_publication.workout_prescription_sha256,
            pending_publication.schedule_timezone,
            pending_publication.occurrence_date,
        )
        != (
            active_publication.workout_identity,
            active_publication.applied_week_approval_id,
            active_publication.applied_running_workouts_sha256,
            active_publication.workout_prescription_sha256,
            active_publication.schedule_timezone,
            active_publication.occurrence_date,
        )
    ):
        candidates.append(
            (
                pending_publication,
                (
                    active_publication.event_id
                    if active_publication is not None
                    else fulfillment.provider_pair.event_id
                    if fulfillment.provider_pair is not None
                    else None
                ),
            )
        )

    def retirement_matches(
        *,
        local_activity_id: str,
        workout_identity: object,
        fulfillment_record_sha256: str,
        execution_local_date: object,
        schedule_offset_days: int,
        reopened_at_utc: object,
    ) -> bool:
        return (
            local_activity_id == fulfillment.local_activity_id
            and workout_identity == fulfillment.workout_identity
            and reopened_at_utc is None
            and (
                not migrated_from_v1
                or (
                    fulfillment_record_sha256 in source_fulfillment_sha256_values
                    and execution_local_date == fulfillment.execution_local_date
                    and schedule_offset_days == fulfillment.schedule_offset_days
                )
            )
        )

    candidates.extend(
        (retirement.publication, retirement.publication.event_id)
        for retirement in manifest.historical_fulfillment_event_retirements
        if retirement_matches(
            local_activity_id=retirement.fulfilling_local_activity_id,
            workout_identity=retirement.publication.workout_identity,
            fulfillment_record_sha256=(retirement.fulfillment_record_sha256_at_retirement),
            execution_local_date=retirement.execution_local_date_at_retirement,
            schedule_offset_days=retirement.schedule_offset_days_at_retirement,
            reopened_at_utc=retirement.reopened_at_utc,
        )
    )
    candidates.extend(
        (retirement.pending_publication, retirement.remote_event_id)
        for retirement in manifest.historical_fulfillment_pending_retirements
        if retirement_matches(
            local_activity_id=retirement.fulfilling_local_activity_id,
            workout_identity=retirement.pending_publication.workout_identity,
            fulfillment_record_sha256=(retirement.fulfillment_record_sha256_at_retirement),
            execution_local_date=retirement.execution_local_date_at_retirement,
            schedule_offset_days=retirement.schedule_offset_days_at_retirement,
            reopened_at_utc=retirement.reopened_at_utc,
        )
    )
    return candidates


def _publication_authority_is_retained(
    publication: PublicationAuthority,
    fulfillment: WorkoutFulfillmentRecord,
    authorities: list[MigrationWorkoutAuthority],
) -> bool:
    if (
        publication.applied_week_approval_id == fulfillment.applied_week_approval_id
        and publication.applied_running_workouts_sha256
        == fulfillment.applied_running_workouts_sha256
    ):
        return True
    return any(
        item.workout.identity == publication.workout_identity
        and item.workout.applied_week_approval_id == publication.applied_week_approval_id
        and item.workout.applied_running_workouts_sha256
        == publication.applied_running_workouts_sha256
        and canonical_data_sha256(item.workout.prescription)
        == publication.workout_prescription_sha256
        and item.workout.schedule_timezone == publication.schedule_timezone
        and item.workout.prescription.date == publication.occurrence_date
        for item in authorities
    )


def _validate_active_fulfillment(
    publication_manifest: PublicationManifest,
    fulfillment: WorkoutFulfillmentRecord,
    *,
    authorities: list[MigrationWorkoutAuthority],
    migrated_from_v1: bool,
    captured_source_sha256: str | None,
    activity: CanonicalActivity | None,
    has_unresolved_conflict: bool,
) -> None:
    if not has_unresolved_conflict and (
        activity is None
        or activity.status != ActivityStatus.ACTIVE
        or not is_running_sport(activity.sport)
        or activity_performance_evidence_sha256(activity)
        != fulfillment.activity_performance_evidence_sha256
    ):
        raise WorkoutFulfillmentMigrationError(
            "Active fulfillment lacks exact current running-activity evidence"
        )
    source_hashes = {
        canonical_data_sha256(fulfillment),
        legacy_v1_fulfillment_sha256(fulfillment),
    }
    if captured_source_sha256 is not None:
        source_hashes.add(captured_source_sha256)
    candidates = _publication_candidates(
        publication_manifest,
        fulfillment,
        migrated_from_v1=migrated_from_v1,
        source_fulfillment_sha256_values=source_hashes,
    )
    matches = [
        (publication, event_id)
        for publication, event_id in candidates
        if publication.workout_identity == fulfillment.workout_identity
        and _publication_authority_is_retained(
            publication,
            fulfillment,
            authorities,
        )
        and publication.workout_prescription_sha256 == fulfillment.workout_prescription_sha256
        and publication.schedule_timezone == fulfillment.schedule_timezone
        and publication.occurrence_date == fulfillment.scheduled_local_date
        and (fulfillment.provider_pair is None or fulfillment.provider_pair.event_id == event_id)
    ]
    exact_applied_revision_matches = [
        (publication, event_id)
        for publication, event_id in matches
        if publication.applied_week_approval_id == fulfillment.applied_week_approval_id
        and publication.applied_running_workouts_sha256
        == fulfillment.applied_running_workouts_sha256
    ]
    if exact_applied_revision_matches:
        matches = exact_applied_revision_matches
    if not matches:
        raise WorkoutFulfillmentMigrationError(
            "Active fulfillment does not match its exact publication authority"
        )
    first, first_event_id = matches[0]
    if any(
        candidate.workout_identity != first.workout_identity
        or candidate.workout_prescription_sha256 != first.workout_prescription_sha256
        or candidate_event_id != first_event_id
        for candidate, candidate_event_id in matches[1:]
    ):
        raise WorkoutFulfillmentMigrationError(
            "Active fulfillment has competing publication authority"
        )
    try:
        validate_migrated_fulfillment_authority(fulfillment, authorities)
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Active fulfillment conflicts with schedule-time workout authority"
        ) from exc


def _validate_historical_fulfillment(
    publication_manifest: PublicationManifest,
    fulfillment: HistoricalLegacyWorkoutFulfillment,
    *,
    activity: CanonicalActivity | None,
    has_unresolved_conflict: bool,
) -> None:
    publication_matches = [
        publication
        for publication in publication_manifest.historical_legacy_workouts.values()
        if publication.workout_identity == fulfillment.workout_identity
        and publication.event_id == fulfillment.provider_pair.event_id
        and publication.occurrence_date == fulfillment.scheduled_local_date
    ]
    if len(publication_matches) != 1:
        raise WorkoutFulfillmentMigrationError(
            "Historical fulfillment lacks its exact legacy publication authority"
        )
    if not has_unresolved_conflict and (
        activity is None
        or activity.status != ActivityStatus.ACTIVE
        or not is_running_sport(activity.sport)
        or activity_performance_evidence_sha256(activity)
        != fulfillment.activity_performance_evidence_sha256
    ):
        raise WorkoutFulfillmentMigrationError(
            "Historical fulfillment lacks exact current running-activity evidence"
        )


def migrate_current_fulfillment_manifest(
    raw: dict[str, object] | None,
    publication_manifest: PublicationManifest,
    authorities: list[MigrationWorkoutAuthority],
    activities_by_local_id: dict[str, CanonicalActivity],
) -> tuple[WorkoutFulfillmentManifest, bool]:
    """Migrate and cross-validate the predecessor fulfillment manifest."""
    if raw is None:
        return WorkoutFulfillmentManifest(), False
    manifest, migrated_from_v1, source_hashes = load_fulfillment_manifest_for_publication_migration(
        raw,
        activities_by_local_id=activities_by_local_id,
    )
    repaired_revoked_unpairs = _stage_revoked_unpairs(
        manifest,
        publication_manifest=publication_manifest,
        authorities=authorities,
        activities_by_local_id=activities_by_local_id,
        source_fulfillment_sha256_by_local_id=source_hashes,
    )
    if migrated_from_v1 or repaired_revoked_unpairs:
        manifest = WorkoutFulfillmentManifest.model_validate(manifest.model_dump(mode="python"))
    for fulfillment in manifest.fulfillments.values():
        _validate_active_fulfillment(
            publication_manifest,
            fulfillment,
            authorities=authorities,
            migrated_from_v1=migrated_from_v1,
            captured_source_sha256=source_hashes.get(fulfillment.local_activity_id),
            activity=activities_by_local_id.get(fulfillment.local_activity_id),
            has_unresolved_conflict=(
                fulfillment.local_activity_id in manifest.unresolved_fulfillment_conflicts
            ),
        )
    for historical in manifest.historical_legacy_fulfillments.values():
        _validate_historical_fulfillment(
            publication_manifest,
            historical,
            activity=activities_by_local_id.get(historical.local_activity_id),
            has_unresolved_conflict=(
                historical.local_activity_id in manifest.unresolved_fulfillment_conflicts
            ),
        )
    return manifest, migrated_from_v1 or repaired_revoked_unpairs
