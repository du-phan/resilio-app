"""Resolve exact publication authority for a revoked native provider pair."""

from collections.abc import Collection

from resilio.core.workout_fulfillment.association_identity import (
    fulfillment_record_sha256_lineage,
)
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublishedWorkout,
)
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRecord

PublicationAuthority = PublishedWorkout | PendingWorkoutPublication


def _record_matches_fulfillment(
    record: PublicationAuthority,
    fulfillment: WorkoutFulfillmentRecord,
) -> bool:
    return (
        record.workout_identity == fulfillment.workout_identity
        and record.applied_week_approval_id == fulfillment.applied_week_approval_id
        and record.applied_running_workouts_sha256 == fulfillment.applied_running_workouts_sha256
        and record.workout_prescription_sha256 == fulfillment.workout_prescription_sha256
        and record.schedule_timezone == fulfillment.schedule_timezone
        and record.occurrence_date == fulfillment.scheduled_local_date
    )


def _historical_authorities(
    manifest: PublicationManifest,
    fulfillment: WorkoutFulfillmentRecord,
    *,
    accepted_fulfillment_sha256_values: Collection[str],
) -> list[tuple[PublicationAuthority, int]]:
    provider_pair = fulfillment.provider_pair
    assert provider_pair is not None
    event_authorities = [
        (retirement.publication, retirement.publication.event_id)
        for retirement in manifest.historical_fulfillment_event_retirements
        if retirement.reopened_at_utc is None
        and retirement.fulfilling_local_activity_id == fulfillment.local_activity_id
        and retirement.fulfillment_record_sha256_at_retirement in accepted_fulfillment_sha256_values
        and retirement.publication.event_id == provider_pair.event_id
        and _record_matches_fulfillment(retirement.publication, fulfillment)
    ]
    pending_authorities = [
        (retirement.pending_publication, retirement.remote_event_id)
        for retirement in manifest.historical_fulfillment_pending_retirements
        if retirement.reopened_at_utc is None
        and retirement.remote_event_id is not None
        and retirement.fulfilling_local_activity_id == fulfillment.local_activity_id
        and retirement.fulfillment_record_sha256_at_retirement in accepted_fulfillment_sha256_values
        and retirement.remote_event_id == provider_pair.event_id
        and _record_matches_fulfillment(
            retirement.pending_publication,
            fulfillment,
        )
    ]
    return [*event_authorities, *pending_authorities]


def revoked_pair_publication_authority(
    manifest: PublicationManifest,
    fulfillment: WorkoutFulfillmentRecord,
    *,
    accepted_fulfillment_sha256_values: Collection[str] | None = None,
) -> PublicationAuthority | None:
    """Return one exact active or historical authority for a revoked pair."""
    provider_pair = fulfillment.provider_pair
    if provider_pair is None:
        return None
    local_workout_id = fulfillment.workout_identity.local_workout_id
    published = manifest.workouts.get(local_workout_id)
    pending = manifest.pending.get(local_workout_id)
    active_authorities: list[tuple[PublicationAuthority, int]] = []
    if published is not None and (
        published.event_id == provider_pair.event_id
        and _record_matches_fulfillment(published, fulfillment)
    ):
        active_authorities.append((published, published.event_id))
    if pending is not None and (
        (published is None or published.event_id == provider_pair.event_id)
        and _record_matches_fulfillment(pending, fulfillment)
    ):
        active_authorities.append((pending, provider_pair.event_id))
    accepted_hashes = set(
        accepted_fulfillment_sha256_values or fulfillment_record_sha256_lineage(fulfillment)
    )
    candidates = [
        *active_authorities,
        *_historical_authorities(
            manifest,
            fulfillment,
            accepted_fulfillment_sha256_values=accepted_hashes,
        ),
    ]
    if not candidates:
        return None
    ownership_signatures = {
        (
            record.uid,
            record.external_id,
            event_id,
        )
        for record, event_id in candidates
    }
    if len(ownership_signatures) != 1:
        raise ValueError("Revoked provider pair has competing publication authority")
    return next(
        (record for record, _ in candidates if isinstance(record, PublishedWorkout)),
        candidates[0][0],
    )
