"""Derive plan invalidation caused by athlete-confirmed profile changes."""

from __future__ import annotations

from datetime import datetime

from resilio.core.planning.integrity import planning_profile_sha256
from resilio.schemas.approvals import PlanningState
from resilio.schemas.profile import AthleteProfile


def invalidated_state_for_profile_change(
    state: PlanningState | None,
    *,
    previous_profile: AthleteProfile,
    updated_profile: AthleteProfile,
    invalidated_at_utc: datetime,
) -> PlanningState | None:
    """Return state that fails closed when planning inputs have changed."""
    if planning_profile_sha256(previous_profile) == planning_profile_sha256(updated_profile):
        return state
    if state is None or state.current_plan is None:
        return state
    return state.model_copy(
        update={
            "pending_weekly_approval": None,
            "plan_invalidated_at_utc": invalidated_at_utc,
            "plan_invalidation_reason": ("Athlete-confirmed planning constraints or goal changed"),
        }
    )
