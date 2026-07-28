"""Metrics refresh and deterministic archive-wide recomputation."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from resilio.core.metrics import (
    MetricsCalculationError,
    _read_activities_for_date,
    compute_daily_metrics,
    compute_weekly_summary,
)
from resilio.core.paths import weekly_metrics_summary_path
from resilio.core.repository import RepositoryIO
from resilio.core.workflow_types import MetricsRefreshResult, WorkflowError

logger = logging.getLogger(__name__)


def run_metrics_refresh(
    repo: RepositoryIO,
    target_date: Optional[date] = None,
) -> MetricsRefreshResult:
    target = target_date or date.today()
    try:
        metrics = compute_daily_metrics(target, repo)
    except Exception as exc:
        raise WorkflowError(f"Metrics refresh failed for {target}: {exc}") from exc
    return MetricsRefreshResult(
        success=True,
        metrics=metrics,
        date_refreshed=target,
    )


def _get_earliest_activity_date(repo: RepositoryIO) -> Optional[date]:
    earliest: Optional[date] = None
    for file_path in repo.list_files("data/activities/**/*.yaml"):
        from resilio.schemas.activity import CanonicalActivity

        activity = repo.read_yaml(file_path, CanonicalActivity)
        if (
            isinstance(activity, CanonicalActivity)
            and activity.status == "active"
        ):
            if earliest is None or activity.date < earliest:
                earliest = activity.date
    return earliest


def recompute_all_metrics(
    repo: RepositoryIO,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    start = start_date or _get_earliest_activity_date(repo)
    if start is None:
        raise MetricsCalculationError("No activities found")
    end = end_date or date.today()
    if start > end:
        raise MetricsCalculationError("Metrics start date cannot be after end date")

    metrics_computed = 0
    rest_days_filled = 0
    current = start
    while current <= end:
        if not _read_activities_for_date(current, repo):
            rest_days_filled += 1
        compute_daily_metrics(current, repo)
        metrics_computed += 1
        current += timedelta(days=1)

    week_start = end - timedelta(days=end.weekday())
    summary = compute_weekly_summary(week_start, repo)
    error = repo.write_yaml(weekly_metrics_summary_path(), summary)
    if error is not None:
        raise MetricsCalculationError(f"Failed to persist weekly summary: {error}")
    logger.info(
        "[Metrics] Computed %s days (%s rest days)",
        metrics_computed,
        rest_days_filled,
    )
    return {
        "start_date": start,
        "end_date": end,
        "metrics_computed": metrics_computed,
        "rest_days_filled": rest_days_filled,
    }
