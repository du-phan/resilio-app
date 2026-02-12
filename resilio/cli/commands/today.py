"""
sce today - Get today's recommended workout.

Returns the workout recommendation for today (or specified date) with full coaching
context including metrics, triggers, and rationale.
"""

from datetime import datetime, date
from typing import Optional

import typer

from sports_coach_engine.api import get_todays_workout
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, output_json


def today_command(
    ctx: typer.Context,
    date: Optional[str] = typer.Option(
        None,
        "--date",
        help="Date to get workout for (YYYY-MM-DD), defaults to today",
    ),
) -> None:
    """Get today's workout recommendation with coaching context.

    Returns:
    - Workout details: type, duration, target RPE, pace zones, HR zones
    - Current metrics: CTL, TSB, ACWR, readiness
    - Adaptation triggers: Warnings about elevated load, low readiness, etc.
    - Rationale: Why this workout for today

    This gives Claude Code everything needed to provide personalized coaching.

    Examples:
        sce today                    # Today's workout
        sce today --date 2026-01-20  # Workout for specific date
    """
    # Parse date if provided
    target_date: Optional[date] = None
    if date:
        try:
            # Convert to date object (not datetime) to match workout schema
            target_date = datetime.fromisoformat(date).date()
        except ValueError:
            # Build error envelope
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid date format: {date}. Use YYYY-MM-DD.",
            )

            output_json(envelope)
            raise typer.Exit(code=5)  # Validation error

    # Call API
    result = get_todays_workout(target_date=target_date)

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=_build_success_message(result, date),
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


def _build_success_message(result: any, date: Optional[str]) -> str:
    """Build human-readable success message.

    Args:
        result: Workout result from API
        date: Date string if specified

    Returns:
        Human-readable message
    """
    date_str = f" for {date}" if date else " for today"

    # Try to extract workout type
    if hasattr(result, 'workout_type'):
        workout_type = result.workout_type
        return f"Workout{date_str}: {workout_type}"
    elif hasattr(result, 'workout') and hasattr(result.workout, 'type'):
        workout_type = result.workout.type
        return f"Workout{date_str}: {workout_type}"

    # Fallback
    return f"Retrieved workout{date_str}"
