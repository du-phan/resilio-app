"""Prove retained macro approvals and select authority by approval time."""

from datetime import datetime

from resilio.canonical import canonical_data_sha256
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.integrity import plan_skeleton_sha256
from resilio.schemas.approvals import ActivePlanState
from resilio.schemas.planning.approval_records import MacroAmendmentAudit, PlanApproval
from resilio.schemas.planning.plans import TrainingPlan


def verify_macro_amendment_history(active: ActivePlanState) -> None:
    """Reject edited historical snapshots or a disconnected amendment chain."""
    previous_approval = None
    previous_amendment_sha256 = None
    for amendment in active.macro_amendments:
        if amendment.previous_amendment_sha256 != previous_amendment_sha256:
            raise PlanOperationError("Macro amendment history is truncated or changed")
        if canonical_data_sha256(amendment.previous_plan) != amendment.previous_plan_sha256:
            raise PlanOperationError("Retained macro amendment snapshot changed after approval")
        if (
            plan_skeleton_sha256(amendment.previous_plan)
            != amendment.previous_plan_approval.plan_skeleton_sha256
        ):
            raise PlanOperationError("Retained macro amendment snapshot changed after approval")
        if previous_approval is not None and amendment.previous_plan_approval != previous_approval:
            raise PlanOperationError("Macro amendment approval chain is disconnected")
        previous_approval = amendment.approval
        previous_amendment_sha256 = canonical_data_sha256(amendment)
    if previous_approval is not None:
        if (
            active.plan_approval != previous_approval
            or plan_skeleton_sha256(active.plan) != previous_approval.plan_skeleton_sha256
        ):
            raise PlanOperationError("Current macro does not match its latest amendment approval")


def macro_authority_at(
    plan: TrainingPlan,
    approval: PlanApproval,
    amendments: list[MacroAmendmentAudit],
    *,
    approved_at_utc: datetime,
) -> tuple[TrainingPlan, PlanApproval]:
    """Return the approved macro under which exact weekly bytes were approved."""
    for amendment in reversed(amendments):
        if approved_at_utc < amendment.applied_at_utc:
            plan, approval = amendment.previous_plan, amendment.previous_plan_approval
    return plan, approval
