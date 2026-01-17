"""Date utilities for training plan generation.

Ensures all training plans follow Monday-Sunday week structure.
"""
from datetime import date, timedelta
from typing import Tuple


def get_next_monday(from_date: date = None) -> date:
    """
    Get the next Monday from a given date.

    If from_date is already Monday, returns the following Monday (7 days ahead).
    Otherwise returns the upcoming Monday.

    Args:
        from_date: Starting date (defaults to today)

    Returns:
        Next Monday as date object

    Examples:
        >>> get_next_monday(date(2026, 1, 17))  # Saturday
        datetime.date(2026, 1, 19)
        >>> get_next_monday(date(2026, 1, 19))  # Monday
        datetime.date(2026, 1, 26)
    """
    if from_date is None:
        from_date = date.today()

    # Calculate days until next Monday
    days_until_monday = (7 - from_date.weekday()) % 7

    # If today is Monday (days_until_monday == 0), return next Monday
    if days_until_monday == 0:
        days_until_monday = 7

    return from_date + timedelta(days=days_until_monday)


def get_week_boundaries(week_start: date) -> Tuple[date, date]:
    """
    Get Monday-Sunday boundaries for a week.

    Args:
        week_start: Week start date (must be Monday)

    Returns:
        Tuple of (week_start, week_end) where week_end is Sunday

    Raises:
        ValueError: If week_start is not a Monday

    Examples:
        >>> get_week_boundaries(date(2026, 1, 19))  # Monday
        (datetime.date(2026, 1, 19), datetime.date(2026, 1, 25))
    """
    if week_start.weekday() != 0:
        raise ValueError(
            f"week_start must be Monday, got {week_start.strftime('%A')} ({week_start})"
        )

    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def format_week_range(week_start: date) -> str:
    """
    Format week as 'Mon Jan 19 - Sun Jan 25'.

    Args:
        week_start: Week start date

    Returns:
        Formatted week range string

    Examples:
        >>> format_week_range(date(2026, 1, 19))
        'Mon Jan 19 - Sun Jan 25'
    """
    week_end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%a %b %d')} - {week_end.strftime('%a %b %d')}"


def validate_week_start(week_start: date) -> bool:
    """
    Validate that a date is a Monday.

    Args:
        week_start: Date to validate

    Returns:
        True if Monday, False otherwise
    """
    return week_start.weekday() == 0
