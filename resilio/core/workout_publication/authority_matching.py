"""Exact publication-to-applied-workout authority matching."""

from resilio.core.planning.adherence_evidence import (
    AppliedWorkoutAuthority,
    AuthoritativeWorkout,
    current_applied_workout_authority,
)
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout


def _publication_authority(
    publication: PublishedWorkout | PendingWorkoutPublication,
) -> AppliedWorkoutAuthority:
    return AppliedWorkoutAuthority(
        applied_week_approval_id=publication.applied_week_approval_id,
        applied_running_workouts_sha256=(publication.applied_running_workouts_sha256),
        workout_prescription_sha256=publication.workout_prescription_sha256,
        schedule_timezone=publication.schedule_timezone,
        scheduled_local_date=publication.occurrence_date,
    )


def publication_record_matches_current_workout_authority(
    publication: PublishedWorkout | PendingWorkoutPublication,
    workout: AuthoritativeWorkout,
) -> bool:
    """Require one whole retained snapshot plus current workout semantics."""
    current_authority = current_applied_workout_authority(workout)
    return (
        publication.workout_identity == workout.identity
        and publication.workout_prescription_sha256 == current_authority.workout_prescription_sha256
        and publication.schedule_timezone == current_authority.schedule_timezone
        and publication.occurrence_date == current_authority.scheduled_local_date
        and _publication_authority(publication)
        in (current_authority, *workout.applied_authority_history)
    )


def publication_record_has_retained_workout_authority(
    publication: PublishedWorkout | PendingWorkoutPublication,
    workout: AuthoritativeWorkout,
) -> bool:
    """Match one exact current or historical authority without requiring current content."""
    current_authority = current_applied_workout_authority(workout)
    return publication.workout_identity == workout.identity and _publication_authority(
        publication
    ) in (current_authority, *workout.applied_authority_history)
