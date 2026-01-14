"""
sce goal - Manage race goals.

Set a race goal and automatically regenerate training plan.
"""

from datetime import datetime
from typing import Optional

import typer

from sports_coach_engine.api import set_goal
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, output_json


def goal_set_command(
    ctx: typer.Context,
    race_type: str = typer.Option(
        ...,
        "--type",
        help="Race type: 5k, 10k, half_marathon, or marathon",
    ),
    target_date: str = typer.Option(
        ...,
        "--date",
        help="Race date (YYYY-MM-DD)",
    ),
    target_time: Optional[str] = typer.Option(
        None,
        "--time",
        help="Target finish time (HH:MM:SS), optional",
    ),
) -> None:
    """Set a new race goal and regenerate training plan.

    Sets a race goal (5K, 10K, half marathon, or marathon) and automatically
    regenerates the training plan to prepare for that goal.

    Valid race types:
    - 5k
    - 10k
    - half_marathon
    - marathon

    Examples:
        sce goal set --type 10k --date 2026-06-01
        sce goal set --type half_marathon --date 2026-04-15 --time 01:45:00
        sce goal set --type marathon --date 2026-10-20 --time 03:30:00
    """
    # Parse target_date
    try:
        date_obj = datetime.fromisoformat(target_date).date()
    except ValueError:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid date format: {target_date}. Use YYYY-MM-DD.",
        )
        output_json(envelope)
        raise typer.Exit(code=5)  # Validation error

    # Validate race_type
    valid_race_types = ["5k", "10k", "half_marathon", "marathon"]
    if race_type not in valid_race_types:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid race type: {race_type}. Valid types: {', '.join(valid_race_types)}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)  # Validation error

    # Validate target_time format if provided
    if target_time:
        # Expected format: HH:MM:SS
        parts = target_time.split(":")
        if len(parts) != 3:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid time format: {target_time}. Use HH:MM:SS (e.g., 01:45:00)",
            )
            output_json(envelope)
            raise typer.Exit(code=5)  # Validation error

        try:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                raise ValueError
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid time values: {target_time}. Use valid HH:MM:SS.",
            )
            output_json(envelope)
            raise typer.Exit(code=5)  # Validation error

    # Call API
    result = set_goal(
        race_type=race_type,
        target_date=date_obj,
        target_time=target_time,
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Set goal: {race_type} on {target_date}"
        + (f" (target: {target_time})" if target_time else ""),
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)
