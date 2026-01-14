"""
Configuration schemas for M2 - Config & Secrets module.

Defines Pydantic models for settings, secrets, and configuration validation.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# ERROR TYPES
# ============================================================


class ConfigErrorType(str, Enum):
    """Types of configuration errors."""

    FILE_NOT_FOUND = "file_not_found"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    MISSING_SECRET = "missing_secret"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    NETWORK_ERROR = "network_error"


# ============================================================
# SETTINGS MODELS
# ============================================================


class PathSettings(BaseModel):
    """File path configuration (relative to repo root)."""

    athlete_dir: str = "data/athlete"
    activities_dir: str = "data/activities"
    metrics_dir: str = "data/metrics"
    plans_dir: str = "data/plans"
    conversations_dir: str = "data/conversations"
    backup_dir: str = "data/backup"


class StravaSettings(BaseModel):
    """Strava API configuration."""

    api_base_url: str = "https://www.strava.com/api/v3"
    token_url: str = "https://www.strava.com/oauth/token"
    auth_url: str = "https://www.strava.com/oauth/authorize"
    scopes: list[str] = Field(default_factory=lambda: ["read", "activity:read_all"])
    history_import_weeks: int = 12


class TrainingDefaults(BaseModel):
    """Training calculation defaults."""

    ctl_time_constant: int = 42  # days (Chronic Training Load)
    atl_time_constant: int = 7  # days (Acute Training Load)
    acwr_acute_window: int = 7  # days
    acwr_chronic_window: int = 28  # days
    baseline_days_threshold: int = 14
    acwr_minimum_days: int = 28


class SystemSettings(BaseModel):
    """System configuration."""

    lock_timeout_ms: int = 300_000  # 5 minutes
    lock_retry_count: int = 3
    lock_retry_delay_ms: int = 2_000
    backup_retention_count: int = 3  # per month
    metrics_stale_hours: int = 24


class Settings(BaseModel):
    """Complete settings configuration."""

    paths: PathSettings = Field(default_factory=PathSettings)
    strava: StravaSettings = Field(default_factory=StravaSettings)
    training_defaults: TrainingDefaults = Field(default_factory=TrainingDefaults)
    system: SystemSettings = Field(default_factory=SystemSettings)


# ============================================================
# SECRETS MODELS
# ============================================================


class StravaSecrets(BaseModel):
    """Strava authentication secrets."""

    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    token_expires_at: int  # Unix timestamp


class Secrets(BaseModel):
    """All application secrets."""

    strava: StravaSecrets


# ============================================================
# CONFIG MODEL
# ============================================================


class Config(BaseModel):
    """Complete application configuration."""

    settings: Settings
    secrets: Secrets
    loaded_at: datetime
