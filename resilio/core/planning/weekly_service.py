"""Exact-file approval and application for one macro-plan week."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    load_all_closed_plan_cycles,
)
from resilio.core.planning.audit import (
    new_planning_id,
    validated_utc_timestamp,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.freshness import (
    load_planning_profile_unlocked,
    require_fresh_plan,
)
from resilio.core.planning.integrity import (
    applied_workout_sha256,
    macro_skeleton_sha256,
    sha256_file,
    target_week_skeleton_sha256,
)
from resilio.core.planning.policy import (
    WeekPolicyError,
    validate_populated_week,
)
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.state_repository import (
    persist_planning_state,
    required_planning_state_unlocked,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import (
    AppliedWeekRevision,
    PlanningState,
    WeeklyApplicationAction,
    WeeklyApproval,
)
from resilio.schemas.plan import (
    MasterPlan,
    WeekApplication,
    WeekPlan,
)


def load_week_application(path: Path) -> WeekApplication:
    try:
        return WeekApplication.model_validate_json(path.read_text())
    except OSError as exc:
        raise PlanOperationError(f"Approved week file could not be read: {exc}") from exc
    except ValueError as exc:
        raise PlanOperationError(f"Approved week file is invalid: {exc}") from exc


def _find_week(plan: MasterPlan, week_number: int) -> WeekPlan:
    matching = [week for week in plan.weeks if week.week_number == week_number]
    if len(matching) != 1:
        raise PlanOperationError("Weekly payload does not identify exactly one macro-plan week")
    return matching[0]


def _populate_and_validate_week(
    plan: MasterPlan,
    target_week: WeekPlan,
    application: WeekApplication,
) -> WeekPlan:
    try:
        populated_week = WeekPlan(
            week_number=target_week.week_number,
            phase=target_week.phase,
            start_date=target_week.start_date,
            end_date=target_week.end_date,
            target_run_volume_meters=target_week.target_run_volume_meters,
            workout_structure_hints=target_week.workout_structure_hints,
            workouts=application.workouts,
            is_recovery_week=target_week.is_recovery_week,
            notes=application.adjustment_rationale,
        )
        validate_populated_week(plan, populated_week)
    except (ValueError, WeekPolicyError) as exc:
        raise PlanOperationError(f"Weekly application violates approved policy: {exc}") from exc
    return populated_week


def _validate_workout_ids_are_globally_unique(
    repo: RepositoryIO,
    state: PlanningState,
    populated_week: WeekPlan,
) -> None:
    """Prevent one external ownership ID from crossing plan or week lineage."""
    assert state.active_plan is not None
    active_plan = state.active_plan.plan
    owners_by_workout_id: dict[str, tuple[str, int]] = {}
    try:
        closed_cycles = load_all_closed_plan_cycles(
            repo,
            state.closed_plan_cycle_references,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    for cycle in closed_cycles:
        plan = cycle.active_plan_snapshot.plan
        for week in plan.weeks:
            for workout in week.workouts:
                owners_by_workout_id[workout.id] = (
                    plan.id,
                    week.week_number,
                )
    for week in active_plan.weeks:
        if week.week_number == populated_week.week_number:
            continue
        for workout in week.workouts:
            owners_by_workout_id[workout.id] = (
                active_plan.id,
                week.week_number,
            )
    for workout in populated_week.workouts:
        if workout.id in owners_by_workout_id:
            raise PlanOperationError(
                "Workout ID is already owned by another plan or week: " f"{workout.id}"
            )


def validate_week_application(
    repo: RepositoryIO,
    application_file: Path,
) -> WeekApplication:
    """Validate an exact file against the fresh current macro and profile."""
    application = load_week_application(application_file)
    with coordinated_plan_lock(repo, "validate_week_application"):
        state = required_planning_state_unlocked(repo)
        plan = require_fresh_plan(repo, state)
        if state.active_plan is None or state.active_plan.macro_approval is None:
            raise PlanOperationError("The current macro plan is not approved")
        target_week = _find_week(plan, application.week_number)
        populated_week = _populate_and_validate_week(
            plan,
            target_week,
            application,
        )
        _validate_workout_ids_are_globally_unique(
            repo,
            state,
            populated_week,
        )
    return application


def approve_week_application(
    repo: RepositoryIO,
    approved_file: Path,
    *,
    approved_at_utc: datetime | None = None,
) -> PlanningState:
    """Bind an exact weekly proposal to its plan, revision, and prior content."""
    resolved_file = approved_file.expanduser().resolve()
    application = load_week_application(resolved_file)
    with coordinated_plan_lock(repo, "approve_week_application"):
        state = required_planning_state_unlocked(repo)
        plan = require_fresh_plan(repo, state)
        assert state.active_plan is not None
        macro_approval = state.active_plan.macro_approval
        if macro_approval is None:
            raise PlanOperationError("The current macro plan is not approved")
        if macro_approval.macro_skeleton_sha256 != macro_skeleton_sha256(plan):
            raise PlanOperationError("The approved macro skeleton has changed")
        week = _find_week(plan, application.week_number)
        populated_week = _populate_and_validate_week(plan, week, application)
        _validate_workout_ids_are_globally_unique(repo, state, populated_week)
        existing_hash = applied_workout_sha256(week) if week.workouts else None
        action = (
            WeeklyApplicationAction.REPLACE
            if existing_hash is not None
            else WeeklyApplicationAction.INITIAL
        )
        approval_timestamp = validated_utc_timestamp(approved_at_utc)
        if approval_timestamp < macro_approval.approved_at_utc:
            raise PlanOperationError("Weekly approval cannot predate macro approval")
        approval = WeeklyApproval(
            approval_id=new_planning_id("week_approval"),
            plan_id=plan.id,
            macro_revision_id=plan.macro_revision_id,
            macro_skeleton_sha256=macro_approval.macro_skeleton_sha256,
            week_number=application.week_number,
            target_week_skeleton_sha256=target_week_skeleton_sha256(week),
            action=action,
            previous_applied_workout_sha256=existing_hash,
            approved_at_utc=approval_timestamp,
            approved_file=str(resolved_file),
            approved_file_sha256=sha256_file(resolved_file),
        )
        active_plan = state.active_plan.model_copy(update={"pending_weekly_approval": approval})
        return persist_planning_state(
            repo,
            state.model_copy(update={"active_plan": active_plan}),
        )


def _updated_plan(
    plan: MasterPlan,
    populated_week: WeekPlan,
) -> MasterPlan:
    return MasterPlan.model_validate(
        plan.model_copy(
            update={
                "weeks": [
                    populated_week
                    if candidate.week_number == populated_week.week_number
                    else candidate
                    for candidate in plan.weeks
                ]
            }
        ).model_dump(mode="python", by_alias=True)
    )


def apply_approved_week(
    repo: RepositoryIO,
    approved_file: Path,
    *,
    applied_at_utc: datetime | None = None,
) -> MasterPlan:
    """Atomically consume an exact-file approval into its bound macro revision."""
    resolved_file = approved_file.expanduser().resolve()
    application = load_week_application(resolved_file)
    with coordinated_plan_lock(repo, "apply_approved_week"):
        state = required_planning_state_unlocked(repo)
        plan = require_fresh_plan(repo, state)
        if state.active_plan is None:
            raise PlanOperationError("No current training plan is available")
        approval = state.active_plan.pending_weekly_approval
        if approval is None:
            raise PlanOperationError("Weekly approval is missing")
        if approval.plan_id != plan.id or approval.macro_revision_id != plan.macro_revision_id:
            raise PlanOperationError("Weekly approval references another plan revision")
        if approval.week_number != application.week_number:
            raise PlanOperationError("Approved week number does not match the payload")
        if Path(approval.approved_file) != resolved_file:
            raise PlanOperationError("Approved file path does not match the payload")
        if sha256_file(resolved_file) != approval.approved_file_sha256:
            raise PlanOperationError("Approved week file changed after approval")
        week = _find_week(plan, application.week_number)
        if target_week_skeleton_sha256(week) != approval.target_week_skeleton_sha256:
            raise PlanOperationError("Target macro week changed after approval")
        current_hash = applied_workout_sha256(week) if week.workouts else None
        if current_hash != approval.previous_applied_workout_sha256:
            raise PlanOperationError("Previously applied weekly content changed")
        populated_week = _populate_and_validate_week(plan, week, application)
        _validate_workout_ids_are_globally_unique(repo, state, populated_week)
        timestamp = validated_utc_timestamp(applied_at_utc)
        if timestamp < approval.approved_at_utc:
            raise PlanOperationError("Weekly application cannot predate its weekly approval")
        revisions = list(state.active_plan.applied_week_revisions)
        previous = next(
            (
                item
                for item in revisions
                if item.week_number == application.week_number and item.active
            ),
            None,
        )
        if previous is not None:
            revisions = [
                item.model_copy(
                    update={
                        "active": False,
                        "invalidated_at_utc": timestamp,
                        "invalidation_reason": "replaced_by_new_week_approval",
                    }
                )
                if item.approval_id == previous.approval_id
                else item
                for item in revisions
            ]
        profile = load_planning_profile_unlocked(repo)
        revisions.append(
            AppliedWeekRevision(
                approval_id=approval.approval_id,
                plan_id=plan.id,
                macro_revision_id=plan.macro_revision_id,
                week_number=application.week_number,
                approved_file_sha256=approval.approved_file_sha256,
                applied_workout_sha256=applied_workout_sha256(populated_week),
                applied_week_snapshot=populated_week,
                schedule_timezone=profile.training_timezone,
                weekly_approved_at_utc=approval.approved_at_utc,
                applied_at_utc=timestamp,
            )
        )
        updated_plan = _updated_plan(plan, populated_week)
        active_plan = state.active_plan.model_copy(
            update={
                "plan": updated_plan,
                "pending_weekly_approval": None,
                "applied_week_revisions": revisions,
            }
        )
        persist_planning_state(
            repo,
            state.model_copy(update={"active_plan": active_plan}),
        )
        return updated_plan
