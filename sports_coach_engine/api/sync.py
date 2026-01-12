"""
Sync API - Strava synchronization and activity logging.

Provides functions for Claude Code to import activities from Strava
or log manual activities.
"""

from datetime import date, datetime
from typing import Optional, Any


def sync_strava(
    since: Optional[datetime] = None,
) -> Any:
    """
    Import activities from Strava.

    Handles:
    - Token refresh if needed
    - Activity deduplication
    - Normalization, RPE analysis, load calculation
    - Metrics recomputation
    - Memory extraction from notes

    Args:
        since: Fetch activities since this datetime. Defaults to last_sync_at.

    Returns:
        SyncResult on success containing:
        - activities_imported: List of new activities with enriched data
        - metrics_updated: Current metrics after sync
        - suggestions_generated: Any adaptation suggestions triggered
        - memories_extracted: Insights extracted from activity notes

        SyncError on failure containing:
        - error_type: "auth", "rate_limit", "network", "partial"
        - message: Human-readable error description
        - retry_after: Seconds to wait (for rate limits)

    Example:
        >>> result = sync_strava()
        >>> if isinstance(result, SyncError):
        ...     print(f"Sync failed: {result.message}")
        ... else:
        ...     print(f"Synced {len(result.activities_imported)} activities")
    """
    raise NotImplementedError("M1 sync workflow not implemented yet")


def log_activity(
    sport_type: str,
    duration_minutes: int,
    rpe: Optional[int] = None,
    notes: Optional[str] = None,
    activity_date: Optional[date] = None,
    distance_km: Optional[float] = None,
) -> Any:
    """
    Log a manual activity (not from Strava).

    Args:
        sport_type: Type of activity (e.g., "run", "climb", "cycle")
        duration_minutes: Duration in minutes
        rpe: Rate of perceived exertion (1-10). If None, estimated from notes.
        notes: Optional activity notes
        activity_date: Activity date. Defaults to today.
        distance_km: Distance in kilometers (for running)

    Returns:
        Activity with calculated loads and enriched data

    Example:
        >>> activity = log_activity(
        ...     sport_type="run",
        ...     duration_minutes=45,
        ...     rpe=6,
        ...     notes="Felt good, easy pace"
        ... )
    """
    raise NotImplementedError("M1 manual activity workflow not implemented yet")
