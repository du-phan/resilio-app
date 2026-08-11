"""Durable athlete-decision suppression for automatic provider pairing."""

from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.workout_fulfillment.candidates import (
    FulfillmentWorkoutAuthority,
    build_fulfillment_candidates,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest


def athlete_provider_pair_conflict(
    *,
    activity: CanonicalActivity,
    publication: PublishedWorkout | None,
    authoritative_workout: AuthoritativeWorkout | None,
    manifest: WorkoutFulfillmentManifest,
) -> dict[str, str] | None:
    """Reject automatic recreation of an exact denied or revoked association."""
    if publication is None:
        return None
    revoked = any(
        item.fulfillment.local_activity_id == activity.local_activity_id
        and item.fulfillment.workout_identity == publication.workout_identity
        and item.fulfillment.workout_prescription_sha256 == publication.workout_prescription_sha256
        and item.fulfillment.activity_performance_evidence_sha256
        == activity_performance_evidence_sha256(activity)
        for item in manifest.revoked_fulfillments
    )
    if revoked:
        return {
            "rule": "paired_event_fulfillment_was_revoked",
            "local_activity_id": activity.local_activity_id,
            "local_workout_id": publication.workout_identity.local_workout_id,
        }
    if authoritative_workout is None:
        return None
    authority = FulfillmentWorkoutAuthority(
        identity=authoritative_workout.identity,
        prescription=authoritative_workout.prescription,
        applied_week_approval_id=authoritative_workout.applied_week_approval_id,
        applied_running_workouts_sha256=(authoritative_workout.applied_running_workouts_sha256),
        schedule_timezone=authoritative_workout.schedule_timezone,
    )
    exact_candidates = build_fulfillment_candidates(
        activity=activity,
        workout_authorities=[authority],
        manifest=WorkoutFulfillmentManifest(),
    )
    dismissed = next(
        (
            manifest.dismissed_candidates[candidate.candidate_sha256]
            for candidate in exact_candidates
            if candidate.candidate_sha256 in manifest.dismissed_candidates
        ),
        None,
    )
    if dismissed is None or dismissed.workout_identity != publication.workout_identity:
        return None
    return {
        "rule": "paired_event_fulfillment_was_dismissed",
        "local_activity_id": activity.local_activity_id,
        "local_workout_id": publication.workout_identity.local_workout_id,
    }
