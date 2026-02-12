"""
Sync API - Strava synchronization and activity logging.

Provides functions for Claude Code to import activities from Strava
or log manual activities.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Union

from sports_coach_engine.core.config import ConfigError, load_config
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.strava import StravaRateLimitError
from sports_coach_engine.core.workflows import (
    WorkflowError,
    run_manual_activity_workflow,
    run_sync_workflow,
)
from sports_coach_engine.schemas.activity import NormalizedActivity
from sports_coach_engine.schemas.sync import SyncReport


@dataclass
class SyncError:
    """Error result from sync operations."""

    error_type: str  # "auth", "rate_limit", "network", "partial", "lock", "unknown"
    message: str
    retry_after: Optional[int] = None  # Seconds to wait for rate limits


def sync_strava(
    since: Optional[datetime] = None,
) -> Union[SyncReport, SyncError]:
    """
    Import activities from Strava and return canonical sync report.
    """
    repo = RepositoryIO()
    config_result = load_config(repo.repo_root)
    if isinstance(config_result, ConfigError):
        return SyncError(
            error_type="config",
            message=f"Configuration error: {config_result.message}",
        )

    config = config_result

    try:
        return run_sync_workflow(repo, config, since=since)
    except StravaRateLimitError as exc:
        return SyncError(
            error_type="rate_limit",
            message="Rate limit exceeded. Please wait and try again.",
            retry_after=exc.retry_after,
        )
    except WorkflowError as exc:
        return SyncError(
            error_type=_classify_workflow_error(exc),
            message=str(exc),
        )
    except Exception as exc:
        return SyncError(
            error_type="unknown",
            message=f"Unexpected error: {str(exc)}",
        )


def log_activity(
    sport_type: str,
    duration_minutes: int,
    rpe: Optional[int] = None,
    notes: Optional[str] = None,
    activity_date: Optional[date] = None,
    distance_km: Optional[float] = None,
) -> Union[NormalizedActivity, SyncError]:
    """
    Log a manual activity (not from Strava).
    """
    repo = RepositoryIO()
    if activity_date is None:
        activity_date = date.today()

    try:
        result = run_manual_activity_workflow(
            repo=repo,
            sport_type=sport_type,
            duration_minutes=duration_minutes,
            rpe=rpe,
            notes=notes,
            activity_date=activity_date,
            distance_km=distance_km,
        )
    except WorkflowError as exc:
        return SyncError(
            error_type=_classify_workflow_error(exc),
            message=str(exc),
        )
    except Exception as exc:
        return SyncError(
            error_type="unknown",
            message=f"Unexpected error: {str(exc)}",
        )

    if not result.success or result.activity is None:
        error_msg = "; ".join(result.warnings) if result.warnings else "Activity logging failed"
        return SyncError(
            error_type="validation",
            message=error_msg,
        )
    return result.activity


def _classify_workflow_error(error: WorkflowError) -> str:
    """Classify WorkflowError into API error type."""
    error_msg = str(error).lower()

    if "strava" in error_msg or "auth" in error_msg or "token" in error_msg:
        return "auth"
    if "rate" in error_msg or "limit" in error_msg:
        return "rate_limit"
    if "network" in error_msg or "connection" in error_msg:
        return "network"
    if "lock" in error_msg:
        return "lock"
    return "unknown"
