"""
sce sync - Import activities from Strava.

Syncs activities from Strava, normalizes data, calculates loads and metrics.
Idempotent - safe to run multiple times.
"""

from datetime import datetime, timedelta
from typing import Optional

import typer

from sports_coach_engine.api import sync_strava
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json
from sports_coach_engine.core.strava import DEFAULT_SYNC_LOOKBACK_DAYS


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

    By default, syncs the last year (365 days) to capture full seasonal training patterns.
    Use --since to specify a custom window.

    Examples:
        sce sync                    # Sync last year (365 days)
        sce sync --since 2026-01-01 # Sync since specific date
        sce sync --since 14d        # Sync last 14 days (recent activities only)

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
        # Default: use 365-day window
        # Note: DEFAULT_SYNC_LOOKBACK_DAYS is imported from core.strava
        since_dt = datetime.now() - timedelta(days=DEFAULT_SYNC_LOOKBACK_DAYS)
        typer.echo(
            f"Syncing last {DEFAULT_SYNC_LOOKBACK_DAYS} days of history (default). "
            f"Use --since to change."
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
        msg += "\n\nTIP: Strava rate limit hit. I've saved everything fetched so far. "
        msg += "Wait ~15 minutes and sync again to continue backwards."
    
    return msg
