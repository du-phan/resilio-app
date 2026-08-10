"""Immutable planning-input projections."""

from __future__ import annotations

from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.activity import SportType, is_running_sport
from resilio.schemas.profile import (
    AthleteManagedParticipation,
    AthleteManagedSportFirstPriority,
    TrainingPriority,
    TypicalIntensity,
    Weekday,
)


class AthleteManagedSportExpectation(BaseModel):
    """Athlete-confirmed future context that never becomes prescribed work."""

    sport_name: str = Field(min_length=1)
    participation_pattern: AthleteManagedParticipation
    typical_session_duration_seconds: int = Field(gt=0)
    athlete_reported_typical_intensity: TypicalIntensity
    athlete_context_note: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("sport_name")
    @classmethod
    def sport_is_canonical_non_run(cls, value: str) -> str:
        try:
            sport = SportType(value.strip().casefold())
        except ValueError as exc:
            raise ValueError("expected sport must be a canonical Resilio sport type") from exc
        if is_running_sport(sport):
            raise ValueError("athlete-managed expectation cannot reference running")
        return sport.value

    @property
    def expected_sessions_per_week(self) -> int:
        pattern = self.participation_pattern
        if pattern.kind == "flexible_weekly":
            return pattern.expected_sessions_per_week
        return len(pattern.weekdays)

    @property
    def expected_weekly_duration_seconds(self) -> int:
        return self.expected_sessions_per_week * self.typical_session_duration_seconds


class PlanningConstraintsSnapshot(BaseModel):
    unavailable_run_days: list[Weekday] = Field(default_factory=list)
    minimum_run_days_per_week: int = Field(ge=0, le=7)
    maximum_run_days_per_week: int = Field(ge=0, le=7)
    maximum_session_duration_seconds: Optional[int] = Field(default=None, gt=0)
    athlete_managed_sport_expectations: list[AthleteManagedSportExpectation] = Field(
        default_factory=list
    )
    training_priority: TrainingPriority
    training_timezone: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("training_timezone")
    @classmethod
    def training_timezone_is_iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("training_timezone must be a recognized IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def constraints_are_coherent(self) -> "PlanningConstraintsSnapshot":
        if self.minimum_run_days_per_week > self.maximum_run_days_per_week:
            raise ValueError("minimum_run_days_per_week cannot exceed maximum_run_days_per_week")
        if len(self.unavailable_run_days) != len(set(self.unavailable_run_days)):
            raise ValueError("unavailable_run_days cannot contain duplicates")
        available_run_days = 7 - len(self.unavailable_run_days)
        if self.minimum_run_days_per_week > available_run_days:
            raise ValueError("minimum_run_days_per_week exceeds the number of available days")
        sport_names = [
            expectation.sport_name for expectation in self.athlete_managed_sport_expectations
        ]
        if len(sport_names) != len(set(sport_names)):
            raise ValueError("athlete-managed sport expectations must be unique")
        if isinstance(self.training_priority, AthleteManagedSportFirstPriority):
            if self.training_priority.sport_name not in set(sport_names):
                raise ValueError("athlete-managed sport priority must reference an expected sport")
        return self
