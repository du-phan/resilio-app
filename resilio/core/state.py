"""
Approval state persistence helpers.
"""

from typing import Optional, Union

from resilio.core.paths import approvals_state_path
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import ApprovalState
from resilio.schemas.repository import RepoError


def load_approval_state() -> Union[ApprovalState, None, RepoError]:
    """Load approval state from disk."""
    repo = RepositoryIO()
    return repo.read_json(approvals_state_path(), schema=ApprovalState)


def save_approval_state(state: ApprovalState) -> Optional[RepoError]:
    """Persist approval state to disk."""
    repo = RepositoryIO()
    return repo.write_json(approvals_state_path(), state)
