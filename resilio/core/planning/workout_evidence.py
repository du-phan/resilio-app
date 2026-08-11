"""Resolve publishable and historical exact-workout evidence."""

from datetime import date

from resilio.core.planning.adherence_evidence import (
    ApprovedWorkoutWindow,
    AuthoritativeWorkout,
    applied_workout_authority_history,
    resolve_approved_workouts_for_date_range,
)
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    load_all_closed_plan_archives,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.freshness import require_fresh_plan
from resilio.core.planning.integrity import (
    applied_running_workouts_sha256,
    plan_skeleton_sha256,
)
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.state_repository import (
    load_planning_aggregate,
    required_planning_state_unlocked,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import PlanningState
from resilio.schemas.plan_history import PlanWorkoutIdentity


def load_publishable_workouts_unlocked(
    repo: RepositoryIO,
    state: PlanningState,
) -> list[AuthoritativeWorkout]:
    """Return exact applied authority while the caller holds the plan lock.

    Application policy is enforced before a week is approved and applied. This
    read path verifies immutable approval identity and bytes without reapplying
    today's policy to historical evidence.
    """
    plan = require_fresh_plan(repo, state)
    if state.active_plan is None or state.active_plan.plan_approval is None:
        raise PlanOperationError("The current plan is not approved")
    if state.active_plan.plan_approval.plan_skeleton_sha256 != plan_skeleton_sha256(plan):
        raise PlanOperationError("The approved plan skeleton has changed")
    active_by_week = {
        approval.week_number: approval
        for approval in state.active_plan.applied_week_revisions
        if approval.active
    }
    workouts: list[AuthoritativeWorkout] = []
    for week in plan.weeks:
        if not week.running_workouts:
            continue
        approval = active_by_week.get(week.week_number)
        if approval is None:
            raise PlanOperationError(
                f"Week {week.week_number} has workouts without an active approval"
            )
        if approval.applied_running_workouts_sha256 != applied_running_workouts_sha256(week):
            raise PlanOperationError(
                f"Week {week.week_number} changed after its approval was applied"
            )
        workouts.extend(
            AuthoritativeWorkout(
                identity=PlanWorkoutIdentity(
                    plan_id=plan.id,
                    plan_revision_id=plan.plan_revision_id,
                    week_number=week.week_number,
                    local_workout_id=workout.id,
                ),
                prescription=workout,
                applied_week_approval_id=approval.approval_id,
                applied_running_workouts_sha256=(approval.applied_running_workouts_sha256),
                schedule_timezone=approval.schedule_timezone,
                applied_authority_history=applied_workout_authority_history(
                    state.active_plan.applied_week_revisions,
                    week_number=week.week_number,
                    local_workout_id=workout.id,
                ),
            )
            for workout in week.running_workouts
        )
    return workouts


def load_publishable_workouts(
    repo: RepositoryIO,
) -> list[AuthoritativeWorkout]:
    """Return workouts covered by active, exact applied-week approvals."""
    with coordinated_plan_lock(repo, "load_publishable_workouts"):
        return load_publishable_workouts_unlocked(
            repo,
            required_planning_state_unlocked(repo),
        )


def load_publishable_workout(
    repo: RepositoryIO,
    workout_id: str,
) -> AuthoritativeWorkout:
    matches = [
        workout
        for workout in load_publishable_workouts(repo)
        if workout.identity.local_workout_id == workout_id
    ]
    if len(matches) != 1:
        raise PlanOperationError(
            "Approved workout ID does not identify exactly one workout: " f"{workout_id}"
        )
    return matches[0]


def load_approved_workouts_for_date_range(
    repo: RepositoryIO,
    *,
    window_start: date,
    window_end: date,
) -> ApprovedWorkoutWindow:
    if window_end < window_start:
        raise ValueError("workout window end cannot precede its start")
    try:
        state = load_planning_aggregate(repo, allow_missing=True)
    except PlanOperationError as exc:
        return ApprovedWorkoutWindow(
            status="unavailable",
            workouts=[],
            reason=str(exc),
        )
    if state is None:
        return ApprovedWorkoutWindow(
            status="no_plan",
            workouts=[],
            reason="planning_state_missing",
        )
    try:
        closed_archives = load_all_closed_plan_archives(
            repo,
            state.closed_plan_references,
        )
    except PlanningArtifactError as exc:
        return ApprovedWorkoutWindow(
            status="unavailable",
            workouts=[],
            reason=str(exc),
        )
    return resolve_approved_workouts_for_date_range(
        state,
        window_start=window_start,
        window_end=window_end,
        closed_plan_archives=closed_archives,
    )
