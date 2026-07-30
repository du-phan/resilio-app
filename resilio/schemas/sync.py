"""Provider-neutral completed-activity sync state and reporting."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SyncPhase(str, Enum):
    PREFLIGHT = "preflight"
    LISTING = "listing"
    DETAIL = "detail"
    RECONCILING = "reconciling"
    COMMITTING = "committing"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"


class CompleteSyncWindow(BaseModel):
    oldest: date
    newest: date
    activity_count: int
    completed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class ActivityCoverageWindow(BaseModel):
    start_date: date
    end_date: date

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def dates_are_ascending(self) -> "ActivityCoverageWindow":
        if self.end_date < self.start_date:
            raise ValueError("coverage window end_date cannot precede start_date")
        return self


class SourceCoverageGap(BaseModel):
    start_date: date
    end_date: date
    reason: Literal["partial_sync_attempt"]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def dates_are_ascending(self) -> "SourceCoverageGap":
        if self.end_date < self.start_date:
            raise ValueError("coverage gap end_date cannot precede start_date")
        return self


class SourceCoverageExclusion(BaseModel):
    """Privacy-safe source evidence intentionally absent from the archive."""

    external_activity_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_date: date
    source_sport_type: Optional[str] = None
    source_recording_provider: Optional[str] = None
    reason: Literal[
        "source_hidden",
        "acknowledged_unsupported_sport",
        "represented_duplicate_recording",
    ]
    represented_by_local_activity_id: Optional[str] = None
    review_fingerprint_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def duplicate_disposition_is_bound(self) -> "SourceCoverageExclusion":
        represented = self.reason == "represented_duplicate_recording"
        bindings = (
            self.represented_by_local_activity_id,
            self.review_fingerprint_sha256,
        )
        if (represented and not all(bindings)) or (not represented and any(bindings)):
            raise ValueError(
                "represented duplicate disposition requires local identity "
                "and review fingerprint; other dispositions forbid them"
            )
        return self


class ActivitySyncState(BaseModel):
    schema_version: Literal[3] = 3
    resolved_athlete_id: Optional[str] = None
    last_successful_incremental_at_utc: Optional[datetime] = None
    last_full_reconciliation_at_utc: Optional[datetime] = None
    incremental_overlap_days: int = 30
    checkpoint_run_id: Optional[str] = None
    external_to_local: dict[str, str] = Field(default_factory=dict)
    sport_settings_fingerprint_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    last_wellness_window_start: Optional[date] = None
    last_wellness_window_end: Optional[date] = None
    complete_activity_windows: list[ActivityCoverageWindow] = Field(default_factory=list)
    source_coverage_gaps: list[SourceCoverageGap] = Field(default_factory=list)
    source_coverage_exclusions: list[SourceCoverageExclusion] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SyncProgress(BaseModel):
    schema_version: Literal[2] = 2
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
    activities_with_native_aerobic_load: int = 0
    wellness_days_received: int = 0
    wellness_days_changed: int = 0
    sport_settings_fingerprint_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
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
    long_running: bool

    model_config = ConfigDict(extra="forbid")


class SyncStatusSnapshot(BaseModel):
    running: bool
    lock: Optional[SyncLockStatus] = None
    progress: Optional[SyncProgress] = None
    state: ActivitySyncState
    activity_files_count: int = 0

    model_config = ConfigDict(extra="forbid")
