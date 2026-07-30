"""Week-scoped completeness of synchronized source evidence."""

from datetime import date
from typing import Literal

from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import read_sync_state
from resilio.schemas.coaching import SyncEvidenceCoverage


def build_sync_evidence_coverage(
    repo: RepositoryIO,
    *,
    requested_window_start: date,
    requested_window_end: date,
) -> SyncEvidenceCoverage:
    """Describe exact coverage without turning missing state into empty evidence."""
    try:
        state = read_sync_state(repo)
    except ValueError:
        return SyncEvidenceCoverage(
            status="unavailable",
            requested_window_start=requested_window_start,
            requested_window_end=requested_window_end,
            reason="activity_sync_state_invalid",
        )

    windows = state.complete_activity_windows
    covering_window = next(
        (
            window
            for window in windows
            if window.start_date <= requested_window_start
            and window.end_date >= requested_window_end
        ),
        None,
    )
    complete_start = covering_window.start_date if covering_window is not None else None
    complete_end = covering_window.end_date if covering_window is not None else None
    last_success = state.last_successful_incremental_at_utc
    if not windows or last_success is None:
        return SyncEvidenceCoverage(
            status="unavailable",
            requested_window_start=requested_window_start,
            requested_window_end=requested_window_end,
            complete_window_start=complete_start,
            complete_window_end=complete_end,
            last_successful_sync_at_utc=last_success,
            reason="no_complete_activity_sync_window",
        )

    exclusions = [
        item
        for item in state.source_coverage_exclusions
        if requested_window_start <= item.local_date <= requested_window_end
    ]
    material_exclusions = [
        item for item in exclusions if item.reason != "represented_duplicate_recording"
    ]
    gaps = [
        gap
        for gap in state.source_coverage_gaps
        if gap.start_date <= requested_window_end and gap.end_date >= requested_window_start
    ]
    window_is_covered = covering_window is not None
    if not window_is_covered or gaps:
        status: Literal[
            "complete",
            "complete_with_declared_exclusions",
            "incomplete",
            "unavailable",
        ] = "incomplete"
        reason = (
            "source_sync_has_unresolved_gap" if gaps else "requested_window_not_fully_synchronized"
        )
    elif material_exclusions:
        status = "complete_with_declared_exclusions"
        reason = "source_rows_are_declared_but_unavailable"
    else:
        status = "complete"
        reason = None
    return SyncEvidenceCoverage(
        status=status,
        requested_window_start=requested_window_start,
        requested_window_end=requested_window_end,
        complete_window_start=complete_start,
        complete_window_end=complete_end,
        last_successful_sync_at_utc=last_success,
        exclusions=exclusions,
        gaps=gaps,
        reason=reason,
    )
