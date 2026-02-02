"""
sce sync - Import activities from Strava.

Syncs activities from Strava, normalizes data, calculates loads and metrics.
Idempotent - safe to run multiple times.
"""

from datetime import date, datetime, timedelta
from typing import Optional

import typer

from sports_coach_engine.api import sync_strava
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.strava import DEFAULT_SYNC_LOOKBACK_DAYS
from sports_coach_engine.schemas.activity import NormalizedActivity
from sports_coach_engine.schemas.repository import ReadOptions, RepoError


def _determine_sync_window(repo: RepositoryIO) -> int:
    """
    Determine optimal sync window based on existing data.

    Implements smart sync detection:
    - If no activities exist → 365 days (first-time sync)
    - If activities exist → days since latest activity + 1 (incremental with buffer)

    The 1-day buffer ensures we catch activities uploaded late to Strava.

    Args:
        repo: Repository instance for accessing activity files

    Returns:
        int: Number of days to look back
    """
    # Find latest activity date by scanning activity files
    activities_pattern = "data/activities/**/*.yaml"
    latest_date = None

    try:
        for file_path in repo.list_files(activities_pattern):
            # Quick parse: extract date from filename (faster than reading file)
            # Filename format: data/activities/YYYY-MM/YYYY-MM-DD_sport_duration.yaml
            filename = file_path.name
            if filename.startswith('.'):
                continue  # Skip hidden files like .DS_Store

            try:
                # Extract date from filename (first 10 chars: YYYY-MM-DD)
                date_str = filename[:10]
                activity_date = date.fromisoformat(date_str)

                if latest_date is None or activity_date > latest_date:
                    latest_date = activity_date
            except (ValueError, IndexError):
                # If filename doesn't match expected format, skip it
                # (Could be a malformed file or non-activity file)
                continue

    except Exception:
        # If anything goes wrong during scan, fall back to first-time sync
        return DEFAULT_SYNC_LOOKBACK_DAYS

    # First-time sync: no activities exist
    if latest_date is None:
        return DEFAULT_SYNC_LOOKBACK_DAYS  # 365 days

    # Incremental sync: calculate days since latest + 1-day buffer
    # Buffer catches activities uploaded late to Strava
    days_since = (date.today() - latest_date).days
    return max(days_since + 1, 1)  # Minimum 1 day


def sync_command(
    ctx: typer.Context,
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Sync activities since (e.g., '14d' for 14 days, or '2026-01-01')",
    ),
) -> None:
    """Import activities from Strava and update metrics.

    Fetches activities from Strava, normalizes sport types, calculates RPE estimates,
    computes training loads, and updates daily/weekly metrics.

    By default, uses smart sync detection:
    - First-time sync: 365 days (establishes CTL baseline)
    - Subsequent syncs: Incremental (only new activities since last sync)

    Use --since to override smart detection with explicit window.

    Examples:
        sce sync                    # Smart sync (365 days first-time, incremental after)
        sce sync --since 2026-01-01 # Sync since specific date
        sce sync --since 7d         # Sync last 7 days (explicit override)

    Note: The sync is "greedy" - it fetches newest activities first and stops
    if the Strava API rate limit is hit. This ensures you always get the
    most recent data even if history is truncated.
    """
    # Parse since parameter
    since_dt: Optional[datetime] = None
    if since:
        # Explicit --since: use provided value
        since_dt = _parse_since_param(since)
        typer.echo(f"Syncing activities since {since_dt.date()}...")
    else:
        # Smart detection: first-time vs. incremental
        repo = RepositoryIO()
        lookback_days = _determine_sync_window(repo)
        since_dt = datetime.now() - timedelta(days=lookback_days)

        if lookback_days == DEFAULT_SYNC_LOOKBACK_DAYS:
            typer.echo(
                "First-time sync: fetching last 365 days to establish training baseline..."
            )
        else:
            typer.echo(
                f"Incremental sync: fetching activities since {since_dt.date()} "
                f"({lookback_days} days)..."
            )

    # Call API
    result = sync_strava(since=since_dt)

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=_build_success_message(result),
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


def _parse_since_param(since: str) -> datetime:
    """Parse --since parameter into datetime.

    Supports:
    - Relative: '14d', '30d' (days ago)
    - Absolute: '2026-01-01', '2026-01-01T00:00:00'

    Args:
        since: Since parameter string

    Returns:
        Parsed datetime

    Raises:
        ValueError: If format is invalid
    """
    # Relative format: '14d'
    if since.endswith('d'):
        try:
            days = int(since[:-1])
            return datetime.now() - timedelta(days=days)
        except ValueError:
            raise ValueError(f"Invalid days format: {since}. Use '14d' for 14 days.")

    # Absolute format: ISO 8601
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        raise ValueError(
            f"Invalid date format: {since}. Use 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS'."
        )


def _build_success_message(result: any) -> str:
    """Build human-readable success message from sync result.

    Args:
        result: SyncResult from API

    Returns:
        Human-readable message
    """
    if not hasattr(result, 'activities_new'):
        return "Sync completed"

    msg = f"Synced {result.activities_new} new activities from Strava."

    # Add rate limit tip if hit
    if result.errors and any("Rate Limit" in str(e) for e in result.errors):
        msg += (
            "\n\nStrava rate limit hit. Data saved successfully. "
            "Wait 15 minutes and run 'sce sync' again to continue."
        )

    return msg
