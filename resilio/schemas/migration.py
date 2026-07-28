"""Deterministic activity-v2 migration reports and run state."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ArchiveTotals(BaseModel):
    record_count: int = 0
    earliest_date: Optional[date] = None
    latest_date: Optional[date] = None
    sport_counts: dict[str, int] = Field(default_factory=dict)
    duration_seconds: int = 0
    distance_meters: float = 0.0
    elevation_gain_meters: float = 0.0
    systemic_load_au: float = 0.0
    lower_body_load_au: float = 0.0
    screenshot_record_count: int = 0
    screenshot_sport_counts: dict[str, int] = Field(default_factory=dict)
    screenshot_earliest_date: Optional[date] = None
    screenshot_latest_date: Optional[date] = None

    model_config = ConfigDict(extra="forbid")


class MigrationReconciliation(BaseModel):
    schema_version: int = 1
    input_manifest_sha256: str
    source: ArchiveTotals
    candidate: ArchiveTotals
    source_file_sha256: dict[str, str]
    candidate_file_sha256: dict[str, str]
    local_id_ledger_sha256: dict[str, str]
    all_records_valid: bool
    totals_match: bool
    normalizations: list[str] = Field(default_factory=list)
    mismatches: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class MigrationRunEnvelope(BaseModel):
    schema_version: int = 1
    run_id: str
    input_manifest_sha256: str
    created_at_utc: datetime
    source_validated: bool = False
    backup_verified: bool = False
    candidate_built: bool = False
    reconciliation_passed: bool = False
    applied: bool = False
    rollback_verified: bool = False

    model_config = ConfigDict(extra="forbid")
