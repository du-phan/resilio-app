"""Exact-file approval and application for one plan week."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import TypeAdapter

from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    canonical_data_sha256,
    load_all_closed_plan_archives,
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
    applied_running_workouts_sha256,
    plan_skeleton_sha256,
    sha256_file,
    target_week_skeleton_sha256,
)
from resilio.core.planning.policy import (
    WeekPolicyError,
    validate_populated_week,
)
from resilio.core.planning.state_repository import (
    persist_planning_state,
    required_planning_state_unlocked,
)
from resilio.core.planning.weekly_evidence import validate_week_planning_evidence
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.locking import coordinated_publication_plan_lock
from resilio.core.workout_publication.publication_deletions import (
    publication_deletion_workout_ids,
)
from resilio.schemas.approvals import (
    AppliedWeekRevision,
    PlanningState,
    WeeklyApplicationAction,
    WeeklyApproval,
)
from resilio.schemas.planning.applications import WeekApplication
from resilio.schemas.planning.plans import TrainingPlan
from resilio.schemas.planning.weeks import WeekPlan

TRAINING_PLAN_ADAPTER: TypeAdapter[TrainingPlan] = TypeAdapter(TrainingPlan)


def load_week_application(path: Path) -> WeekApplication:
    try:
        return WeekApplication.model_validate_json(path.read_text())
    except OSError as exc:
        raise PlanOperationError(f"Approved week file could not be read: {exc}") from exc
    except ValueError as exc:
        raise PlanOperationError(f"Approved week file is invalid: {exc}") from exc


def _find_week(plan: TrainingPlan, week_number: int) -> WeekPlan:
    matching = [week for week in plan.weeks if week.week_number == week_number]
    if len(matching) != 1:
        raise PlanOperationError("Weekly payload does not identify exactly one plan week")
    return matching[0]


def _populate_and_validate_week(
    plan: TrainingPlan,
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
            running_workouts=application.running_workouts,
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
        closed_cycles = load_all_closed_plan_archives(
            repo,
            state.closed_plan_references,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    for cycle in closed_cycles:
        plan = cycle.active_plan_snapshot.plan
        for week in plan.weeks:
            for workout in week.running_workouts:
                owners_by_workout_id[workout.id] = (
                    plan.id,
                    week.week_number,
                )
    for week in active_plan.weeks:
        if week.week_number == populated_week.week_number:
            continue
        for workout in week.running_workouts:
            owners_by_workout_id[workout.id] = (
                active_plan.id,
                week.week_number,
            )
    for workout in populated_week.running_workouts:
        if workout.id in owners_by_workout_id:
            raise PlanOperationError(
                "Workout ID is already owned by another plan or week: " f"{workout.id}"
            )
    tombstoned_ids = publication_deletion_workout_ids(repo).intersection(
        workout.id for workout in populated_week.running_workouts
    )
    if tombstoned_ids:
        raise PlanOperationError(
            "Workout IDs are permanently reserved by publication deletion tombstones: "
            f"{sorted(tombstoned_ids)}"
        )


def validate_week_application(
    repo: RepositoryIO,
    application_file: Path,
) -> WeekApplication:
    """Validate an exact file against the fresh current macro and profile."""
    application = load_week_application(application_file)
    with coordinated_publication_plan_lock(repo, "validate_week_application"):
        state = required_planning_state_unlocked(repo)
        plan = require_fresh_plan(repo, state)
        if state.active_plan is None or state.active_plan.plan_approval is None:
            raise PlanOperationError("The current plan is not approved")
        target_week = _find_week(plan, application.week_number)
        validate_week_planning_evidence(
            repo,
            plan=plan,
            target_week=target_week,
            application=application,
        )
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
    with coordinated_publication_plan_lock(repo, "approve_week_application"):
        state = required_planning_state_unlocked(repo)
        plan = require_fresh_plan(repo, state)
        assert state.active_plan is not None
        plan_approval = state.active_plan.plan_approval
        if plan_approval is None:
            raise PlanOperationError("The current plan is not approved")
        if plan_approval.plan_skeleton_sha256 != plan_skeleton_sha256(plan):
            raise PlanOperationError("The approved plan skeleton has changed")
        approval_timestamp = validated_utc_timestamp(approved_at_utc)
        if approval_timestamp < plan_approval.approved_at_utc:
            raise PlanOperationError("Weekly approval cannot predate plan approval")
        week = _find_week(plan, application.week_number)
        planning_context = validate_week_planning_evidence(
            repo,
            plan=plan,
            target_week=week,
            application=application,
        )
        populated_week = _populate_and_validate_week(plan, week, application)
        _validate_workout_ids_are_globally_unique(repo, state, populated_week)
        existing_hash = applied_running_workouts_sha256(week) if week.running_workouts else None
        action = (
            WeeklyApplicationAction.REPLACE
            if existing_hash is not None
            else WeeklyApplicationAction.INITIAL
        )
        if approval_timestamp < planning_context.generated_at_utc:
            raise PlanOperationError("Weekly approval cannot predate its week-planning context")
        approval = WeeklyApproval(
            approval_id=new_planning_id("week_approval"),
            plan_id=plan.id,
            plan_revision_id=plan.plan_revision_id,
            plan_skeleton_sha256=plan_approval.plan_skeleton_sha256,
            week_number=application.week_number,
            target_week_skeleton_sha256=target_week_skeleton_sha256(week),
            action=action,
            previous_applied_running_workouts_sha256=existing_hash,
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
    plan: TrainingPlan,
    populated_week: WeekPlan,
) -> TrainingPlan:
    return TRAINING_PLAN_ADAPTER.validate_python(
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


def _assert_fulfilled_workouts_unchanged(
    repo: RepositoryIO,
    *,
    previous_revision: AppliedWeekRevision,
    populated_week: WeekPlan,
) -> None:
    prior_workouts = {
        workout.id: workout for workout in previous_revision.applied_week_snapshot.running_workouts
    }
    proposed_workouts = {workout.id: workout for workout in populated_week.running_workouts}
    for fulfillment in load_fulfillment_manifest(repo).fulfillments.values():
        identity = fulfillment.workout_identity
        if (
            identity.plan_id != previous_revision.plan_id
            or identity.plan_revision_id != previous_revision.plan_revision_id
            or identity.week_number != previous_revision.week_number
        ):
            continue
        prior = prior_workouts.get(identity.local_workout_id)
        if prior is None or canonical_data_sha256(prior) != fulfillment.workout_prescription_sha256:
            raise PlanOperationError(
                "Fulfilled workout authority no longer matches its applied-week snapshot"
            )
        proposed = proposed_workouts.get(identity.local_workout_id)
        if (
            proposed is None
            or canonical_data_sha256(proposed) != fulfillment.workout_prescription_sha256
        ):
            raise PlanOperationError(
                "A weekly replacement cannot remove or alter a fulfilled workout"
            )


def apply_approved_week(
    repo: RepositoryIO,
    approved_file: Path,
    *,
    applied_at_utc: datetime | None = None,
) -> TrainingPlan:
    """Atomically consume an exact-file approval into its bound plan revision."""
    resolved_file = approved_file.expanduser().resolve()
    application = load_week_application(resolved_file)
    with coordinated_publication_plan_lock(repo, "apply_approved_week"):
        state = required_planning_state_unlocked(repo)
        plan = require_fresh_plan(repo, state)
        if state.active_plan is None:
            raise PlanOperationError("No current training plan is available")
        approval = state.active_plan.pending_weekly_approval
        if approval is None:
            raise PlanOperationError("Weekly approval is missing")
        if approval.plan_id != plan.id or approval.plan_revision_id != plan.plan_revision_id:
            raise PlanOperationError("Weekly approval references another plan revision")
        if approval.week_number != application.week_number:
            raise PlanOperationError("Approved week number does not match the payload")
        if Path(approval.approved_file) != resolved_file:
            raise PlanOperationError("Approved file path does not match the payload")
        if sha256_file(resolved_file) != approval.approved_file_sha256:
            raise PlanOperationError("Approved week file changed after approval")
        week = _find_week(plan, application.week_number)
        if target_week_skeleton_sha256(week) != approval.target_week_skeleton_sha256:
            raise PlanOperationError("Target plan week changed after approval")
        current_hash = applied_running_workouts_sha256(week) if week.running_workouts else None
        if current_hash != approval.previous_applied_running_workouts_sha256:
            raise PlanOperationError("Previously applied weekly content changed")
        validate_week_planning_evidence(
            repo,
            plan=plan,
            target_week=week,
            application=application,
        )
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
            _assert_fulfilled_workouts_unchanged(
                repo,
                previous_revision=previous,
                populated_week=populated_week,
            )
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
                plan_revision_id=plan.plan_revision_id,
                week_number=application.week_number,
                approved_file_sha256=approval.approved_file_sha256,
                planning_context_reference=application.planning_context_reference,
                applied_running_workouts_sha256=(applied_running_workouts_sha256(populated_week)),
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
