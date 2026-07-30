"""Presentation-neutral access to the typed weekly coaching context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from resilio.core.coaching_context import (
    build_coach_history,
    build_week_planning_context,
    build_weekly_coach_context,
)
from resilio.core.planning.service import PlanOperationError
from resilio.core.repository import RepositoryIO
from resilio.schemas.coaching import (
    CoachHistoryContext,
    WeeklyCoachContext,
    WeekPlanningContext,
)


@dataclass(frozen=True)
class CoachingContextError:
    error_type: str
    message: str


def get_weekly_coach_context(
    *,
    week_start: date,
    as_of_date: date,
) -> WeeklyCoachContext | CoachingContextError:
    """Return a read-only context or an explicit validation/data error."""
    try:
        return build_weekly_coach_context(
            RepositoryIO(),
            week_start=week_start,
            as_of_date=as_of_date,
        )
    except ValueError as exc:
        return CoachingContextError(
            error_type="validation",
            message=str(exc),
        )
    except OSError as exc:
        return CoachingContextError(
            error_type="validation",
            message=f"Coaching state could not be read: {exc}",
        )


def get_coach_history(
    *,
    as_of_date: date,
    week_count: int,
) -> CoachHistoryContext | CoachingContextError:
    try:
        return build_coach_history(
            RepositoryIO(),
            as_of_date=as_of_date,
            week_count=week_count,
        )
    except (OSError, ValueError, PlanOperationError) as exc:
        return CoachingContextError("validation", str(exc))


def get_week_planning_context(
    *,
    week_number: int,
    evidence_as_of_date: date,
    history_week_count: int,
) -> WeekPlanningContext | CoachingContextError:
    try:
        return build_week_planning_context(
            RepositoryIO(),
            week_number=week_number,
            evidence_as_of_date=evidence_as_of_date,
            history_week_count=history_week_count,
        )
    except (OSError, ValueError) as exc:
        return CoachingContextError("validation", str(exc))
