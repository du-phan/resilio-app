"""
resilio dates - Date utilities for training plan generation.

Provides computational date verification to prevent manual calculation errors.
All training weeks follow Monday-Sunday structure.
"""

from datetime import date, datetime
from typing import Optional

import typer

from resilio.utils.dates import (
    get_next_monday,
    get_week_boundaries,
    format_week_range,
    validate_week_start,
)
from resilio.cli.output import (
    output_json,
    create_success_envelope,
    create_error_envelope,
)

# Create subcommand app
app = typer.Typer(help="Date utilities for training plans")

# Day name mapping for validation
DAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


def parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD date string.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        date object

    Raises:
        ValueError: If date string is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.") from e


@app.command(name="today")
def today_command() -> None:
    """Get today's date with day name and next Monday.

    Returns comprehensive date information for planning context.

    Examples:
        resilio dates today

    Output includes:
        - date: Today's date (YYYY-MM-DD)
        - day_name: Day of week (Monday, Tuesday, etc.)
        - day_number: ISO weekday (0=Monday, 6=Sunday)
        - next_monday: Date of next Monday
        - is_monday: Whether today is Monday
    """
    today = date.today()
    day_num = today.weekday()
    next_mon = get_next_monday(today)

    data = {
        "date": today.isoformat(),
        "day_name": DAY_NAMES[day_num],
        "day_number": day_num,
        "next_monday": next_mon.isoformat(),
        "is_monday": day_num == 0,
    }

    message = f"Today is {DAY_NAMES[day_num]}, {today.strftime('%B %d, %Y')}"
    envelope = create_success_envelope(message=message, data=data)
    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="next-monday")
def next_monday_command(
    from_date: Optional[str] = typer.Option(
        None,
        "--from-date",
        help="Start date (YYYY-MM-DD). Defaults to today."
    )
) -> None:
    """Get next Monday from a given date.

    If the starting date is already Monday, returns the following Monday (7 days ahead).
    Otherwise returns the upcoming Monday.

    Examples:
        resilio dates next-monday
        resilio dates next-monday --from-date 2026-01-17

    Output includes:
        - date: Next Monday (YYYY-MM-DD)
        - day_name: "Monday" (always)
        - formatted: Human-readable format (Mon Jan 19, 2026)
        - days_ahead: Number of days from starting date
    """
    try:
        # Parse starting date
        if from_date:
            start = parse_date(from_date)
        else:
            start = date.today()

        # Calculate next Monday
        next_mon = get_next_monday(start)
        days_ahead = (next_mon - start).days

        data = {
            "date": next_mon.isoformat(),
            "day_name": "Monday",
            "formatted": next_mon.strftime("%a %b %d, %Y"),
            "days_ahead": days_ahead,
        }

        if from_date:
            message = f"Next Monday from {from_date} is {next_mon.isoformat()}"
        else:
            message = f"Next Monday is {next_mon.isoformat()}"

        envelope = create_success_envelope(message=message, data=data)
        output_json(envelope)
        raise typer.Exit(code=0)

    except ValueError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=str(e),
            data={"from_date": from_date}
        )
        output_json(envelope)
        raise typer.Exit(code=5)


@app.command(name="week-boundaries")
def week_boundaries_command(
    start: str = typer.Option(
        ...,
        "--start",
        help="Week start date (YYYY-MM-DD). Must be Monday."
    )
) -> None:
    """Get Monday-Sunday boundaries for a week.

    Validates that the start date is Monday and returns the corresponding Sunday.

    Examples:
        resilio dates week-boundaries --start 2026-01-19

    Output includes:
        - start: Week start date (Monday)
        - end: Week end date (Sunday)
        - formatted: Human-readable range (Mon Jan 19 - Sun Jan 25)
        - duration_days: Always 7
    """
    try:
        # Parse and validate
        week_start = parse_date(start)
        week_start_date, week_end = get_week_boundaries(week_start)

        data = {
            "start": week_start_date.isoformat(),
            "end": week_end.isoformat(),
            "formatted": format_week_range(week_start_date),
            "duration_days": 7,
        }

        message = f"Week boundaries: {format_week_range(week_start_date)}"
        envelope = create_success_envelope(message=message, data=data)
        output_json(envelope)
        raise typer.Exit(code=0)

    except ValueError as e:
        # Check if it's a date parse error or week validation error
        try:
            parsed = parse_date(start)
            actual_day = DAY_NAMES[parsed.weekday()]
            error_msg = f"Week start must be Monday, got {actual_day} ({start})"
        except ValueError:
            error_msg = str(e)

        envelope = create_error_envelope(
            error_type="invalid_input",
            message=error_msg,
            data={"start": start}
        )
        output_json(envelope)
        raise typer.Exit(code=5)


@app.command(name="validate")
def validate_command(
    date_str: str = typer.Option(
        ...,
        "--date",
        help="Date to validate (YYYY-MM-DD)"
    ),
    must_be: str = typer.Option(
        "monday",
        "--must-be",
        help="Required day of week (monday, tuesday, ..., sunday)"
    )
) -> None:
    """Validate that a date is a specific day of week.

    Useful for verifying training plan dates before saving.

    Examples:
        resilio dates validate --date 2026-01-19 --must-be monday
        resilio dates validate --date 2026-01-25 --must-be sunday

    Output includes:
        - valid: True if date matches required day
        - date: Input date
        - day_name: Actual day of week
        - required_day: Expected day of week
    """
    try:
        # Parse date
        parsed = parse_date(date_str)
        actual_day_num = parsed.weekday()
        actual_day = DAY_NAMES[actual_day_num]

        # Parse required day
        must_be_lower = must_be.lower()
        day_name_to_num = {name.lower(): num for num, name in DAY_NAMES.items()}

        if must_be_lower not in day_name_to_num:
            raise ValueError(
                f"Invalid day name '{must_be}'. "
                f"Expected one of: {', '.join(day_name_to_num.keys())}"
            )

        required_day_num = day_name_to_num[must_be_lower]
        required_day = DAY_NAMES[required_day_num]
        is_valid = actual_day_num == required_day_num

        data = {
            "valid": is_valid,
            "date": date_str,
            "day_name": actual_day,
            "required_day": required_day,
        }

        if is_valid:
            message = f"{date_str} is {actual_day} ✓"
        else:
            message = f"{date_str} is {actual_day}, not {required_day} ✗"

        envelope = create_success_envelope(message=message, data=data)
        output_json(envelope)

        # Exit with code 0 even if validation failed (we successfully validated, result is in data)
        raise typer.Exit(code=0)

    except ValueError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=str(e),
            data={"date": date_str, "must_be": must_be}
        )
        output_json(envelope)
        raise typer.Exit(code=5)
