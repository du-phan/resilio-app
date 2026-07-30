"""Durable source-coverage windows, gaps, and declared dispositions."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from resilio.schemas.sync import (
    ActivityCoverageWindow,
    ActivitySyncState,
    SourceCoverageExclusion,
    SourceCoverageGap,
)


def merge_source_coverage_exclusions(
    *,
    previous: list[SourceCoverageExclusion],
    current: list[SourceCoverageExclusion],
    window_start: date,
    window_end: date,
    replace_window: bool,
) -> list[SourceCoverageExclusion]:
    outside_window = [
        item for item in previous if not window_start <= item.local_date <= window_end
    ]
    retained = outside_window if replace_window else previous
    merged = {
        (
            item.external_activity_id_sha256,
            item.reason,
        ): item
        for item in [*retained, *current]
    }
    return sorted(
        merged.values(),
        key=lambda item: (
            item.local_date,
            item.external_activity_id_sha256,
            item.reason,
        ),
    )


def merge_coverage_windows(
    windows: list[ActivityCoverageWindow],
) -> list[ActivityCoverageWindow]:
    merged: list[ActivityCoverageWindow] = []
    for window in sorted(windows, key=lambda item: item.start_date):
        if not merged or window.start_date > merged[-1].end_date + timedelta(days=1):
            merged.append(window)
            continue
        previous = merged[-1]
        merged[-1] = ActivityCoverageWindow(
            start_date=previous.start_date,
            end_date=max(previous.end_date, window.end_date),
        )
    return merged


def merge_coverage_gaps(
    gaps: list[SourceCoverageGap],
) -> list[SourceCoverageGap]:
    windows = merge_coverage_windows(
        [
            ActivityCoverageWindow(
                start_date=gap.start_date,
                end_date=gap.end_date,
            )
            for gap in gaps
        ]
    )
    return [
        SourceCoverageGap(
            start_date=window.start_date,
            end_date=window.end_date,
            reason="partial_sync_attempt",
        )
        for window in windows
    ]


def clear_coverage_gaps(
    gaps: list[SourceCoverageGap],
    *,
    window_start: date,
    window_end: date,
) -> list[SourceCoverageGap]:
    remaining: list[SourceCoverageGap] = []
    for gap in gaps:
        if gap.end_date < window_start or gap.start_date > window_end:
            remaining.append(gap)
            continue
        if gap.start_date < window_start:
            remaining.append(
                SourceCoverageGap(
                    start_date=gap.start_date,
                    end_date=window_start - timedelta(days=1),
                    reason=gap.reason,
                )
            )
        if gap.end_date > window_end:
            remaining.append(
                SourceCoverageGap(
                    start_date=window_end + timedelta(days=1),
                    end_date=gap.end_date,
                    reason=gap.reason,
                )
            )
    return remaining


def record_sync_coverage(
    state: ActivitySyncState,
    *,
    window_start: date,
    window_end: date,
    current_exclusions: list[SourceCoverageExclusion],
    partial: bool,
    completed_at_utc: datetime,
    full_reconciliation: bool,
) -> None:
    """Update source-evidence state for one attempted sync window."""
    state.source_coverage_exclusions = merge_source_coverage_exclusions(
        previous=state.source_coverage_exclusions,
        current=current_exclusions,
        window_start=window_start,
        window_end=window_end,
        replace_window=not partial,
    )
    if partial:
        state.source_coverage_gaps = merge_coverage_gaps(
            [
                *state.source_coverage_gaps,
                SourceCoverageGap(
                    start_date=window_start,
                    end_date=window_end,
                    reason="partial_sync_attempt",
                ),
            ]
        )
        return

    state.last_successful_incremental_at_utc = completed_at_utc
    state.complete_activity_windows = merge_coverage_windows(
        [
            *state.complete_activity_windows,
            ActivityCoverageWindow(
                start_date=window_start,
                end_date=window_end,
            ),
        ]
    )
    state.source_coverage_gaps = clear_coverage_gaps(
        state.source_coverage_gaps,
        window_start=window_start,
        window_end=window_end,
    )
    if full_reconciliation:
        state.last_full_reconciliation_at_utc = completed_at_utc
