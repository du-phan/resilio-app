"""Complete-window listing and strict batch-detail retrieval."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone

from resilio.core.activity_sync.windowing import (
    SaturatedActivityWindowError,
    enumerate_windows,
    fetch_complete_window,
)
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import write_sync_progress
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    ActivitySummaryDTO,
    HiddenActivityDTO,
)
from resilio.schemas.config import IntervalsIcuSettings
from resilio.schemas.sync import (
    CompleteSyncWindow,
    SourceCoverageExclusion,
    SyncProgress,
    SyncReport,
)


@dataclass(frozen=True)
class ActivityListing:
    complete_rows_by_external_id: dict[str, ActivitySummaryDTO]
    listed_external_ids: set[str]
    hidden_rows: list[HiddenActivityDTO]

    @property
    def hidden_row_count(self) -> int:
        return len(self.hidden_rows)

    def source_coverage_exclusions(self) -> list[SourceCoverageExclusion]:
        return [
            SourceCoverageExclusion(
                external_activity_id_sha256=hashlib.sha256(row.id.encode()).hexdigest(),
                local_date=row.start_date_local.date(),
                source_recording_provider=row.source,
                reason="source_hidden",
            )
            for row in self.hidden_rows
        ]


def list_complete_activity_rows(
    *,
    client: IntervalsIcuClient,
    repo: RepositoryIO,
    athlete_id: str,
    oldest: date,
    newest: date,
    settings: IntervalsIcuSettings,
    progress: SyncProgress,
    report: SyncReport,
) -> ActivityListing:
    """Enumerate all complete rows while durably checkpointing windows."""
    complete_rows: dict[str, ActivitySummaryDTO] = {}
    listed_external_ids: set[str] = set()
    hidden_rows: list[HiddenActivityDTO] = []
    windows = enumerate_windows(oldest, newest, settings.initial_window_days)
    for window_start, window_end in windows:
        try:
            rows = fetch_complete_window(
                client,
                window_start,
                window_end,
                athlete_id=athlete_id,
                limit=settings.list_limit,
            )
        except SaturatedActivityWindowError as exc:
            report.partial = True
            report.errors.append(str(exc))
            break
        for row in rows:
            listed_external_ids.add(row.id)
            if isinstance(row, HiddenActivityDTO):
                hidden_rows.append(row)
            else:
                complete_rows[row.id] = row
        completed_at_utc = datetime.now(timezone.utc)
        report.complete_windows.append(
            CompleteSyncWindow(
                oldest=window_start,
                newest=window_end,
                activity_count=len(rows),
                completed_at_utc=completed_at_utc,
            )
        )
        progress.windows_complete += 1
        progress.activities_seen += len(rows)
        progress.hidden_rows = len(hidden_rows)
        progress.updated_at_utc = completed_at_utc
        write_sync_progress(repo, progress)

    report.activities_seen = len(complete_rows) + len(hidden_rows)
    report.hidden_rows = len(hidden_rows)
    return ActivityListing(
        complete_rows_by_external_id=complete_rows,
        listed_external_ids=listed_external_ids,
        hidden_rows=hidden_rows,
    )


def fetch_activity_details(
    *,
    client: IntervalsIcuClient,
    athlete_id: str,
    complete_rows_by_external_id: dict[str, ActivitySummaryDTO],
    detail_batch_size: int,
    report: SyncReport,
) -> dict[str, ActivityDTO]:
    """Fetch exact batches and fail closed on missing, extra, or duplicate IDs."""
    details: dict[str, ActivityDTO] = {}
    external_ids = sorted(complete_rows_by_external_id)
    for offset in range(0, len(external_ids), detail_batch_size):
        requested_ids = external_ids[offset : offset + detail_batch_size]
        batch = client.get_activities(
            requested_ids,
            athlete_id=athlete_id,
            intervals=True,
        )
        returned_ids = [activity.id for activity in batch]
        duplicate_ids = {
            activity_id for activity_id in returned_ids if returned_ids.count(activity_id) > 1
        }
        unexpected_ids = set(returned_ids) - set(requested_ids)
        missing_ids = set(requested_ids) - set(returned_ids)
        _record_batch_identity_errors(
            duplicate_count=len(duplicate_ids),
            unexpected_count=len(unexpected_ids),
            missing_count=len(missing_ids),
            report=report,
        )
        if not duplicate_ids and not unexpected_ids and not missing_ids:
            details.update({activity.id: activity for activity in batch})
    return details


def _record_batch_identity_errors(
    *,
    duplicate_count: int,
    unexpected_count: int,
    missing_count: int,
    report: SyncReport,
) -> None:
    for count, message in (
        (duplicate_count, "Batch detail duplicated {count} activity IDs"),
        (unexpected_count, "Batch detail returned {count} unrequested activity IDs"),
        (missing_count, "Batch detail omitted {count} validated activity IDs"),
    ):
        if count:
            report.partial = True
            report.quarantined_rows += count
            report.errors.append(message.format(count=count))
