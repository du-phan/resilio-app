"""Strict publication-manifest transformations for the fulfillment cutover."""

from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.workout_fulfillment.legacy_contracts import (
    LegacyPublicationManifest,
    LegacyV7PublicationManifest,
)
from resilio.core.workout_fulfillment.migration_authority import (
    MigrationWorkoutAuthority,
    validate_migrated_publication_authority,
)
from resilio.core.workout_fulfillment.migration_validation import (
    WorkoutFulfillmentMigrationError,
    parse_aware_legacy_datetime,
)
from resilio.core.workout_publication.preparation import rendered_workout_sha256
from resilio.schemas.publication import (
    HistoricalFulfillmentRetirementConfirmation,
    HistoricalLegacyWorkoutPublication,
    PendingWorkoutPublication,
    PublicationDriftResolution,
    PublicationManifest,
    PublishedWorkout,
)

MigrationAuthorityIndex = dict[
    tuple[str, str, int, str],
    list[MigrationWorkoutAuthority],
]


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


def _index_authorities(
    authorities: list[MigrationWorkoutAuthority],
) -> MigrationAuthorityIndex:
    indexed: MigrationAuthorityIndex = {}
    for item in authorities:
        identity = item.workout.identity
        key = (
            identity.plan_id,
            identity.plan_revision_id,
            identity.week_number,
            identity.local_workout_id,
        )
        indexed.setdefault(key, []).append(item)
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
        observed_at_utc = parse_aware_legacy_datetime(
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


def _migrate_v7(
    raw: dict[str, object],
    authorities: list[MigrationWorkoutAuthority],
) -> PublicationManifest:
    try:
        legacy = LegacyV7PublicationManifest.model_validate(raw)
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Publication manifest violates its version 7 contract"
        ) from exc
    manifest = PublicationManifest(
        workouts=legacy.workouts,
        pending=legacy.pending,
        historical_fulfillment_event_retirements=[
            *legacy.retirement_history,
            *(legacy.retired[key] for key in sorted(legacy.retired)),
        ],
        historical_fulfillment_pending_retirements=[
            *legacy.pending_retirement_history,
            *(legacy.retired_pending[key] for key in sorted(legacy.retired_pending)),
        ],
        historical_legacy_workouts=legacy.historical_legacy_workouts,
        drift_resolutions=[
            PublicationDriftResolution.model_validate(item.model_dump(mode="python"))
            for item in legacy.drift_resolutions
            if item.strategy == "restore_local"
        ],
        historical_legacy_drift_resolutions=(
            legacy.historical_legacy_drift_resolutions
        ),
        historical_fulfillment_retirement_confirmations=[
            HistoricalFulfillmentRetirementConfirmation.model_validate(
                item.model_dump(mode="python")
            )
            for item in legacy.drift_resolutions
            if item.strategy == "retire_fulfilled"
        ],
    )
    try:
        for published_workout in manifest.workouts.values():
            validate_migrated_publication_authority(published_workout, authorities)
        for pending_publication in manifest.pending.values():
            validate_migrated_publication_authority(pending_publication, authorities)
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Publication manifest conflicts with schedule-time workout authority"
        ) from exc
    return manifest


def migrate_publication_manifest(
    raw: dict[str, object] | None,
    authorities: list[MigrationWorkoutAuthority],
    *,
    migration_date: date,
) -> tuple[PublicationManifest, bool]:
    """Transform publication v6/v7 into the strict native-pairing v8 contract."""
    if raw is None:
        return PublicationManifest(), False
    if raw.get("schema_version") == 8:
        return PublicationManifest.model_validate(raw), False
    if raw.get("schema_version") == 7:
        return _migrate_v7(raw, authorities), True
    if raw.get("schema_version") != 6:
        raise WorkoutFulfillmentMigrationError(
            "Publication migration requires schema version 6, 7, or 8"
        )
    try:
        legacy = LegacyPublicationManifest.model_validate(raw).model_dump(mode="json")
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Legacy publication manifest violates its version 6 contract"
        ) from exc
    authorities_by_identity = _index_authorities(authorities)
    historical_drifts = [
        {**item, "strategy": "restore_local"}
        if isinstance(item, dict) and "strategy" not in item
        else item
        for item in legacy["drift_resolutions"]
    ]
    workouts: dict[str, PublishedWorkout] = {}
    historical_workouts: dict[str, HistoricalLegacyWorkoutPublication] = {}
    for local_id, payload in legacy["workouts"].items():
        authority = _authority_for_legacy_publication(
            payload,
            pending=False,
            authorities_by_identity=authorities_by_identity,
            migration_date=migration_date,
        )
        if authority is None:
            historical_workouts[local_id] = HistoricalLegacyWorkoutPublication.model_validate(
                payload
            )
        else:
            record = _enriched_publication_record(payload, authority, pending=False)
            assert isinstance(record, PublishedWorkout)
            workouts[local_id] = record
    pending: dict[str, PendingWorkoutPublication] = {}
    for local_id, payload in legacy["pending"].items():
        authority = _authority_for_legacy_publication(
            payload,
            pending=True,
            authorities_by_identity=authorities_by_identity,
            migration_date=migration_date,
        )
        assert authority is not None
        record = _enriched_publication_record(payload, authority, pending=True)
        assert isinstance(record, PendingWorkoutPublication)
        pending[local_id] = record
    return (
        PublicationManifest.model_validate(
            {
                "workouts": workouts,
                "pending": pending,
                "historical_legacy_workouts": historical_workouts,
                "historical_legacy_drift_resolutions": historical_drifts,
            }
        ),
        True,
    )
