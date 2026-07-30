"""Deterministic athlete-local calendar-date resolution."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def athlete_local_date(
    training_timezone: str,
    *,
    now_utc: datetime | None = None,
) -> date:
    """Return the athlete-local date for one explicit or current UTC instant."""
    try:
        zone = ZoneInfo(training_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("training timezone is not recognized") from exc
    instant = now_utc or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    return instant.astimezone(zone).date()
