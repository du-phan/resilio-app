"""
sce week - Get weekly training summary.

Shows planned workouts, completed activities, metrics, and overall week status.
"""

import typer

from sports_coach_engine.api import get_weekly_status
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json


def week_command(ctx: typer.Context) -> None:
    """Get weekly training summary with activities and metrics.

    Returns:
    - Week start/end dates
    - Planned workouts vs completed activities
    - Total training load for the week
    - Current metrics (CTL, TSB, ACWR, readiness)
    - Week-over-week changes

    This gives Claude Code a complete picture of the week for coaching.
    """
    # Call API
    result = get_weekly_status()

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


def _build_success_message(result: any) -> str:
    """Build human-readable success message.

    Args:
        result: WeeklyStatus from API

    Returns:
        Human-readable message
    """
    # Try to extract week info
    if hasattr(result, 'week_start'):
        week_start = result.week_start
        return f"Weekly status for week starting {week_start}"

    # Fallback
    return "Retrieved weekly training summary"
