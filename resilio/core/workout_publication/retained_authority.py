"""Recover exact applied authority retained by pending publication intents."""

from resilio.core.planning.adherence_evidence import (
    AuthoritativeWorkout,
    applied_workout_authority_history,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.planning.integrity import applied_running_workouts_sha256
from resilio.core.planning.state_repository import required_planning_state_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.naming import provider_workout_names
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.schemas.plan_history import PlanWorkoutIdentity


def retained_pending_publication_authorities(
    repo: RepositoryIO,
    current_workouts: list[AuthoritativeWorkout],
) -> tuple[dict[str, AuthoritativeWorkout], dict[str, str]]:
    """Resolve pending-only desired bytes from their immutable applied revision."""
    authorities = {
        workout.identity.local_workout_id: workout for workout in current_workouts
    }
    provider_names = provider_workout_names(
        [workout.prescription for workout in current_workouts]
    )
    state = required_planning_state_unlocked(repo)
    active_plan = state.active_plan
    if active_plan is None:
        return authorities, provider_names
    if not current_workouts:
        return authorities, provider_names
    requested_identity = current_workouts[0].identity
    if any(
        (
            workout.identity.plan_id,
            workout.identity.plan_revision_id,
            workout.identity.week_number,
        )
        != (
            requested_identity.plan_id,
            requested_identity.plan_revision_id,
            requested_identity.week_number,
        )
        for workout in current_workouts
    ):
        raise PublicationSafetyError("Current workout authority spans multiple plan weeks")
    for pending in load_manifest(repo).pending.values():
        pending_identity = pending.workout_identity
        if (
            pending_identity.plan_id,
            pending_identity.plan_revision_id,
            pending_identity.week_number,
        ) != (
            requested_identity.plan_id,
            requested_identity.plan_revision_id,
            requested_identity.week_number,
        ):
            continue
        local_workout_id = pending.workout_identity.local_workout_id
        if local_workout_id in authorities:
            continue
        revisions = [
            revision
            for revision in active_plan.applied_week_revisions
            if revision.approval_id == pending.applied_week_approval_id
            and revision.plan_id == pending.workout_identity.plan_id
            and revision.plan_revision_id == pending.workout_identity.plan_revision_id
            and revision.week_number == pending.workout_identity.week_number
            and revision.applied_running_workouts_sha256
            == pending.applied_running_workouts_sha256
            and revision.schedule_timezone == pending.schedule_timezone
            and applied_running_workouts_sha256(revision.applied_week_snapshot)
            == revision.applied_running_workouts_sha256
        ]
        if len(revisions) != 1:
            raise PublicationSafetyError(
                "Pending publication lacks exactly one retained applied-week revision"
            )
        revision = revisions[0]
        workout_matches = [
            workout
            for workout in revision.applied_week_snapshot.running_workouts
            if workout.id == local_workout_id
            and workout.date == pending.occurrence_date
            and canonical_data_sha256(workout)
            == pending.workout_prescription_sha256
        ]
        if len(workout_matches) != 1:
            raise PublicationSafetyError(
                "Pending publication differs from retained workout authority"
            )
        workout = workout_matches[0]
        authorities[local_workout_id] = AuthoritativeWorkout(
            identity=PlanWorkoutIdentity(
                plan_id=revision.plan_id,
                plan_revision_id=revision.plan_revision_id,
                week_number=revision.week_number,
                local_workout_id=local_workout_id,
            ),
            prescription=workout,
            applied_week_approval_id=revision.approval_id,
            applied_running_workouts_sha256=(
                revision.applied_running_workouts_sha256
            ),
            schedule_timezone=revision.schedule_timezone,
            applied_authority_history=applied_workout_authority_history(
                active_plan.applied_week_revisions,
                week_number=revision.week_number,
                local_workout_id=local_workout_id,
            ),
        )
        revision_names = provider_workout_names(
            list(revision.applied_week_snapshot.running_workouts)
        )
        provider_names[local_workout_id] = revision_names[local_workout_id]
    return authorities, provider_names
