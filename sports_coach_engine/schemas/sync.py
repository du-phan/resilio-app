"""
Sync schemas - canonical models for Strava sync reporting and status.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SyncPhase(str, Enum):
    """Sync lifecycle phase."""

    FETCHING = "fetching"
    PROCESSING = "processing"
    METRICS = "metrics"
    PAUSED_RATE_LIMIT = "paused_rate_limit"
    DONE = "done"
    FAILED = "failed"


class SyncReport(BaseModel):
    """Canonical sync result contract."""

    activities_imported: int = 0
    activities_skipped: int = 0
    activities_failed: int = 0
    laps_fetched: int = 0
    laps_skipped_age: int = 0
    lap_fetch_failures: int = 0
    phase: SyncPhase = SyncPhase.DONE
    rate_limited: bool = False
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class SyncResumeState(BaseModel):
    """Persisted state for deterministic sync resume."""

    backfill_in_progress: bool = False
    target_start_date: Optional[date] = None
    resume_before_timestamp: Optional[int] = None
    last_progress_at: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True)


class SyncProgress(BaseModel):
    """Heartbeat snapshot written while sync is running."""

    phase: SyncPhase
    activities_seen: int = 0
    activities_imported: int = 0
    activities_skipped: int = 0
    activities_failed: int = 0
    current_page: Optional[int] = None
    current_month: Optional[str] = None
    cursor_before_timestamp: Optional[int] = None
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class SyncLockStatus(BaseModel):
    """Current lock status for observability."""

    pid: int
    operation: str
    acquired_at: datetime
    age_seconds: int
    stale: bool

    model_config = ConfigDict(populate_by_name=True)


class SyncStatusSnapshot(BaseModel):
    """Status payload returned by `sce sync --status`."""

    running: bool
    lock: Optional[SyncLockStatus] = None
    progress: Optional[SyncProgress] = None
    resume_state: SyncResumeState
    activity_files_count: int = 0

    model_config = ConfigDict(populate_by_name=True)
