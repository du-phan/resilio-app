"""Runtime configuration contracts."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ConfigErrorType(str, Enum):
    FILE_NOT_FOUND = "file_not_found"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    MISSING_SECRET = "missing_secret"
    AUTHENTICATION_REJECTED = "authentication_rejected"
    AUTHORIZATION_REJECTED = "authorization_rejected"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"


class PathSettings(BaseModel):
    athlete_dir: str = "data/athlete"
    activities_dir: str = "data/activities"
    plans_dir: str = "data/plans"
    state_dir: str = "data/state"

    model_config = ConfigDict(extra="forbid")


class IntervalsIcuSettings(BaseModel):
    api_base_url: str = "https://intervals.icu/api/v1"
    athlete_alias: str = "0"
    history_start_date: date = date(2022, 1, 20)
    initial_window_days: int = Field(default=90, ge=1, le=365)
    incremental_overlap_days: int = Field(default=30, ge=1, le=90)
    full_reconciliation_days: int = Field(default=30, ge=1, le=365)
    list_limit: int = Field(default=1000, ge=1, le=1000)
    detail_batch_size: int = Field(default=100, ge=1, le=200)
    max_read_attempts: int = Field(default=4, ge=1, le=6)
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    model_config = ConfigDict(extra="forbid")


class Settings(BaseModel):
    paths: PathSettings = Field(default_factory=PathSettings)
    intervals_icu: IntervalsIcuSettings = Field(default_factory=IntervalsIcuSettings)

    model_config = ConfigDict(extra="forbid")


class Config(BaseModel):
    settings: Settings
    intervals_icu_api_key: SecretStr
    loaded_at: datetime

    model_config = ConfigDict(extra="forbid")
