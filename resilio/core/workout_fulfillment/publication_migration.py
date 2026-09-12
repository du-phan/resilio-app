"""Strict publication-manifest transformations for the fulfillment cutover."""

from collections.abc import Mapping
from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.workout_fulfillment.association_identity import (
    fulfillment_association_sha256,
)
from resilio.core.workout_fulfillment.legacy_contracts import (
    LegacyPublicationManifest,
    LegacyV7PublicationManifest,
    LegacyV8PublicationManifest,
)
from resilio.core.workout_fulfillment.migration_authority import (
    MigrationWorkoutAuthority,
    validate_migrated_publication_authority,
)
from resilio.core.workout_fulfillment.migration_validation import (
    WorkoutFulfillmentMigrationError,
    parse_aware_legacy_datetime,
)
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    provider_local_date,
)
from resilio.core.workout_publication.preparation import rendered_workout_sha256
from resilio.core.workout_publication.semantics import (
    WorkoutSemanticsError,
    expected_workout_semantics,
    workout_semantics_sha256,
)
from resilio.schemas.publication import (
    HistoricalFulfillmentRetirementConfirmation,
    HistoricalLegacyWorkoutPublication,
    PendingWorkoutPublication,
    PublicationDriftResolution,
    PublicationManifest,
    PublishedWorkout,
)
from resilio.schemas.publication_placement import (
    FulfillmentProviderOccurrencePlacement,
    ProviderOccurrencePlacement,
)
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)

MigrationAuthorityIndex = dict[
    tuple[str, str, int, str],
    list[MigrationWorkoutAuthority],
]
PublicationRecord = PublishedWorkout | PendingWorkoutPublication


def _authority_step_semantics_sha256(authority: AuthoritativeWorkout) -> str:
    structured_workout = authority.prescription.structured_workout
    if structured_workout is None:
        raise WorkoutFulfillmentMigrationError(
            "Published workout authority lacks structured step semantics"
        )
    try:
        return workout_semantics_sha256(expected_workout_semantics(structured_workout.steps))
    except WorkoutSemanticsError as exc:
        raise WorkoutFulfillmentMigrationError(str(exc)) from exc


def _fulfillment_matches_occurrence(
    fulfillment: WorkoutFulfillmentRecord,
    record: PublicationRecord,
    provider_occurrence_date: date,
) -> bool:
    associated_execution_dates = {
        fulfillment.execution_local_date,
        *(
            revision.previous_execution_local_date
            for revision in fulfillment.activity_evidence_revisions
        ),
    }
    return (
        fulfillment.workout_identity == record.workout_identity
        and fulfillment.workout_prescription_sha256 == record.workout_prescription_sha256
        and fulfillment.schedule_timezone == record.schedule_timezone
        and fulfillment.scheduled_local_date == record.occurrence_date
        and provider_occurrence_date in associated_execution_dates
        and (
            not isinstance(record, PublishedWorkout)
            or fulfillment.provider_pair is None
            or fulfillment.provider_pair.event_id == record.event_id
        )
    )


def _matching_fulfillment(
    record: PublicationRecord,
    provider_occurrence_date: date,
    fulfillment_manifest: WorkoutFulfillmentManifest,
) -> WorkoutFulfillmentRecord | None:
    active_matches = [
        fulfillment
        for fulfillment in fulfillment_manifest.fulfillments.values()
        if _fulfillment_matches_occurrence(
            fulfillment,
            record,
            provider_occurrence_date,
        )
    ]
    if len(active_matches) > 1:
        raise WorkoutFulfillmentMigrationError(
            "Publication occurrence has competing active fulfillment authority"
        )
    if active_matches:
        return active_matches[0]
    revoked_matches = [
        revocation
        for revocation in fulfillment_manifest.revoked_fulfillments
        if _fulfillment_matches_occurrence(
            revocation.fulfillment,
            record,
            provider_occurrence_date,
        )
    ]
    if not revoked_matches:
        return None
    latest_revocation = max(
        revoked_matches,
        key=lambda item: (item.revoked_at_utc, item.revocation_id),
    )
    return latest_revocation.fulfillment


