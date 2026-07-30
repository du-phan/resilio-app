"""Athlete-confirmed profile contracts.

Provider observations do not live in this document. They remain in the
wellness and sport-settings archives and are exposed as read-only candidates.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.activity import SportType, is_running_sport
from resilio.schemas.weather import WeatherLocation


class Weekday(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class RunningPriority(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EQUAL = "equal"


class ConflictPolicy(str, Enum):
    PRIMARY_SPORT_WINS = "primary_sport_wins"
    RUNNING_GOAL_WINS = "running_goal_wins"
    ASK_EACH_TIME = "ask_each_time"


class GoalType(str, Enum):
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"
    GENERAL_FITNESS = "general_fitness"


class DetailLevel(str, Enum):
    BRIEF = "brief"
    MODERATE = "moderate"
    DETAILED = "detailed"


class CoachingStyle(str, Enum):
    ANALYTICAL = "analytical"


class IntensityMetric(str, Enum):
    PACE = "pace"
    HEART_RATE = "heart_rate"
    RPE = "rpe"


class PauseReason(str, Enum):
    FOCUS_RUNNING = "focus_running"
    INJURY = "injury"
    ILLNESS = "illness"
    OFF_SEASON = "off_season"
    OTHER = "other"


class TypicalIntensity(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    MODERATE_TO_HARD = "moderate_to_hard"


class Goal(BaseModel):
    type: GoalType
    target_date: date | None = None
    target_finish_time_seconds: int | None = Field(default=None, gt=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_goal(self) -> "Goal":
        if self.type == GoalType.GENERAL_FITNESS and self.target_finish_time_seconds:
            raise ValueError("general_fitness goals cannot have a target finish time")
        return self


class TrainingConstraints(BaseModel):
    unavailable_run_days: list[Weekday] = Field(default_factory=list)
    minimum_run_days_per_week: int = Field(ge=0, le=7)
    maximum_run_days_per_week: int = Field(ge=0, le=7)
    maximum_session_duration_minutes: int | None = Field(default=90, gt=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_availability(self) -> "TrainingConstraints":
        if self.minimum_run_days_per_week > self.maximum_run_days_per_week:
            raise ValueError("minimum_run_days_per_week cannot exceed maximum_run_days_per_week")
        if len(set(self.unavailable_run_days)) != len(self.unavailable_run_days):
            raise ValueError("unavailable_run_days cannot contain duplicates")
        available_days = 7 - len(self.unavailable_run_days)
        if self.minimum_run_days_per_week > available_days:
            raise ValueError("minimum_run_days_per_week exceeds the number of available days")
        return self


class OtherSport(BaseModel):
    sport_name: str = Field(min_length=1)
    sessions_per_week: int = Field(ge=1, le=7)
    unavailable_days: list[Weekday] = Field(default_factory=list)
    typical_session_duration_minutes: int = Field(default=60, gt=0)
    typical_intensity: TypicalIntensity = TypicalIntensity.MODERATE
    active: bool = True
    pause_reason: PauseReason | None = None
    paused_on: date | None = None
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_pause_state(self) -> "OtherSport":
        cleaned_name = self.sport_name.strip()
        if not cleaned_name:
            raise ValueError("sport_name cannot be blank")
        try:
            canonical_sport = SportType(cleaned_name.casefold())
        except ValueError as exc:
            raise ValueError("sport_name must be a canonical Resilio sport type") from exc
        if is_running_sport(canonical_sport):
            raise ValueError("running variants are not an other-sport commitment")
        self.sport_name = canonical_sport.value
        if len(set(self.unavailable_days)) != len(self.unavailable_days):
            raise ValueError("unavailable_days cannot contain duplicates")
        if self.active:
            self.pause_reason = None
            self.paused_on = None
        elif self.pause_reason is None:
            raise ValueError("inactive sport commitments require a pause_reason")
        return self


class CommunicationPreferences(BaseModel):
    detail_level: DetailLevel = DetailLevel.MODERATE
    coaching_style: CoachingStyle = CoachingStyle.ANALYTICAL
    intensity_metric: IntensityMetric = IntensityMetric.PACE

    model_config = ConfigDict(extra="forbid")


WeatherPreferences = WeatherLocation


class PBEntry(BaseModel):
    elapsed_time_seconds: int = Field(gt=0)
    performance_date: date
    vdot: float = Field(ge=30.0, le=85.0)

    model_config = ConfigDict(extra="forbid")


class AthleteProfile(BaseModel):
    schema_version: Literal[2] = 2
    athlete_name: str = Field(min_length=1)
    created_on: date
    training_timezone: str = Field(min_length=1)
    age_years: int | None = Field(default=None, ge=0, le=120)
    running_experience_years: float | None = Field(default=None, ge=0)
    personal_bests_by_distance: dict[str, PBEntry] = Field(default_factory=dict)
    constraints: TrainingConstraints
    other_sport_commitments: list[OtherSport] = Field(default_factory=list)
    running_priority: RunningPriority
    primary_sport_name: str | None = None
    conflict_policy: ConflictPolicy
    goal: Goal = Field(default_factory=lambda: Goal(type=GoalType.GENERAL_FITNESS))
    preferences: CommunicationPreferences = Field(default_factory=CommunicationPreferences)
    weather_preferences: WeatherPreferences | None = None

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
    def validate_profile(self) -> "AthleteProfile":
        cleaned_name = self.athlete_name.strip()
        if not cleaned_name:
            raise ValueError("athlete_name cannot be blank")
        self.athlete_name = cleaned_name
        if self.primary_sport_name is not None:
            try:
                self.primary_sport_name = SportType(
                    self.primary_sport_name.strip().casefold()
                ).value
            except ValueError as exc:
                raise ValueError(
                    "primary_sport_name must be a canonical Resilio sport type"
                ) from exc
        normalized_sports = [
            commitment.sport_name.casefold() for commitment in self.other_sport_commitments
        ]
        if len(set(normalized_sports)) != len(normalized_sports):
            raise ValueError("other sport commitments must have unique sport names")
        return self

    @property
    def peak_vdot(self) -> float | None:
        values = [entry.vdot for entry in self.personal_bests_by_distance.values()]
        return max(values, default=None)
