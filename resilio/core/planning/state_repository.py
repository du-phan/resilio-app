"""Typed persistence boundary for the planning aggregate."""

from resilio.core.locking import OperationLockError
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    load_all_closed_plan_archives,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.profile_plan_transaction import (
    coordinated_plan_lock,
)
from resilio.core.repository import RepositoryIO
from resilio.core.state import load_planning_state, save_planning_state
from resilio.schemas.approvals import PlanningState
from resilio.schemas.plan import RaceMacroPlan
from resilio.schemas.repository import RepoError


def load_planning_aggregate_unlocked(
    repo: RepositoryIO,
    *,
    allow_missing: bool = False,
) -> PlanningState | None:
    result = load_planning_state(repo, allow_missing=allow_missing)
    if result is None:
        return None
    if isinstance(result, RepoError):
        raise PlanOperationError(f"Planning state is invalid: {result}")
    if result is not None:
        try:
            closed_cycles = load_all_closed_plan_archives(
                repo,
                result.closed_plan_references,
            )
        except PlanningArtifactError as exc:
            raise PlanOperationError(f"Planning history is invalid: {exc}") from exc
        approval_ids = {approval.approval_id for approval in result.vdot_approvals}
        missing_historical_approval_ids = sorted(
            {
                archive.active_plan_snapshot.plan.vdot_approval_id
                for archive in closed_cycles
                if isinstance(archive.active_plan_snapshot.plan, RaceMacroPlan)
            }
            - approval_ids
        )
        if missing_historical_approval_ids:
            raise PlanOperationError(
                "Planning history references an absent historical VDOT approval: "
                f"{missing_historical_approval_ids}"
            )
    return result


def load_planning_aggregate(
    repo: RepositoryIO,
    *,
    allow_missing: bool = False,
) -> PlanningState | None:
    """Read planning state while excluding profile/plan pair transitions."""
    try:
        with coordinated_plan_lock(repo, "read_planning_state"):
            return load_planning_aggregate_unlocked(
                repo,
                allow_missing=allow_missing,
            )
    except OperationLockError as exc:
        raise PlanOperationError(
            "Planning state is temporarily unavailable during a coordinated "
            "profile/plan transition"
        ) from exc


def required_planning_state_unlocked(repo: RepositoryIO) -> PlanningState:
    state = load_planning_aggregate_unlocked(repo, allow_missing=True)
    return state or PlanningState()


def required_planning_state(repo: RepositoryIO) -> PlanningState:
    state = load_planning_aggregate(repo, allow_missing=True)
    return state or PlanningState()


def persist_planning_state(
    repo: RepositoryIO,
    state: PlanningState,
) -> PlanningState:
    validated = PlanningState.model_validate(state.model_dump(mode="python"))
    error = save_planning_state(validated, repo)
    if error is not None:
        raise PlanOperationError(f"Planning state could not be saved: {error}")
    return validated
