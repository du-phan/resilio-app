"""Deterministic date windows and saturation-safe listing."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol

from resilio.integrations.intervals_icu.dto import (
    ActivitySummaryDTO,
    HiddenActivityDTO,
)

ActivityRow = ActivitySummaryDTO | HiddenActivityDTO


class ActivityLister(Protocol):
    def list_activities(
        self,
        oldest: date,
        newest: date,
        *,
        athlete_id: str | None = None,
        limit: int = 1000,
    ) -> list[ActivityRow]:
        ...


class SaturatedActivityWindowError(RuntimeError):
    pass


def enumerate_windows(oldest: date, newest: date, window_days: int) -> list[tuple[date, date]]:
    if oldest > newest:
        raise ValueError("oldest cannot be after newest")
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    result: list[tuple[date, date]] = []
    start = oldest
    while start <= newest:
        end = min(start + timedelta(days=window_days - 1), newest)
        result.append((start, end))
        start = end + timedelta(days=1)
    return result


def fetch_complete_window(
    client: ActivityLister,
    oldest: date,
    newest: date,
    *,
    athlete_id: str,
    limit: int,
) -> list[ActivityRow]:
    """Fetch a complete window, recursively bisecting saturated date ranges."""
    rows = client.list_activities(
        oldest,
        newest,
        athlete_id=athlete_id,
        limit=limit,
    )
    if len(rows) < limit:
        return rows
    if oldest == newest:
        raise SaturatedActivityWindowError(
            f"Single-day activity window saturated at limit={limit}: {oldest}"
        )
    midpoint = oldest + timedelta(days=(newest - oldest).days // 2)
    left = fetch_complete_window(
        client,
        oldest,
        midpoint,
        athlete_id=athlete_id,
        limit=limit,
    )
    right = fetch_complete_window(
        client,
        midpoint + timedelta(days=1),
        newest,
        athlete_id=athlete_id,
        limit=limit,
    )
    # The API returns descending rows; preserve that documented ordering.
    return sorted(
        [*left, *right],
        key=lambda row: (
            row.start_date_local.isoformat()
            if hasattr(row.start_date_local, "isoformat")
            else str(row.start_date_local)
        ),
        reverse=True,
    )