def _provider_occurrence_placement(
    record: PublicationRecord,
    *,
    fulfillment_manifest: WorkoutFulfillmentManifest,
) -> ProviderOccurrencePlacement:
    try:
        provider_occurrence_date = provider_local_date(record.provider_start_date_local)
    except PublicationSafetyError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Publication occurrence has an invalid provider local timestamp"
        ) from exc
    matching_fulfillment = _matching_fulfillment(
        record,
        provider_occurrence_date,
        fulfillment_manifest,
    )
    override = (
        FulfillmentProviderOccurrencePlacement(
            local_activity_id=matching_fulfillment.local_activity_id,
            fulfillment_association_sha256=fulfillment_association_sha256(matching_fulfillment),
            execution_local_date=provider_occurrence_date,
        )
        if matching_fulfillment is not None
        else None
    )
    moved = provider_occurrence_date != record.occurrence_date
    if moved and override is None:
        raise WorkoutFulfillmentMigrationError(
            "Off-schedule publication lacks exact fulfillment placement authority"
        )
    return ProviderOccurrencePlacement(
        calendar_source="approved_schedule",
        calendar_occurrence_date=record.occurrence_date,
        fulfillment_override=override,
    )


def _provider_occurrence_placements(
    records: Mapping[str, PublicationRecord],
    *,
    fulfillment_manifest: WorkoutFulfillmentManifest,
) -> dict[str, ProviderOccurrencePlacement]:
    return {
        local_workout_id: _provider_occurrence_placement(
            record,
            fulfillment_manifest=fulfillment_manifest,
        )
        for local_workout_id, record in records.items()
    }


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


def _enrich_active_publication_step_semantics(
    raw: dict[str, object],
    authorities: list[MigrationWorkoutAuthority],
    *,
    migration_date: date,
) -> dict[str, object]:
    """Add v9 parsed-semantic evidence from exact schedule-time authority."""
    raw_workouts = raw.get("workouts", {})
    if not isinstance(raw_workouts, dict):
        raise WorkoutFulfillmentMigrationError("Legacy publication workouts must be an object")
    authorities_by_identity = _index_authorities(authorities)
    enriched_workouts: dict[str, object] = {}
    for local_workout_id, payload in raw_workouts.items():
        authority = _authority_for_legacy_publication(
            payload,
            pending=False,
            authorities_by_identity=authorities_by_identity,
            migration_date=migration_date,
        )
        if authority is None or not isinstance(payload, dict):
            raise WorkoutFulfillmentMigrationError(
                "Active publication lacks exact schedule-time workout authority "
                "for parsed semantics"
            )
        enriched_workouts[local_workout_id] = {
            **payload,
            "provider_step_semantics_sha256": (_authority_step_semantics_sha256(authority)),
        }
    return {**raw, "workouts": enriched_workouts}


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
    if not pending:
        enriched["provider_step_semantics_sha256"] = _authority_step_semantics_sha256(authority)
    model = PendingWorkoutPublication if pending else PublishedWorkout
    return model.model_validate(enriched)


def _migrate_v7(
    raw: dict[str, object],
    authorities: list[MigrationWorkoutAuthority],
    fulfillment_manifest: WorkoutFulfillmentManifest,
    *,
    migration_date: date,
) -> PublicationManifest:
    raw = _enrich_active_publication_step_semantics(
        raw,
        authorities,
        migration_date=migration_date,
    )
    try:
        legacy = LegacyV7PublicationManifest.model_validate(raw)
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Publication manifest violates its version 7 contract"
        ) from exc
    manifest = PublicationManifest(
        workouts=legacy.workouts,
        pending=legacy.pending,
        workout_provider_occurrence_placements=_provider_occurrence_placements(
            legacy.workouts,
            fulfillment_manifest=fulfillment_manifest,
        ),
        pending_provider_occurrence_placements=_provider_occurrence_placements(
            legacy.pending,
            fulfillment_manifest=fulfillment_manifest,
        ),
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
        historical_legacy_drift_resolutions=(legacy.historical_legacy_drift_resolutions),
        historical_fulfillment_retirement_confirmations=[
            HistoricalFulfillmentRetirementConfirmation.model_validate(
                item.model_dump(mode="python")
            )
            for item in legacy.drift_resolutions
            if item.strategy == "retire_fulfilled"
        ],
    )
    _validate_active_publication_authorities(manifest, authorities)
    return manifest


