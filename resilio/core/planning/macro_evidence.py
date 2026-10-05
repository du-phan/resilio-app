"""Validate original macro evidence independently of progression readiness."""

from resilio.core.planning.artifacts import PlanningArtifactError, load_evidence_artifact
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.integrity import planning_constraints_snapshot, planning_inputs_sha256
from resilio.core.planning.source_state import coaching_evidence_source_sha256_unlocked
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import PlanningState
from resilio.schemas.macro_plan_draft import MacroPlanDraft
from resilio.schemas.planning_evidence import MacroPlanningContext
from resilio.schemas.profile import AthleteProfile


def load_validated_macro_context(
    repo: RepositoryIO,
    state: PlanningState,
    draft: MacroPlanDraft,
    profile: AthleteProfile,
) -> MacroPlanningContext:
    try:
        context = load_evidence_artifact(
            repo,
            draft.planning_context_reference,
            MacroPlanningContext,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    if context.planning_inputs_sha256 != planning_inputs_sha256(profile):
        raise PlanOperationError(
            "Macro-planning context does not match the current planning inputs"
        )
    if context.current_constraints != planning_constraints_snapshot(profile):
        raise PlanOperationError(
            "Macro-planning context constraints differ from the current profile"
        )
    if context.active_vdot_approval_id != state.active_vdot_approval_id:
        raise PlanOperationError("Macro-planning context does not use the active VDOT approval")
    if context.source_state_sha256 != coaching_evidence_source_sha256_unlocked(
        repo,
        evidence_as_of_date=context.evidence_as_of_date,
    ):
        raise PlanOperationError("Macro-planning training evidence changed after context creation")
    if min(week.start_date for week in draft.weeks) != context.intended_plan_start_date:
        raise PlanOperationError("Macro draft does not start on its evidence-bound intended Monday")
    archived_plan_ids = {reference.plan_id for reference in state.closed_plan_references}
    context_plan_ids = {summary.plan_id for summary in context.historical_plan_summaries} | {
        summary.plan_id for summary in context.historical_assessment_summaries
    }
    if context_plan_ids != archived_plan_ids:
        raise PlanOperationError(
            "Macro-planning context does not cover the complete closed-plan history"
        )
    if not context.recent_detailed_weeks:
        raise PlanOperationError("Macro-planning context must contain recent training evidence")
    available_evidence_ids = {pointer.evidence_id for pointer in context.evidence_index}
    cited_evidence_ids: set[str] = set()
    for decision in draft.adaptation_decisions:
        cited_evidence_ids.update(decision.evidence_ids)
        unknown_ids = set(decision.evidence_ids) - available_evidence_ids
        if unknown_ids:
            raise PlanOperationError(
                "Macro decision cites evidence absent from its context: " f"{sorted(unknown_ids)}"
            )
        if any(week_number > len(draft.weeks) for week_number in decision.affected_week_numbers):
            raise PlanOperationError("Macro decision references a week outside the draft horizon")
    latest_recent_week = max(
        context.recent_detailed_weeks,
        key=lambda week: week.week_start,
    )
    required_evidence_ids = {f"recent_week.{latest_recent_week.week_start.isoformat()}"}
    if context.historical_plan_summaries:
        latest_plan = max(
            context.historical_plan_summaries,
            key=lambda summary: (
                summary.effective_end_date,
                summary.plan_id,
            ),
        )
        required_evidence_ids.update(
            {
                f"closed_plan.{latest_plan.plan_id}.summary",
                f"goal_outcome.{latest_plan.plan_id}",
            }
        )
    if context.historical_assessment_summaries:
        latest_assessment = max(
            context.historical_assessment_summaries,
            key=lambda summary: (
                summary.result.performance_date,
                summary.plan_id,
            ),
        )
        required_evidence_ids.add(f"assessment_result.{latest_assessment.plan_id}")
    missing_required_ids = required_evidence_ids - cited_evidence_ids
    if missing_required_ids:
        raise PlanOperationError(
            "Macro decisions do not cite required renewal evidence: "
            f"{sorted(missing_required_ids)}"
        )
    return context
