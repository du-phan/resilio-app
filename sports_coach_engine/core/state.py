"""
Approval state persistence helpers.
"""

from typing import Optional, Union

from sports_coach_engine.core.paths import approvals_state_path
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.approvals import ApprovalState
from sports_coach_engine.schemas.repository import RepoError


def load_approval_state() -> Union[ApprovalState, None, RepoError]:
    """Load approval state from disk."""
    repo = RepositoryIO()
    return repo.read_json(approvals_state_path(), schema=ApprovalState)


def save_approval_state(state: ApprovalState) -> Optional[RepoError]:
    """Persist approval state to disk."""
    repo = RepositoryIO()
    return repo.write_json(approvals_state_path(), state)
