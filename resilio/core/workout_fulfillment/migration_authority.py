"""Applied-workout authority proofs used by the one-shot fulfillment cutover."""

from dataclasses import dataclass
from datetime import date, datetime

from resilio.core.planning.adherence_evidence import (
    AppliedWorkoutAuthority,
    AuthoritativeWorkout,
)
from resilio.core.planning.artifacts import (
    canonical_data_sha256,
    load_all_closed_plan_archives,
)
from resilio.core.planning.integrity import assert_applied_week_revision_matches_plan
from resilio.core.planning.schedule import (
    WorkoutScheduleError,
    schedule_authority_deadline_utc,
)
from resilio.core.planning.state_repository import load_planning_aggregate_unlocked
from resilio.core.repository import RepositoryIO
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRecord


@dataclass(frozen=True)
class MigrationWorkoutAuthority:
    workout: AuthoritativeWorkout
    valid_from_utc: datetime
    valid_until_utc: datetime | None
    plan_approved_at_utc: datetime
    weekly_approved_at_utc: datetime
    effective_end_date: date
    retired_at_utc: datetime | None


def _temporally_applicable_authorities(
    identity: PlanWorkoutIdentity,
    authorities: list[MigrationWorkoutAuthority],
) -> list[MigrationWorkoutAuthority]:
    applicable: list[MigrationWorkoutAuthority] = []
    for item in authorities:
        if item.workout.identity != identity:
            continue
        deadline_utc = schedule_authority_deadline_utc(
            item.workout.prescription,
            training_timezone=item.workout.schedule_timezone,
        )
        if (
            item.workout.prescription.date <= item.effective_end_date
            and item.plan_approved_at_utc <= deadline_utc
            and item.weekly_approved_at_utc <= deadline_utc
            and item.valid_from_utc <= deadline_utc
            and (item.valid_until_utc is None or deadline_utc < item.valid_until_utc)
            and (item.retired_at_utc is None or deadline_utc < item.retired_at_utc)
        ):
            applicable.append(item)
    return applicable


def load_migration_authorities_unlocked(
    repo: RepositoryIO,
) -> list[MigrationWorkoutAuthority]:
    """Load exact applied revisions while the caller holds the plan lock."""
    state = load_planning_aggregate_unlocked(repo, allow_missing=True)
    if state is None:
        return []
    closed_archives = load_all_closed_plan_archives(repo, state.closed_plan_references)
    plan_states = [
        *[
            (
                archive.active_plan_snapshot,
                archive.closure.effective_end_date,
                archive.closure.closed_at_utc,
            )
            for archive in closed_archives
        ],
        *(
            [(state.active_plan, state.active_plan.plan.end_date, None)]
            if state.active_plan is not None
            else []
        ),
    ]
    authorities: list[MigrationWorkoutAuthority] = []
    for plan_state, effective_end_date, retired_at_utc in plan_states:
        plan = plan_state.plan
        plan_approval = plan_state.plan_approval
        if plan_approval is None:
            if plan_state.applied_week_revisions:
                raise ValueError("Applied-week evidence lacks an approved plan")
            continue
        for revision in plan_state.applied_week_revisions:
            assert_applied_week_revision_matches_plan(plan, revision)
            week = revision.applied_week_snapshot
            for workout in week.running_workouts:
                authorities.append(
                    MigrationWorkoutAuthority(
                        workout=AuthoritativeWorkout(
                            identity=PlanWorkoutIdentity(
                                plan_id=plan.id,
                                plan_revision_id=plan.plan_revision_id,
                                week_number=revision.week_number,
                                local_workout_id=workout.id,
                            ),
                            prescription=workout,
                            applied_week_approval_id=revision.approval_id,
                            applied_running_workouts_sha256=(
                                revision.applied_running_workouts_sha256
                            ),
                            schedule_timezone=revision.schedule_timezone,
                        ),
                        valid_from_utc=revision.applied_at_utc,
                        valid_until_utc=revision.invalidated_at_utc,
                        plan_approved_at_utc=plan_approval.approved_at_utc,
                        weekly_approved_at_utc=revision.weekly_approved_at_utc,
                        effective_end_date=effective_end_date,
                        retired_at_utc=retired_at_utc,
                    )
                )
    return authorities


def validate_migrated_fulfillment_authority(
    fulfillment: WorkoutFulfillmentRecord,
    authorities: list[MigrationWorkoutAuthority],
) -> None:
    """Prove old publication authority and schedule-time workout semantics."""
    matching = [
        item for item in authorities if item.workout.identity == fulfillment.workout_identity
    ]
    try:
        temporally_applicable = _temporally_applicable_authorities(
            fulfillment.workout_identity,
            authorities,
        )
    except WorkoutScheduleError as exc:
        raise ValueError("Migrated fulfillment schedule authority is invalid") from exc
    if len(temporally_applicable) != 1:
        raise ValueError("Migrated fulfillment lacks one exact schedule-time workout authority")
    selected = temporally_applicable[0].workout
    history = tuple(
        AppliedWorkoutAuthority(
            applied_week_approval_id=item.workout.applied_week_approval_id,
            applied_running_workouts_sha256=(item.workout.applied_running_workouts_sha256),
            workout_prescription_sha256=canonical_data_sha256(item.workout.prescription),
            schedule_timezone=item.workout.schedule_timezone,
            scheduled_local_date=item.workout.prescription.date,
        )
        for item in matching
    )
    from resilio.core.workout_fulfillment.evidence import (
        assert_fulfillment_authority_is_current,
    )

    assert_fulfillment_authority_is_current(
        fulfillment,
        AuthoritativeWorkout(
            identity=selected.identity,
            prescription=selected.prescription,
            applied_week_approval_id=selected.applied_week_approval_id,
            applied_running_workouts_sha256=(selected.applied_running_workouts_sha256),
            schedule_timezone=selected.schedule_timezone,
            applied_authority_history=history,
        ),
    )


def validate_migrated_publication_authority(
    publication: PublishedWorkout | PendingWorkoutPublication,
    authorities: list[MigrationWorkoutAuthority],
) -> None:
    """Prove one v7 active publication against schedule-time plan authority."""
    try:
        applicable = _temporally_applicable_authorities(
            publication.workout_identity,
            authorities,
        )
    except WorkoutScheduleError as exc:
        raise ValueError("Migrated publication schedule authority is invalid") from exc
    matches = [
        item
        for item in applicable
        if publication.applied_week_approval_id
        == item.workout.applied_week_approval_id
        and publication.applied_running_workouts_sha256
        == item.workout.applied_running_workouts_sha256
        and publication.workout_prescription_sha256
        == canonical_data_sha256(item.workout.prescription)
        and publication.schedule_timezone == item.workout.schedule_timezone
        and publication.occurrence_date == item.workout.prescription.date
    ]
    if len(matches) != 1:
        raise ValueError(
            "Migrated publication lacks one exact schedule-time workout authority"
        )
