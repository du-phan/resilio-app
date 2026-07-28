"""Provider-neutral completed-activity sync state and reporting."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SyncPhase(str, Enum):
    PREFLIGHT = "preflight"
    LISTING = "listing"
    DETAIL = "detail"
    RECONCILING = "reconciling"
    COMMITTING = "committing"
    METRICS = "metrics"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"


class CompleteSyncWindow(BaseModel):
    oldest: date
    newest: date
    activity_count: int
    completed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class ActivitySyncState(BaseModel):
    schema_version: int = 2
    resolved_athlete_id: Optional[str] = None
    last_successful_incremental_at_utc: Optional[datetime] = None
    last_complete_window_start: Optional[date] = None
    last_complete_window_end: Optional[date] = None
    last_full_reconciliation_at_utc: Optional[datetime] = None
    incremental_overlap_days: int = 30
    checkpoint_run_id: Optional[str] = None
    external_to_local: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class SyncProgress(BaseModel):
    schema_version: int = 2
    run_id: str
    phase: SyncPhase
    oldest: date
    newest: date
    windows_complete: int = 0
    windows_total: int = 0
    activities_seen: int = 0
    activities_created: int = 0
    activities_updated: int = 0
    activities_linked: int = 0
    hidden_rows: int = 0
    ambiguous_rows: int = 0
    updated_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class SyncReport(BaseModel):
    run_id: str
    phase: SyncPhase = SyncPhase.DONE
    activities_seen: int = 0
    activities_created: int = 0
    activities_updated: int = 0
    activities_linked: int = 0
    activities_unchanged: int = 0
    activities_tombstoned: int = 0
    completion_matches_linked: int = 0
    completion_candidates_reported: int = 0
    hidden_rows: int = 0
    ambiguous_rows: int = 0
    excluded_duplicate_rows: int = 0
    quarantined_rows: int = 0
    acknowledged_quarantined_rows: int = 0
    partial: bool = False
    earliest_changed_date: Optional[date] = None
    complete_windows: list[CompleteSyncWindow] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class SyncLockStatus(BaseModel):
    pid: int
    operation: str
    acquired_at: datetime
    age_seconds: int
    stale: bool

    model_config = ConfigDict(extra="forbid")


class SyncStatusSnapshot(BaseModel):
    running: bool
    lock: Optional[SyncLockStatus] = None
    progress: Optional[SyncProgress] = None
    state: ActivitySyncState
    activity_files_count: int = 0

    model_config = ConfigDict(extra="forbid")
