"""Persistence boundary for the athlete-confirmed profile."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

from resilio.core.locking import OperationLockError
from resilio.core.paths import athlete_profile_path
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.profile_invalidation import (
    invalidated_state_for_profile_change,
)
from resilio.core.planning.profile_plan_transaction import (
    ProfilePlanTransactionError,
    advance_profile_plan_transaction,
    begin_profile_plan_transaction,
    clear_profile_plan_transaction,
    coordinated_plan_lock,
    recover_profile_plan_transaction,
    transaction_is_pending,
)
from resilio.core.planning.state_repository import (
    load_planning_aggregate_unlocked,
    persist_planning_state,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.profile import AthleteProfile
from resilio.schemas.repository import ReadOptions, RepoError


class ProfileRepository:
    def __init__(self, repo: RepositoryIO):
        self._repo = repo

    def _load_unlocked(
        self,
        *,
        allow_missing: bool = False,
    ) -> AthleteProfile | None:
        result = self._repo.read_yaml(
            athlete_profile_path(),
            AthleteProfile,
            ReadOptions(allow_missing=allow_missing),
        )
        if isinstance(result, RepoError):
            raise ValueError(f"Invalid athlete profile: {result}")
        return result

    def load(self, *, allow_missing: bool = False) -> AthleteProfile | None:
        """Read the profile while excluding coordinated profile/plan writes."""
        try:
            with coordinated_plan_lock(self._repo, "read_athlete_profile"):
                return self._load_unlocked(allow_missing=allow_missing)
        except OperationLockError as exc:
            raise OSError(
                "Athlete profile is temporarily unavailable during a "
                "coordinated profile/plan transition"
            ) from exc

    def _save_unlocked(self, profile: AthleteProfile) -> None:
        result = self._repo.write_yaml(athlete_profile_path(), profile)
        if isinstance(result, RepoError):
            raise OSError(f"Failed to save athlete profile: {result}")

    def create(self, profile: AthleteProfile) -> AthleteProfile:
        """Create the first profile atomically; never overwrite existing state."""
        try:
            with coordinated_plan_lock(self._repo, "create_athlete_profile"):
                if self._load_unlocked(allow_missing=True) is not None:
                    raise ValueError("Athlete profile already exists")
                self._save_unlocked(profile)
                return profile
        except OperationLockError as exc:
            raise OSError(f"Unable to create the athlete profile: {exc}") from exc

    def update(self, fields: dict[str, object]) -> AthleteProfile:
        unknown = set(fields) - set(AthleteProfile.model_fields)
        if unknown:
            raise ValueError(f"Unknown athlete profile fields: {sorted(unknown)}")
        try:
            with coordinated_plan_lock(self._repo, "update_athlete_profile"):
                profile = self._load_unlocked()
                if profile is None:
                    raise ValueError("Athlete profile does not exist")
                payload = profile.model_dump(mode="json")
                payload.update(fields)
                try:
                    updated = AthleteProfile.model_validate(payload)
                except ValidationError as exc:
                    raise ValueError(f"Invalid athlete profile update: {exc}") from exc
                try:
                    state = load_planning_aggregate_unlocked(
                        self._repo,
                        allow_missing=True,
                    )
                except PlanOperationError as exc:
                    raise OSError(f"Unable to validate the dependent training plan: {exc}") from exc
                replacement = invalidated_state_for_profile_change(
                    state,
                    previous_profile=profile,
                    updated_profile=updated,
                    invalidated_at_utc=datetime.now(timezone.utc),
                )
                if replacement == state:
                    self._save_unlocked(updated)
                    return updated
                assert state is not None
                assert replacement is not None
                transaction = begin_profile_plan_transaction(
                    self._repo,
                    previous_profile=profile,
                    updated_profile=updated,
                    previous_planning_state=state,
                    updated_planning_state=replacement,
                )
                try:
                    self._save_unlocked(updated)
                    transaction = advance_profile_plan_transaction(
                        self._repo,
                        transaction,
                        phase="profile_written",
                    )
                    try:
                        persist_planning_state(self._repo, replacement)
                    except PlanOperationError as exc:
                        recover_profile_plan_transaction(self._repo)
                        raise OSError(
                            "The dependent plan could not be invalidated; "
                            "the athlete profile update was rolled back"
                        ) from exc
                    transaction = advance_profile_plan_transaction(
                        self._repo,
                        transaction,
                        phase="committed",
                    )
                    clear_profile_plan_transaction(self._repo)
                except (OSError, ProfilePlanTransactionError):
                    if transaction_is_pending(self._repo):
                        recover_profile_plan_transaction(self._repo)
                    raise
        except OperationLockError as exc:
            raise OSError(f"Unable to update the athlete profile: {exc}") from exc
        return updated
