"""Publication retirement policy for early fulfilled workouts."""

from __future__ import annotations

from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_authority_is_current,
    assert_fulfillment_is_usable,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)

WorkoutIdentityKey = tuple[str, str, int, str]


def _identity_key(fulfillment: WorkoutFulfillmentRecord) -> WorkoutIdentityKey:
    identity = fulfillment.workout_identity
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def fulfillment_retirements(
    *,
    publication_manifest: PublicationManifest,
    fulfillment_manifest: WorkoutFulfillmentManifest,
    workout_authorities_by_identity: dict[
        WorkoutIdentityKey,
        AuthoritativeWorkout,
    ],
    canonical_activities_by_id: dict[str, CanonicalActivity],
    as_of_date: date,
) -> dict[str, WorkoutFulfillmentRecord]:
    """Return exact active owned events safe to retire from the future calendar."""
    retirements: dict[str, WorkoutFulfillmentRecord] = {}
    for fulfillment in fulfillment_manifest.fulfillments.values():
        local_workout_id = fulfillment.workout_identity.local_workout_id
        authority = workout_authorities_by_identity.get(_identity_key(fulfillment))
        if authority is None:
            continue
        assert_fulfillment_authority_is_current(fulfillment, authority)
        activity = canonical_activities_by_id.get(fulfillment.local_activity_id)
        if activity is None:
            raise ValueError("Workout fulfillment activity is unavailable for retirement")
        assert_fulfillment_is_usable(
            fulfillment,
            activity,
            fulfillment_manifest,
        )
        publication = publication_manifest.workouts.get(local_workout_id)
        pending = publication_manifest.pending.get(local_workout_id)
        owned_identity = (
            publication.workout_identity
            if publication is not None
            else pending.workout_identity
            if pending is not None
            else None
        )
        occurrence_date = (
            publication.occurrence_date
            if publication is not None
            else pending.occurrence_date
            if pending is not None
            else None
        )
        if owned_identity is None or occurrence_date is None:
            continue
        if owned_identity != fulfillment.workout_identity:
            continue
        if fulfillment.athlete_confirmation is None:
            continue
        if fulfillment.schedule_offset_days >= 0:
            continue
        if occurrence_date <= as_of_date:
            continue
        retirements[local_workout_id] = fulfillment
    return retirements
