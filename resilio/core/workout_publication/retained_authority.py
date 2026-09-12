"""Recover exact applied authority retained by active publication records."""

from dataclasses import dataclass

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
from resilio.schemas.approvals import ActivePlanState
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout

PublicationAuthorityRecord = PublishedWorkout | PendingWorkoutPublication


@dataclass(frozen=True)
class RetainedPublicationAuthority:
    """One publication record's exact immutable workout authority."""

    workout: AuthoritativeWorkout
    provider_name: str


@dataclass(frozen=True)
class RetainedPublicationAuthorities:
    """Exact published and pending authority candidates for one stale identity."""

    published: RetainedPublicationAuthority | None = None
    pending: RetainedPublicationAuthority | None = None

    def preferred(self) -> RetainedPublicationAuthority:
        authority = self.published or self.pending
        if authority is None:
            raise PublicationSafetyError("Stale publication lacks retained workout authority")
        return authority


def _retained_authority(
    record: PublicationAuthorityRecord,
    *,
    active_plan: ActivePlanState,
) -> tuple[AuthoritativeWorkout, str]:
    applied_week_revisions = active_plan.applied_week_revisions
    revisions = [
        revision
        for revision in applied_week_revisions
        if revision.approval_id == record.applied_week_approval_id
        and revision.plan_id == record.workout_identity.plan_id
        and revision.plan_revision_id == record.workout_identity.plan_revision_id
        and revision.week_number == record.workout_identity.week_number
        and revision.applied_running_workouts_sha256 == record.applied_running_workouts_sha256
        and revision.schedule_timezone == record.schedule_timezone
        and applied_running_workouts_sha256(revision.applied_week_snapshot)
        == revision.applied_running_workouts_sha256
    ]
    if len(revisions) != 1:
        raise PublicationSafetyError(
            "Publication record lacks exactly one retained applied-week revision"
        )
    revision = revisions[0]
    local_workout_id = record.workout_identity.local_workout_id
    workout_matches = [
        workout
        for workout in revision.applied_week_snapshot.running_workouts
        if workout.id == local_workout_id
        and workout.date == record.occurrence_date
        and canonical_data_sha256(workout) == record.workout_prescription_sha256
    ]
    if len(workout_matches) != 1:
        raise PublicationSafetyError("Publication record differs from retained workout authority")
    workout = workout_matches[0]
    authority = AuthoritativeWorkout(
        identity=PlanWorkoutIdentity(
            plan_id=revision.plan_id,
            plan_revision_id=revision.plan_revision_id,
            week_number=revision.week_number,
            local_workout_id=local_workout_id,
        ),
        prescription=workout,
        applied_week_approval_id=revision.approval_id,
        applied_running_workouts_sha256=revision.applied_running_workouts_sha256,
        schedule_timezone=revision.schedule_timezone,
        applied_authority_history=applied_workout_authority_history(
            applied_week_revisions,
            week_number=revision.week_number,
            local_workout_id=local_workout_id,
        ),
    )
    provider_name = provider_workout_names(list(revision.applied_week_snapshot.running_workouts))[
        local_workout_id
    ]
    return authority, provider_name


def _same_plan_week(
    record: PublicationAuthorityRecord | None,
    requested_identity: PlanWorkoutIdentity,
) -> bool:
    return record is not None and (
        record.workout_identity.plan_id,
        record.workout_identity.plan_revision_id,
        record.workout_identity.week_number,
    ) == (
        requested_identity.plan_id,
        requested_identity.plan_revision_id,
        requested_identity.week_number,
    )


def _resolved_retained_authority(
    record: PublicationAuthorityRecord | None,
    *,
    active_plan: ActivePlanState,
    requested_identity: PlanWorkoutIdentity,
) -> RetainedPublicationAuthority | None:
    if not _same_plan_week(record, requested_identity):
        return None
    assert record is not None
    workout, provider_name = _retained_authority(record, active_plan=active_plan)
    return RetainedPublicationAuthority(
        workout=workout,
        provider_name=provider_name,
    )


def retained_publication_authority(
    repo: RepositoryIO,
    record: PublicationAuthorityRecord,
) -> RetainedPublicationAuthority:
    """Resolve one active record from its exact immutable applied revision."""
    active_plan = required_planning_state_unlocked(repo).active_plan
    if active_plan is None:
        raise PublicationSafetyError("Publication record lacks an active plan authority archive")
    workout, provider_name = _retained_authority(record, active_plan=active_plan)
    return RetainedPublicationAuthority(
        workout=workout,
        provider_name=provider_name,
    )


def retained_publication_authorities(
    repo: RepositoryIO,
    current_workouts: list[AuthoritativeWorkout],
) -> dict[str, RetainedPublicationAuthorities]:
    """Resolve every stale record independently from immutable applied revisions."""
    current_workout_ids = {workout.identity.local_workout_id for workout in current_workouts}
    state = required_planning_state_unlocked(repo)
    active_plan = state.active_plan
    if active_plan is None:
        return {}
    if not current_workouts:
        return {}
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
    manifest = load_manifest(repo)
    retained: dict[str, RetainedPublicationAuthorities] = {}
    stale_record_ids = (set(manifest.workouts) | set(manifest.pending)) - (current_workout_ids)
    for local_workout_id in sorted(stale_record_ids):
        published = manifest.workouts.get(local_workout_id)
        pending = manifest.pending.get(local_workout_id)
        published_authority = _resolved_retained_authority(
            published,
            active_plan=active_plan,
            requested_identity=requested_identity,
        )
        pending_authority = _resolved_retained_authority(
            pending,
            active_plan=active_plan,
            requested_identity=requested_identity,
        )
        if published_authority is None and pending_authority is None:
            continue
        retained[local_workout_id] = RetainedPublicationAuthorities(
            published=published_authority,
            pending=pending_authority,
        )
    return retained
