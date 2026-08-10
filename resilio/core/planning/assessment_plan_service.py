"""Create evidence-bound baseline-assessment plan revisions."""

from __future__ import annotations

from datetime import datetime

from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    load_evidence_artifact,
)
from resilio.core.planning.audit import new_planning_id, validated_utc_timestamp
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.freshness import load_planning_profile_unlocked
from resilio.core.planning.integrity import (
    planning_constraints_snapshot,
    planning_inputs_sha256,
)
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.source_state import coaching_evidence_source_sha256
from resilio.core.planning.state_repository import (
    persist_planning_state,
    required_planning_state_unlocked,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import ActivePlanState
from resilio.schemas.planning.drafts import AssessmentPlanDraft
from resilio.schemas.planning.plans import BaselineAssessmentPlan
from resilio.schemas.planning_evidence import AssessmentPlanningContext
from resilio.schemas.profile import AthleteProfile


def _validated_assessment_context(
    repo: RepositoryIO,
    draft: AssessmentPlanDraft,
    profile: AthleteProfile,
) -> AssessmentPlanningContext:
    try:
        context = load_evidence_artifact(
            repo,
            draft.planning_context_reference,
            AssessmentPlanningContext,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    if context.planning_inputs_sha256 != planning_inputs_sha256(profile):
        raise PlanOperationError(
            "Assessment-planning context does not match the current planning inputs"
        )
    if context.current_constraints != planning_constraints_snapshot(profile):
        raise PlanOperationError(
            "Assessment-planning context constraints differ from the current profile"
        )
    if set(context.assessment_reasons) != set(draft.assessment_reasons):
        raise PlanOperationError("Assessment draft reasons differ from its evidence context")
    if context.temporary_schedule_constraints != draft.temporary_schedule_constraints:
        raise PlanOperationError(
            "Assessment draft temporary schedule differs from its evidence context"
        )
    if context.source_state_sha256 != coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=context.evidence_as_of_date,
    ):
        raise PlanOperationError(
            "Assessment-planning training evidence changed after context creation"
        )
    if min(week.start_date for week in draft.weeks) != context.intended_plan_start_date:
        raise PlanOperationError(
            "Assessment draft does not start on its evidence-bound intended Monday"
        )
    available_evidence_ids = {pointer.evidence_id for pointer in context.evidence_index}
    cited_evidence_ids: set[str] = set()
    for decision in draft.adaptation_decisions:
        cited_evidence_ids.update(decision.evidence_ids)
        unknown_ids = set(decision.evidence_ids) - available_evidence_ids
        if unknown_ids:
            raise PlanOperationError(
                "Assessment decision cites evidence absent from its context: "
                f"{sorted(unknown_ids)}"
            )
        if any(week_number > len(draft.weeks) for week_number in decision.affected_week_numbers):
            raise PlanOperationError(
                "Assessment decision references a week outside the draft horizon"
            )
    latest_recent_week = max(context.recent_detailed_weeks, key=lambda week: week.week_start)
    required_evidence_id = f"recent_week.{latest_recent_week.week_start.isoformat()}"
    required_evidence_ids = {required_evidence_id}
    if context.temporary_schedule_constraints:
        required_evidence_ids.add("assessment.temporary_schedule_constraints")
    missing_required_evidence_ids = required_evidence_ids - cited_evidence_ids
    if missing_required_evidence_ids:
        raise PlanOperationError(
            "Assessment decisions do not cite required context evidence: "
            f"{sorted(missing_required_evidence_ids)}"
        )
    return context


def create_assessment_plan(
    repo: RepositoryIO,
    draft: AssessmentPlanDraft,
    *,
    created_at_utc: datetime | None = None,
) -> BaselineAssessmentPlan:
    """Create a short baseline assessment without a VDOT dependency."""
    with coordinated_plan_lock(repo, "create_assessment_plan"):
        state = required_planning_state_unlocked(repo)
        if state.active_plan is not None:
            raise PlanOperationError("A current plan already exists; close it before replacement")
        profile = load_planning_profile_unlocked(repo)
        context = _validated_assessment_context(repo, draft, profile)
        creation_timestamp = validated_utc_timestamp(created_at_utc)
        if creation_timestamp < context.generated_at_utc:
            raise PlanOperationError("Assessment plan creation cannot predate its planning context")
        plan = BaselineAssessmentPlan(
            id=new_planning_id("plan"),
            plan_revision_id=new_planning_id("plan_revision"),
            planning_context_reference=draft.planning_context_reference,
            planning_inputs_sha256=planning_inputs_sha256(profile),
            created_at_utc=creation_timestamp,
            planning_rationale=draft.planning_rationale,
            adaptation_decisions=draft.adaptation_decisions,
            weeks=draft.weeks,
            constraints_snapshot=planning_constraints_snapshot(profile),
            assessment_reasons=draft.assessment_reasons,
            benchmark_intent=draft.benchmark_intent,
            temporary_schedule_constraints=draft.temporary_schedule_constraints,
            medical_rehabilitation_excluded=draft.medical_rehabilitation_excluded,
        )
        persist_planning_state(
            repo,
            state.model_copy(update={"active_plan": ActivePlanState(plan=plan)}),
        )
        return plan