def _validate_active_publication_authorities(
    manifest: PublicationManifest,
    authorities: list[MigrationWorkoutAuthority],
) -> None:
    try:
        for published_workout in manifest.workouts.values():
            validate_migrated_publication_authority(published_workout, authorities)
        for pending_publication in manifest.pending.values():
            validate_migrated_publication_authority(pending_publication, authorities)
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Publication manifest conflicts with schedule-time workout authority"
        ) from exc


def _migrate_v8(
    raw: dict[str, object],
    authorities: list[MigrationWorkoutAuthority],
    fulfillment_manifest: WorkoutFulfillmentManifest,
    *,
    migration_date: date,
) -> PublicationManifest:
    raw = _enrich_active_publication_step_semantics(
        raw,
        authorities,
        migration_date=migration_date,
    )
    try:
        legacy = LegacyV8PublicationManifest.model_validate(raw)
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Publication manifest violates its version 8 contract"
        ) from exc
    try:
        manifest = PublicationManifest(
            workouts=legacy.workouts,
            pending=legacy.pending,
            workout_provider_occurrence_placements=_provider_occurrence_placements(
                legacy.workouts,
                fulfillment_manifest=fulfillment_manifest,
            ),
            pending_provider_occurrence_placements=_provider_occurrence_placements(
                legacy.pending,
                fulfillment_manifest=fulfillment_manifest,
            ),
            historical_fulfillment_event_retirements=(
                legacy.historical_fulfillment_event_retirements
            ),
            historical_fulfillment_pending_retirements=(
                legacy.historical_fulfillment_pending_retirements
            ),
            historical_legacy_workouts=legacy.historical_legacy_workouts,
            drift_resolutions=legacy.drift_resolutions,
            historical_legacy_drift_resolutions=(legacy.historical_legacy_drift_resolutions),
            historical_fulfillment_retirement_confirmations=(
                legacy.historical_fulfillment_retirement_confirmations
            ),
        )
    except ValueError as exc:
        raise WorkoutFulfillmentMigrationError(
            "Publication manifest cannot satisfy the version 9 contract"
        ) from exc
    _validate_active_publication_authorities(manifest, authorities)
    return manifest


def migrate_publication_manifest(
    raw: dict[str, object] | None,
    authorities: list[MigrationWorkoutAuthority],
    *,
    migration_date: date,
    fulfillment_manifest: WorkoutFulfillmentManifest | None = None,
) -> tuple[PublicationManifest, bool]:
    """Transform publication v6-v8 into the explicit-placement v9 contract."""
    fulfillment_manifest = fulfillment_manifest or WorkoutFulfillmentManifest()
    if raw is None:
        return PublicationManifest(), False
    if raw.get("schema_version") == 9:
        return PublicationManifest.model_validate(raw), False
    if raw.get("schema_version") == 8:
        return _migrate_v8(
            raw,
            authorities,
            fulfillment_manifest,
            migration_date=migration_date,
        ), True
    if raw.get("schema_version") == 7:
        return _migrate_v7(
            raw,
            authorities,
            fulfillment_manifest,
            migration_date=migration_date,
        ), True
    if raw.get("schema_version") != 6:
        raise WorkoutFulfillmentMigrationError(
            "Publication migration requires schema version 6, 7, 8, or 9"
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
                "workout_provider_occurrence_placements": (
                    _provider_occurrence_placements(
                        workouts,
                        fulfillment_manifest=fulfillment_manifest,
                    )
                ),
                "pending_provider_occurrence_placements": (
                    _provider_occurrence_placements(
                        pending,
                        fulfillment_manifest=fulfillment_manifest,
                    )
                ),
                "historical_legacy_workouts": historical_workouts,
                "historical_legacy_drift_resolutions": historical_drifts,
            }
        ),
        True,
    )
