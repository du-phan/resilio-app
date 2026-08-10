"""Exact weekly application plus downstream synchronization outcome."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resilio.api.publication import PublicationError, reconcile_week_run_workouts
from resilio.core.planning.integrity import applied_running_workouts_sha256
from resilio.core.planning.service import (
    PlanOperationError,
    apply_approved_week,
    validate_week_application,
)
from resilio.core.planning.weekly_service import load_week_application
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.preferences import (
    load_run_synchronization_preferences,
)
from resilio.schemas.planning.applications import (
    AppliedWeekResult,
    RunSynchronizationError,
    WeekApplication,
)


@dataclass(frozen=True)
class WeekApplicationError:
    error_type: str
    message: str


def validate_week_file(path: Path) -> WeekApplication | WeekApplicationError:
    try:
        return validate_week_application(
            RepositoryIO(),
            path.expanduser().resolve(),
        )
    except PlanOperationError as exc:
        return WeekApplicationError("validation", str(exc))


def apply_week_file(path: Path) -> AppliedWeekResult | WeekApplicationError:
    """Commit approved bytes, then independently reconcile enabled run sync."""
    repo = RepositoryIO()
    try:
        application = load_week_application(path.expanduser().resolve())
        plan = apply_approved_week(repo, path)
    except PlanOperationError as exc:
        return WeekApplicationError("validation", str(exc))
    week = next(
        candidate for candidate in plan.weeks if candidate.week_number == application.week_number
    )
    common = {
        "plan_id": plan.id,
        "plan_revision_id": plan.plan_revision_id,
        "week_number": application.week_number,
        "applied_running_workouts_sha256": applied_running_workouts_sha256(week),
    }
    try:
        preferences = load_run_synchronization_preferences(repo)
    except (ValueError, OSError) as exc:
        return _failed_result(
            common,
            error_type="synchronization_preferences",
            message=str(exc),
        )
    if preferences.run_synchronization_mode == "disabled":
        return AppliedWeekResult.model_validate(
            {**common, "run_synchronization_status": "disabled"}
        )
    sync_result = reconcile_week_run_workouts(application.week_number)
    if isinstance(sync_result, PublicationError):
        return _failed_result(
            common,
            error_type=sync_result.error_type,
            message=sync_result.message,
        )
    if not sync_result.reconciliation_safe:
        sync_status = "blocked"
    elif sync_result.partial:
        return _failed_result(
            common,
            error_type="publication_partial",
            message="Local week applied, but one or more remote mutations failed",
            report=sync_result,
        )
    else:
        sync_status = "synchronized"
    return AppliedWeekResult.model_validate(
        {
            **common,
            "run_synchronization_status": sync_status,
            "run_synchronization_report": sync_result,
        }
    )


def _failed_result(
    common: dict[str, object],
    *,
    error_type: str,
    message: str,
    report: object | None = None,
) -> AppliedWeekResult:
    return AppliedWeekResult.model_validate(
        {
            **common,
            "run_synchronization_status": "failed",
            "run_synchronization_report": report,
            "run_synchronization_error": RunSynchronizationError(
                error_type=error_type,
                message=message,
            ),
        }
    )
