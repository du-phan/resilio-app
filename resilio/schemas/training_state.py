"""Provider-neutral wellness, sport-settings, and training-state contracts."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WellnessSource(str, Enum):
    INTERVALS_ICU = "intervals_icu"


class WellnessDay(BaseModel):
    local_date: date
    fitness_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    fatigue_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    ramp_load_points_per_week: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    fitness_contribution_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    fatigue_contribution_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    resting_hr_bpm: Optional[int] = Field(default=None, ge=20, le=260)
    hrv_rmssd_ms: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    hrv_sdnn_ms: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    sleep_duration_seconds: Optional[int] = Field(default=None, ge=0, le=172_800)
    sleep_score: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=4)
    average_sleeping_hr_bpm: Optional[float] = Field(
        default=None,
        ge=20,
        le=260,
        allow_inf_nan=False,
    )
    soreness: Optional[int] = Field(default=None, ge=0, le=4)
    subjective_fatigue: Optional[int] = Field(default=None, ge=0, le=4)
    stress: Optional[int] = Field(default=None, ge=0, le=4)
    mood: Optional[int] = Field(default=None, ge=1, le=4)
    motivation: Optional[int] = Field(default=None, ge=1, le=4)
    injury: Optional[int] = Field(default=None, ge=1, le=4)
    hydration: Optional[int] = Field(default=None, ge=1, le=4)
    provider_hydration_volume_value: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_readiness_value: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    vo2_max_ml_per_kg_per_min: Optional[float] = Field(
        default=None,
        gt=0,
        le=100,
        allow_inf_nan=False,
    )
    resting_hr_is_temporary: bool = False
    source: WellnessSource = WellnessSource.INTERVALS_ICU

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @property
    def form_load_points(self) -> Optional[float]:
        if self.fitness_load_points is None or self.fatigue_load_points is None:
            return None
        return round(self.fitness_load_points - self.fatigue_load_points, 10)


class LoadMeasurementMethod(str, Enum):
    POWER = "power"
    HEART_RATE = "heart_rate"
    PACE = "pace"


class SportSettings(BaseModel):
    provider_settings_id: int
    source_sport_types: list[str]
    functional_threshold_power_watts: Optional[int] = Field(default=None, gt=0)
    indoor_functional_threshold_power_watts: Optional[int] = Field(
        default=None,
        gt=0,
    )
    lactate_threshold_hr_bpm: Optional[int] = Field(default=None, gt=0, le=260)
    maximum_hr_bpm: Optional[int] = Field(default=None, gt=0, le=260)
    threshold_speed_meters_per_second: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    pace_display_unit: Optional[str] = None
    power_zone_upper_bounds_watts: list[int] = Field(default_factory=list)
    heart_rate_zone_upper_bounds_bpm: list[int] = Field(default_factory=list)
    pace_zone_upper_bounds_percent: list[float] = Field(default_factory=list)
    power_zone_names: list[str] = Field(default_factory=list)
    heart_rate_zone_names: list[str] = Field(default_factory=list)
    pace_zone_names: list[str] = Field(default_factory=list)
    heart_rate_load_type: Optional[str] = None
    pace_load_type: Optional[str] = None
    load_priority: list[LoadMeasurementMethod] = Field(default_factory=list)
    time_in_zones_priority: list[LoadMeasurementMethod] = Field(default_factory=list)
    workout_priority: list[LoadMeasurementMethod] = Field(default_factory=list)
    default_workout_time_local: Optional[str] = None
    provider_updated_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class SportSettingsSnapshot(BaseModel):
    fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings: list[SportSettings]

    model_config = ConfigDict(extra="forbid")


class ProviderProfileMetric(str, Enum):
    FUNCTIONAL_THRESHOLD_POWER = "functional_threshold_power"
    INDOOR_FUNCTIONAL_THRESHOLD_POWER = "indoor_functional_threshold_power"
    LACTATE_THRESHOLD_HEART_RATE = "lactate_threshold_heart_rate"
    MAXIMUM_HEART_RATE = "maximum_heart_rate"
    THRESHOLD_SPEED = "threshold_speed"
    RESTING_HEART_RATE = "resting_heart_rate"
    PROVIDER_VO2_MAX = "provider_vo2_max"


class ProviderProfileCandidate(BaseModel):
    metric_name: ProviderProfileMetric
    value: float
    unit: str
    source: WellnessSource = WellnessSource.INTERVALS_ICU
    source_sport_types: list[str] = Field(default_factory=list)
    provider_settings_id: int | None = None
    observed_on: date | None = None
    provider_updated_at: datetime | None = None
    is_temporary: bool = False

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ProviderProfileCandidates(BaseModel):
    as_of_date: date
    generated_at_utc: datetime
    sport_settings_fingerprint_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    candidates: list[ProviderProfileCandidate]

    model_config = ConfigDict(extra="forbid")
