"""Resolve publishable and historical exact-workout evidence."""

from datetime import date

from resilio.core.planning.adherence_evidence import (
    ApprovedWorkoutWindow,
    AuthoritativeWorkout,
    resolve_approved_workouts_for_date_range,
)
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    load_all_closed_plan_cycles,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.freshness import require_fresh_plan
from resilio.core.planning.integrity import (
    applied_workout_sha256,
    macro_skeleton_sha256,
)
from resilio.core.planning.policy import (
    WeekPolicyError,
    validate_populated_week,
)
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.state_repository import (
    load_planning_aggregate,
    required_planning_state_unlocked,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.plan_history import PlanWorkoutIdentity


def load_publishable_workouts(
    repo: RepositoryIO,
) -> list[AuthoritativeWorkout]:
    """Return workouts covered by active, exact applied-week approvals."""
    with coordinated_plan_lock(repo, "load_publishable_workouts"):
        state = required_planning_state_unlocked(repo)
        plan = require_fresh_plan(repo, state)
        if state.active_plan is None or state.active_plan.macro_approval is None:
            raise PlanOperationError("The current macro plan is not approved")
        if state.active_plan.macro_approval.macro_skeleton_sha256 != macro_skeleton_sha256(plan):
            raise PlanOperationError("The approved macro skeleton has changed")
        active_by_week = {
            approval.week_number: approval
            for approval in state.active_plan.applied_week_revisions
            if approval.active
        }
        workouts: list[AuthoritativeWorkout] = []
        for week in plan.weeks:
            if not week.workouts:
                continue
            try:
                validate_populated_week(plan, week)
            except WeekPolicyError as exc:
                raise PlanOperationError(
                    f"Week {week.week_number} violates approved policy: {exc}"
                ) from exc
            approval = active_by_week.get(week.week_number)
            if approval is None:
                raise PlanOperationError(
                    f"Week {week.week_number} has workouts without an active approval"
                )
            if approval.applied_workout_sha256 != applied_workout_sha256(week):
                raise PlanOperationError(
                    f"Week {week.week_number} changed after its approval was applied"
                )
            workouts.extend(
                AuthoritativeWorkout(
                    identity=PlanWorkoutIdentity(
                        plan_id=plan.id,
                        macro_revision_id=plan.macro_revision_id,
                        week_number=week.week_number,
                        local_workout_id=workout.id,
                    ),
                    prescription=workout,
                )
                for workout in week.workouts
            )
        return workouts


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
        closed_cycles = load_all_closed_plan_cycles(
            repo,
            state.closed_plan_cycle_references,
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
        closed_plan_cycles=closed_cycles,
    )
