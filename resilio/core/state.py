"""Atomic persistence for the planning aggregate."""

from __future__ import annotations

from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import PlanningState
from resilio.schemas.repository import ReadOptions, RepoError

PLANNING_STATE_PATH = "data/plans/planning_state.yaml"


def load_planning_state(
    repo: RepositoryIO,
    *,
    allow_missing: bool = False,
) -> PlanningState | None | RepoError:
    """Load the only persisted plan and approval aggregate."""
    return repo.read_yaml(
        PLANNING_STATE_PATH,
        PlanningState,
        ReadOptions(allow_missing=allow_missing),
    )


def save_planning_state(
    state: PlanningState,
    repo: RepositoryIO,
) -> RepoError | None:
    """Validate and atomically persist one complete planning transition."""
    validated = PlanningState.model_validate(state.model_dump(mode="python"))
    return repo.write_yaml(PLANNING_STATE_PATH, validated)
