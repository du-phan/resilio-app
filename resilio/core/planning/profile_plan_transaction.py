"""Crash-recoverable profile and dependent-plan state transition."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Literal

from pydantic import BaseModel, ConfigDict

from resilio.core.locking import OperationLock
from resilio.core.paths import athlete_profile_path
from resilio.core.planning.constants import PLAN_MUTATION_LOCK_PATH
from resilio.core.repository import RepositoryIO
from resilio.core.state import PLANNING_STATE_PATH
from resilio.schemas.approvals import PlanningState
from resilio.schemas.profile import AthleteProfile
from resilio.schemas.repository import RepoError

PROFILE_PLAN_TRANSACTION_PATH = "data/state/profile-plan-transaction.json"


class ProfilePlanTransactionError(OSError):
    """A coordinated profile/plan transition could not be made durable."""


class ProfilePlanTransaction(BaseModel):
    phase: Literal["prepared", "profile_written", "committed"]
    previous_profile: AthleteProfile
    updated_profile: AthleteProfile
    previous_planning_state: PlanningState
    updated_planning_state: PlanningState

    model_config = ConfigDict(extra="forbid")


def transaction_is_pending(repo: RepositoryIO) -> bool:
    return repo.file_exists(PROFILE_PLAN_TRANSACTION_PATH)


def _write_transaction(
    repo: RepositoryIO,
    transaction: ProfilePlanTransaction,
) -> None:
    error = repo.write_json(PROFILE_PLAN_TRANSACTION_PATH, transaction)
    if isinstance(error, RepoError):
        raise ProfilePlanTransactionError(
            f"Profile/plan transaction journal could not be written: {error}"
        )


def _write_state_pair(
    repo: RepositoryIO,
    *,
    profile: AthleteProfile,
    planning_state: PlanningState,
) -> None:
    profile_error = repo.write_yaml(athlete_profile_path(), profile)
    if isinstance(profile_error, RepoError):
        raise ProfilePlanTransactionError(f"Athlete profile recovery write failed: {profile_error}")
    planning_error = repo.write_yaml(PLANNING_STATE_PATH, planning_state)
    if isinstance(planning_error, RepoError):
        raise ProfilePlanTransactionError(f"Planning-state recovery write failed: {planning_error}")


def clear_profile_plan_transaction(repo: RepositoryIO) -> None:
    journal_path = repo.resolve_path(PROFILE_PLAN_TRANSACTION_PATH)
    journal_path.unlink(missing_ok=True)
    directory_descriptor = os.open(journal_path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def recover_profile_plan_transaction(repo: RepositoryIO) -> None:
    """Rollback incomplete state pairs or roll forward a committed pair."""
    result = repo.read_json(
        PROFILE_PLAN_TRANSACTION_PATH,
        ProfilePlanTransaction,
    )
    if result is None:
        return
    if isinstance(result, RepoError):
        raise ProfilePlanTransactionError(f"Profile/plan transaction journal is invalid: {result}")
    if result.phase == "committed":
        profile = result.updated_profile
        planning_state = result.updated_planning_state
    else:
        profile = result.previous_profile
        planning_state = result.previous_planning_state
    _write_state_pair(
        repo,
        profile=profile,
        planning_state=planning_state,
    )
    clear_profile_plan_transaction(repo)


@contextmanager
def coordinated_plan_lock(
    repo: RepositoryIO,
    operation: str,
) -> Iterator[None]:
    """Acquire the plan lock and recover any interrupted state pair."""
    with OperationLock(repo.resolve_path(PLAN_MUTATION_LOCK_PATH), operation):
        recover_profile_plan_transaction(repo)
        yield


def begin_profile_plan_transaction(
    repo: RepositoryIO,
    *,
    previous_profile: AthleteProfile,
    updated_profile: AthleteProfile,
    previous_planning_state: PlanningState,
    updated_planning_state: PlanningState,
) -> ProfilePlanTransaction:
    transaction = ProfilePlanTransaction(
        phase="prepared",
        previous_profile=previous_profile,
        updated_profile=updated_profile,
        previous_planning_state=previous_planning_state,
        updated_planning_state=updated_planning_state,
    )
    _write_transaction(repo, transaction)
    return transaction


def advance_profile_plan_transaction(
    repo: RepositoryIO,
    transaction: ProfilePlanTransaction,
    *,
    phase: Literal["profile_written", "committed"],
) -> ProfilePlanTransaction:
    updated = transaction.model_copy(update={"phase": phase})
    _write_transaction(repo, updated)
    return updated
