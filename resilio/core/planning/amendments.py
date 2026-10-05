"""Explicit, evidence-bound amendments preserving race-cycle ownership history."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH
from resilio.core.locking import OperationLock
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.planning.audit import new_planning_id, validated_utc_timestamp
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.freshness import require_fresh_plan
from resilio.core.planning.integrity import plan_skeleton_sha256, target_week_skeleton_sha256
from resilio.core.planning.schedule import schedule_authority_deadline_utc
from resilio.core.planning.source_state import coaching_evidence_source_sha256_unlocked
from resilio.core.planning.state_repository import (
    persist_planning_state,
    required_planning_state_unlocked,
)
from resilio.core.planning.weekly_evidence import validate_week_context
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.locking import coordinated_publication_plan_lock
from resilio.schemas.approvals import PlanningState
from resilio.schemas.coaching import WeekPlanningContext
from resilio.schemas.planning.amendments import MacroAmendmentProposal, MacroAmendmentValidation
from resilio.schemas.planning.approval_records import MacroAmendmentAudit, PlanApproval
from resilio.schemas.planning.plans import RaceMacroPlan
from resilio.schemas.planning.weeks import WeekPlan


def _load_proposal(path: Path) -> tuple[MacroAmendmentProposal, str]:
    try:
        content = path.read_bytes()
        return (
            MacroAmendmentProposal.model_validate_json(content),
            hashlib.sha256(content).hexdigest(),
        )
    except (OSError, ValueError) as exc:
        raise PlanOperationError(f"Macro amendment file is unavailable or invalid: {exc}") from exc


def _validate_long_run_target(week: WeekPlan) -> None:
    hints = week.workout_structure_hints.long_run
    if hints is None or hints.target_distance_meters is None:
        return
    if week.target_run_volume_meters <= 0:
        raise PlanOperationError("A long-run target requires positive weekly volume")
    share = 100 * hints.target_distance_meters / week.target_run_volume_meters
    if (
        not hints.minimum_weekly_run_volume_percent
        <= share
        <= hints.maximum_weekly_run_volume_percent
    ):
        raise PlanOperationError(
            "Amended long-run target is outside its approved weekly-distance range"
        )


def _require_unexecuted_week(
    repo: RepositoryIO, state: PlanningState, week: WeekPlan, timestamp: datetime
) -> None:
    assert state.active_plan is not None
    plan = state.active_plan.plan
    if any(
        schedule_authority_deadline_utc(
            workout, training_timezone=plan.constraints_snapshot.training_timezone
        )
        <= timestamp
        for workout in week.running_workouts
    ):
        raise PlanOperationError("A populated week with elapsed workouts cannot be amended")
    if any(
        record.workout_identity.plan_id == plan.id
        and record.workout_identity.plan_revision_id == plan.plan_revision_id
        and record.workout_identity.week_number == week.week_number
        for record in load_fulfillment_manifest(repo).fulfillments.values()
    ):
        raise PlanOperationError("A populated week with fulfilled workouts cannot be amended")


def _prepare_amendment(
    repo: RepositoryIO,
    state: PlanningState,
    proposal: MacroAmendmentProposal,
    timestamp: datetime,
) -> tuple[RaceMacroPlan, list[int], list[WeekPlanningContext]]:
    plan = require_fresh_plan(repo, state)
    active = state.active_plan
    if not isinstance(plan, RaceMacroPlan) or active is None or active.plan_approval is None:
        raise PlanOperationError("Macro amendment requires an approved active race plan")
    if active.pending_weekly_approval is not None:
        raise PlanOperationError("Resolve the pending weekly approval before amending its macro")
    if plan_skeleton_sha256(plan) != active.plan_approval.plan_skeleton_sha256:
        raise PlanOperationError("The approved macro skeleton has changed")
    if canonical_data_sha256(active) != proposal.expected_active_plan_sha256:
        raise PlanOperationError("Active planning state changed after the amendment proposal")
    if timestamp <= active.plan_approval.approved_at_utc:
        raise PlanOperationError("Macro amendment must follow the previous approval")
    latest_application = max(
        (item.applied_at_utc for item in active.applied_week_revisions), default=plan.created_at_utc
    )
    if timestamp <= latest_application:
        raise PlanOperationError("Macro amendment must follow existing weekly applications")
    local_date = timestamp.astimezone(ZoneInfo(plan.constraints_snapshot.training_timezone)).date()
    existing = {week.week_number: week for week in plan.weeks}
    replacements: dict[int, WeekPlan] = {}
    retired: list[int] = []
    contexts: list[WeekPlanningContext] = []
    for amended, reference in zip(
        proposal.weeks, proposal.planning_context_references, strict=True
    ):
        previous = existing.get(amended.week_number)
        if previous is None or (amended.start_date, amended.end_date) != (
            previous.start_date,
            previous.end_date,
        ):
            raise PlanOperationError(
                "Macro amendment must preserve the exact week identities and dates"
            )
        if amended.end_date < local_date:
            raise PlanOperationError("Completed calendar weeks cannot be amended")
        if target_week_skeleton_sha256(amended) == target_week_skeleton_sha256(previous):
            raise PlanOperationError("An amended week must change its macro skeleton")
        _validate_long_run_target(amended)
        context = validate_week_context(repo, plan=plan, target_week=previous, reference=reference)
        if context.evidence_as_of_date != local_date or context.generated_at_utc > timestamp:
            raise PlanOperationError(
                "Macro amendment requires planning evidence through its application date"
            )
        contexts.append(context)
        if previous.running_workouts:
            _require_unexecuted_week(repo, state, previous, timestamp)
            retired.append(previous.week_number)
        replacements[amended.week_number] = amended
    amended_plan = RaceMacroPlan.model_validate(
        plan.model_copy(
            update={
                "weeks": [replacements.get(week.week_number, week) for week in plan.weeks],
            }
        ).model_dump(mode="python", by_alias=True)
    )
    return amended_plan, retired, contexts


def validate_macro_amendment(
    repo: RepositoryIO,
    path: Path,
    *,
    evaluated_at_utc: datetime | None = None,
) -> MacroAmendmentValidation:
    proposal, digest = _load_proposal(path)
    timestamp = validated_utc_timestamp(evaluated_at_utc)
    with coordinated_publication_plan_lock(repo, "validate_macro_amendment"):
        state = required_planning_state_unlocked(repo)
        _, retired, _ = _prepare_amendment(repo, state, proposal, timestamp)
    return MacroAmendmentValidation(
        file_sha256=digest,
        amended_week_numbers=[week.week_number for week in proposal.weeks],
        retired_week_numbers=retired,
    )


def _amended_state(
    state: PlanningState,
    plan: RaceMacroPlan,
    proposal: MacroAmendmentProposal,
    path: Path,
    digest: str,
    confirmation: str,
    retired: list[int],
    timestamp: datetime,
) -> PlanningState:
    active = state.active_plan
    assert active is not None and active.plan_approval is not None
    approval = PlanApproval(
        approval_id=new_planning_id("plan_approval"),
        plan_kind=plan.kind,
        plan_id=plan.id,
        plan_revision_id=plan.plan_revision_id,
        plan_skeleton_sha256=plan_skeleton_sha256(plan),
        vdot_approval_id=plan.vdot_approval_id,
        planning_inputs_sha256=plan.planning_inputs_sha256,
        approved_at_utc=timestamp,
    )
    assert isinstance(active.plan, RaceMacroPlan)
    amendment = MacroAmendmentAudit(
        amendment_id=new_planning_id("macro_amendment"),
        previous_plan=active.plan,
        previous_plan_sha256=canonical_data_sha256(active.plan),
        previous_amendment_sha256=(
            canonical_data_sha256(active.macro_amendments[-1]) if active.macro_amendments else None
        ),
        previous_plan_approval=active.plan_approval,
        approval=approval,
        approved_file=str(path),
        approved_file_sha256=digest,
        expected_active_plan_sha256=proposal.expected_active_plan_sha256,
        planning_context_references=proposal.planning_context_references,
        affected_week_numbers=[week.week_number for week in proposal.weeks],
        rationale=proposal.rationale,
        athlete_confirmation_reference=confirmation,
        applied_at_utc=timestamp,
    )
    revisions = [
        item.model_copy(
            update={
                "active": False,
                "invalidated_at_utc": timestamp,
                "invalidation_reason": "superseded_by_macro_amendment",
            }
        )
        if item.active and item.week_number in retired
        else item
        for item in active.applied_week_revisions
    ]
    return state.model_copy(
        update={
            "active_plan": active.model_copy(
                update={
                    "plan": plan,
                    "plan_approval": approval,
                    "applied_week_revisions": revisions,
                    "macro_amendments": [*active.macro_amendments, amendment],
                }
            )
        }
    )


def apply_macro_amendment(
    repo: RepositoryIO,
    path: Path,
    *,
    expected_file_sha256: str,
    athlete_confirmation_reference: str,
    applied_at_utc: datetime | None = None,
) -> PlanningState:
    """Approve exact reviewed bytes, then atomically replace future skeletons.

    Cycle/workout ownership identities stay fixed. Each amendment has a new
    approval and immutable previous snapshot. Retired future workouts require
    fresh, separate weekly approval before synchronization is possible.
    """
    resolved = path.expanduser().resolve()
    proposal, digest = _load_proposal(resolved)
    if digest != expected_file_sha256:
        raise PlanOperationError("Macro amendment file changed after review")
    if not 10 <= len(athlete_confirmation_reference.strip()) <= 1_000:
        raise PlanOperationError("Macro amendment requires explicit athlete confirmation")
    timestamp = validated_utc_timestamp(applied_at_utc)
    with coordinated_publication_plan_lock(repo, "apply_macro_amendment"):
        state = required_planning_state_unlocked(repo)
        plan, retired, contexts = _prepare_amendment(repo, state, proposal, timestamp)
        updated = _amended_state(
            state,
            plan,
            proposal,
            resolved,
            digest,
            athlete_confirmation_reference,
            retired,
            timestamp,
        )
        with OperationLock(repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH), "apply_macro_amendment"):
            for context in contexts:
                current = coaching_evidence_source_sha256_unlocked(
                    repo,
                    evidence_as_of_date=context.evidence_as_of_date,
                    evidence_window_start=context.recent_history.evidence_window_start,
                )
                if current != context.source_state_sha256:
                    raise PlanOperationError(
                        "Training evidence changed before macro amendment commit"
                    )
            return persist_planning_state(repo, updated)
