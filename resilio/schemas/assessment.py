"""Baseline-assessment intent contracts independent of plan persistence."""

from datetime import date, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.vdot import RaceDistance


class AssessmentReason(str, Enum):
    MISSING_BASELINE = "missing_baseline"
    DISPUTED_BASELINE = "disputed_baseline"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    POST_INACTIVITY_BASELINE = "post_inactivity_baseline"


class TemporaryScheduleConstraint(BaseModel):
    """Athlete-confirmed date range that applies only to one assessment plan."""

    unavailable_start_date: date
    unavailable_end_date: date
    reason: str = Field(min_length=20, max_length=1_000)
    athlete_confirmation_reference: str = Field(min_length=10, max_length=1_000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def unavailable_range_is_ascending(self) -> "TemporaryScheduleConstraint":
        if self.unavailable_end_date < self.unavailable_start_date:
            raise ValueError("temporary unavailable date range must be ascending")
        return self

    def contains(self, candidate_date: date) -> bool:
        return self.unavailable_start_date <= candidate_date <= self.unavailable_end_date


class TimedBenchmarkIntent(BaseModel):
    """Athlete-approved distance and bounded scheduling discretion for one test."""

    race_distance: RaceDistance = RaceDistance.FIVE_K
    preferred_date: date
    fallback_window_start: date
    fallback_window_end: date
    longer_distance_confirmation_reference: str | None = Field(
        default=None,
        min_length=10,
        max_length=1_000,
    )
    longer_distance_rationale: str | None = Field(
        default=None,
        min_length=40,
        max_length=2_000,
    )

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def bounded_window_and_distance_safety(self) -> "TimedBenchmarkIntent":
        if self.fallback_window_end < self.fallback_window_start:
            raise ValueError("benchmark fallback window must be ascending")
        if not self.fallback_window_start <= self.preferred_date <= self.fallback_window_end:
            raise ValueError("benchmark preferred date must fall within the fallback window")
        window_start_monday = self.fallback_window_start - timedelta(
            days=self.fallback_window_start.weekday()
        )
        window_end_monday = self.fallback_window_end - timedelta(
            days=self.fallback_window_end.weekday()
        )
        if window_start_monday != window_end_monday:
            raise ValueError("benchmark fallback window must fit within one plan week")
        longer_than_five_k = RaceDistance(self.race_distance).distance_meters > 5_000
        has_confirmation = self.longer_distance_confirmation_reference is not None
        has_rationale = self.longer_distance_rationale is not None
        if longer_than_five_k and not (has_confirmation and has_rationale):
            raise ValueError(
                "a benchmark longer than 5k requires explicit athlete confirmation and rationale"
            )
        if not longer_than_five_k and (has_confirmation or has_rationale):
            raise ValueError("longer-distance safety fields are only valid above 5k")
        return self
