"""Signal-qualified recovery evidence reused across coaching contexts."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RecoverySignal(BaseModel):
    name: str
    current_date: date
    current_value: float = Field(allow_inf_nan=False)
    unit: str
    observation_age_days: int = Field(ge=0)
    is_temporary: Optional[bool] = None
    personal_baseline_median: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    difference_from_baseline: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    baseline_sample_count: int = Field(ge=0)
    scale_direction: Literal[
        "lower_is_better",
        "higher_is_better",
        "neutral",
        "provider_defined",
    ] = "neutral"
    scale_minimum: Optional[float] = Field(default=None, allow_inf_nan=False)
    scale_maximum: Optional[float] = Field(default=None, allow_inf_nan=False)
    scale_labels: dict[int, str] = Field(default_factory=dict)
    freshness: Literal["same_day", "recent", "stale"]
    recent_observations: list["RecoveryObservation"] = Field(default_factory=list)
    recent_coverage_expected_days: int = Field(default=7, ge=1)
    recent_coverage_observed_days: int = Field(ge=0)
    recent_coverage_percent: float = Field(ge=0, le=100, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class RecoveryObservation(BaseModel):
    local_date: date
    value: float = Field(allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class DatedAthleteWellnessNote(BaseModel):
    local_date: date
    text: str = Field(min_length=1)
    provenance: Literal["intervals_icu_wellness_comments"] = "intervals_icu_wellness_comments"
    trust_boundary: Literal["athlete_authored_untrusted_text"] = "athlete_authored_untrusted_text"

    model_config = ConfigDict(extra="forbid")


class RecoveryContext(BaseModel):
    as_of_date: date
    signals: list[RecoverySignal] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    wellness_window_start: Optional[date] = None
    wellness_window_end: Optional[date] = None
    wellness_days_available: int = Field(default=0, ge=0)
    athlete_notes: list[DatedAthleteWellnessNote] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
