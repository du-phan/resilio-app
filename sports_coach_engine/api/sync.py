"""
Sync API - Strava synchronization and activity logging.

Provides functions for Claude Code to import activities from Strava
or log manual activities.
"""

from datetime import date, datetime
from typing import Optional, Union
from dataclasses import dataclass

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.repository import RepoError
from sports_coach_engine.core.config import load_config
from sports_coach_engine.core.workflows import (
    run_sync_workflow,
    run_manual_activity_workflow,
    WorkflowError,
)
from sports_coach_engine.core.logger import log_message, MessageRole
from sports_coach_engine.core.enrichment import enrich_metrics, interpret_load
from sports_coach_engine.schemas.enrichment import SyncSummary
from sports_coach_engine.schemas.activity import NormalizedActivity


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class SyncError:
    """Error result from sync operations."""

    error_type: str  # "auth", "rate_limit", "network", "partial", "lock", "unknown"
    message: str
    retry_after: Optional[int] = None  # Seconds to wait for rate limits
    activities_imported: int = 0
    activities_failed: int = 0


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def sync_strava(
    since: Optional[datetime] = None,
) -> Union[SyncSummary, SyncError]:
    """
    Import activities from Strava.

    Workflow:
    1. Load configuration and check Strava connection
    2. Call M1 run_sync_workflow() to orchestrate full pipeline:
       - M5: Fetch activities from Strava
       - M6: Normalize activities
       - M7: Analyze notes and RPE
       - M8: Calculate loads
       - M9: Recompute metrics
       - M11: Check for adaptation triggers
       - M13: Extract memories
    3. Enrich results via M12 for interpretable data
    4. Log operation via M14
    5. Return enriched summary

    Args:
        since: Fetch activities since this datetime. Defaults to last_sync_at
               from profile if not specified.

    Returns:
        SyncSummary on success containing:
        - activities_imported: Count of new activities
        - activities_skipped: Count of duplicates skipped
        - activities_failed: Count of activities that failed processing
        - activity_types: List of sport types imported
        - total_duration_minutes: Total training time
        - total_load_au: Total systemic load
        - metrics_before: Metrics before sync (if available)
        - metrics_after: Metrics after sync
        - metric_changes: List of significant metric changes
        - suggestions_generated: Count of new suggestions
        - suggestion_summaries: Brief descriptions of suggestions
        - has_errors: Whether any errors occurred
        - error_summaries: List of error messages

        SyncError on failure containing:
        - error_type: Category of error
        - message: Human-readable error description
        - retry_after: Seconds to wait (for rate limits)

    Example:
        >>> result = sync_strava()
        >>> if isinstance(result, SyncError):
        ...     print(f"Sync failed: {result.message}")
        ... else:
        ...     print(f"Synced {result.activities_imported} activities")
        ...     print(f"CTL changes: {result.metric_changes}")
    """
    # Initialize repository and config
    repo = RepositoryIO()
    config_result = load_config(repo.repo_root)
    if isinstance(config_result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Sync failed: config error - {str(config_result)}",
        )
        return SyncError(
            error_type="config",
            message=f"Configuration error: {str(config_result)}",
        )

    config = config_result

    # Log user request
    log_message(
        repo,
        MessageRole.USER,
        f"sync_strava(since={since})",
    )

    # Call M1 workflow
    try:
        result = run_sync_workflow(repo, config, since=since)
    except WorkflowError as e:
        error_type = _classify_workflow_error(e)
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Sync workflow failed: {error_type} - {str(e)}",
        )
        return SyncError(
            error_type=error_type,
            message=str(e),
        )
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Sync workflow failed: unknown error - {str(e)}",
        )
        return SyncError(
            error_type="unknown",
            message=f"Unexpected error: {str(e)}",
        )

    # Handle workflow failure
    if not result.success:
        error_msg = "; ".join(result.warnings) if result.warnings else "Sync failed"
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Sync completed with errors: {error_msg}",
        )
        return SyncError(
            error_type="partial" if result.partial_failure else "unknown",
            message=error_msg,
            activities_imported=len(result.activities_imported),
            activities_failed=result.activities_failed,
        )

    # Build enriched sync summary
    try:
        sync_summary = _build_sync_summary(repo, result)
    except Exception as e:
        # Enrichment failure shouldn't block returning the result
        # Fall back to basic summary
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Warning: enrichment failed, returning basic summary: {str(e)}",
        )
        sync_summary = _build_basic_sync_summary(result)

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Synced {sync_summary.activities_imported} activities, "
        f"{sync_summary.activities_failed} failed, "
        f"{sync_summary.suggestions_generated} suggestions generated",
    )

    return sync_summary


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

    Workflow:
    1. Create RawActivity from inputs
    2. Call M1 run_manual_activity_workflow():
       - M6: Normalize activity
       - M7: Analyze notes and RPE
       - M8: Calculate loads
       - M9: Update metrics
    3. Log operation via M14
    4. Return normalized activity

    Args:
        sport_type: Type of activity (e.g., "run", "climb", "cycle")
        duration_minutes: Duration in minutes
        rpe: Rate of perceived exertion (1-10). If None, estimated from notes
             or defaults to moderate effort.
        notes: Optional activity notes
        activity_date: Activity date. Defaults to today.
        distance_km: Distance in kilometers (for running/cycling)

    Returns:
        NormalizedActivity with calculated loads and enriched data

        SyncError on failure containing error details

    Example:
        >>> activity = log_activity(
        ...     sport_type="run",
        ...     duration_minutes=45,
        ...     rpe=6,
        ...     notes="Felt good, easy pace"
        ... )
        >>> if isinstance(activity, SyncError):
        ...     print(f"Failed to log activity: {activity.message}")
        ... else:
        ...     print(f"Logged {activity.sport_type}: {activity.calculated.systemic_load_au} AU")
    """
    # Initialize repository
    repo = RepositoryIO()

    # Default activity date to today
    if activity_date is None:
        activity_date = date.today()

    # Log user request
    log_message(
        repo,
        MessageRole.USER,
        f"log_activity(sport_type={sport_type}, duration={duration_minutes}min, "
        f"rpe={rpe}, date={activity_date})",
    )

    # Call M1 workflow
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
    except WorkflowError as e:
        error_type = _classify_workflow_error(e)
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Manual activity workflow failed: {error_type} - {str(e)}",
        )
        return SyncError(
            error_type=error_type,
            message=str(e),
        )
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Manual activity workflow failed: unknown error - {str(e)}",
        )
        return SyncError(
            error_type="unknown",
            message=f"Unexpected error: {str(e)}",
        )

    # Handle workflow failure
    if not result.success or result.activity is None:
        error_msg = "; ".join(result.warnings) if result.warnings else "Activity logging failed"
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Activity logging failed: {error_msg}",
        )
        return SyncError(
            error_type="validation",
            message=error_msg,
        )

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Logged {result.activity.sport_type}: "
        f"{result.activity.calculated.systemic_load_au:.0f} AU systemic, "
        f"{result.activity.calculated.lower_body_load_au:.0f} AU lower-body",
    )

    return result.activity


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _classify_workflow_error(error: WorkflowError) -> str:
    """Classify WorkflowError into API error type."""
    error_msg = str(error).lower()

    if "strava" in error_msg or "auth" in error_msg or "token" in error_msg:
        return "auth"
    elif "rate" in error_msg or "limit" in error_msg:
        return "rate_limit"
    elif "network" in error_msg or "connection" in error_msg:
        return "network"
    elif "lock" in error_msg:
        return "lock"
    else:
        return "unknown"


def _build_sync_summary(repo: RepositoryIO, result) -> SyncSummary:
    """Build enriched SyncSummary from workflow result."""
    # Extract activity types
    activity_types = list(set(a.sport_type for a in result.activities_imported))

    # Calculate totals
    total_duration = sum(a.duration_minutes for a in result.activities_imported)
    total_load = sum(
        a.calculated.systemic_load_au if a.calculated else 0.0
        for a in result.activities_imported
    )

    # Enrich metrics (after sync)
    metrics_after = None
    if result.metrics_updated:
        metrics_after = enrich_metrics(result.metrics_updated, repo)

    # Calculate metric changes
    metric_changes = []
    if metrics_after:
        # Extract key changes (simplified for v0)
        metric_changes.append(f"CTL: {metrics_after.ctl.formatted_value}")
        metric_changes.append(f"TSB: {metrics_after.tsb.formatted_value}")
        if metrics_after.acwr:
            metric_changes.append(f"ACWR: {metrics_after.acwr.formatted_value}")

    # Build suggestion summaries
    suggestion_summaries = []
    for suggestion in result.suggestions_generated:
        # Simplified summary - M12 has full suggestion enrichment
        suggestion_summaries.append(f"Check adaptation for {suggestion.get('date', 'workout')}")

    # Build error summaries
    error_summaries = result.warnings if result.warnings else []

    return SyncSummary(
        activities_imported=len(result.activities_imported),
        activities_skipped=0,  # Would come from workflow if tracked
        activities_failed=result.activities_failed,
        activity_types=activity_types,
        total_duration_minutes=total_duration,
        total_load_au=total_load,
        profile_fields_updated=result.profile_fields_updated,
        metrics_before=None,  # Would require reading metrics before sync
        metrics_after=metrics_after,
        metric_changes=metric_changes,
        suggestions_generated=len(result.suggestions_generated),
        suggestion_summaries=suggestion_summaries,
        has_errors=len(error_summaries) > 0,
        error_summaries=error_summaries,
    )


def _build_basic_sync_summary(result) -> SyncSummary:
    """Build basic SyncSummary when enrichment fails."""
    activity_types = list(set(a.sport_type for a in result.activities_imported))
    total_duration = sum(a.duration_minutes for a in result.activities_imported)
    total_load = sum(
        a.calculated.systemic_load_au if a.calculated else 0.0
        for a in result.activities_imported
    )

    return SyncSummary(
        activities_imported=len(result.activities_imported),
        activities_skipped=0,
        activities_failed=result.activities_failed,
        activity_types=activity_types,
        total_duration_minutes=total_duration,
        total_load_au=total_load,
        profile_fields_updated=result.profile_fields_updated,
        metrics_before=None,
        metrics_after=None,
        metric_changes=[],
        suggestions_generated=len(result.suggestions_generated),
        suggestion_summaries=[],
        has_errors=len(result.warnings) > 0,
        error_summaries=result.warnings,
    )
