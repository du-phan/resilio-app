"""Verify the evidence on which a current macro plan depends."""

from resilio.core.methodology import (
    MethodologyRegistryError,
    verify_methodology_selection,
)
from resilio.core.planning.approval_evidence import (
    ApprovalEvidenceError,
    verify_vdot_approval_unlocked,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.integrity import planning_profile_sha256
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import PlanningState, VDOTApproval
from resilio.schemas.plan import MasterPlan
from resilio.schemas.profile import AthleteProfile


def load_planning_profile_unlocked(repo: RepositoryIO) -> AthleteProfile:
    """Load profile state while the caller holds the coordinated plan lock."""
    try:
        profile = ProfileRepository(repo)._load_unlocked()
    except (OSError, ValueError) as exc:
        raise PlanOperationError(str(exc)) from exc
    if profile is None:
        raise PlanOperationError("Athlete profile does not exist")
    return profile


def require_verified_vdot_approval(
    repo: RepositoryIO,
    approval: VDOTApproval | None,
) -> VDOTApproval:
    try:
        return verify_vdot_approval_unlocked(repo, approval)
    except ApprovalEvidenceError as exc:
        raise PlanOperationError(str(exc)) from exc


def require_fresh_plan(
    repo: RepositoryIO,
    state: PlanningState,
) -> MasterPlan:
    active_plan = state.active_plan
    if active_plan is None:
        raise PlanOperationError("No current training plan is available")
    plan = active_plan.plan
    require_verified_vdot_approval(repo, state.active_vdot_approval)
    try:
        verify_methodology_selection(repo.repo_root, plan.methodology)
    except MethodologyRegistryError as exc:
        raise PlanOperationError(str(exc)) from exc
    if (
        planning_profile_sha256(load_planning_profile_unlocked(repo))
        != plan.planning_profile_sha256
    ):
        raise PlanOperationError(
            "The planning profile changed after this macro revision was created"
        )
    if active_plan.invalidated_at_utc is not None:
        raise PlanOperationError(
            f"The current plan is invalidated: " f"{active_plan.invalidation_reason}"
        )
    return plan
