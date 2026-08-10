"""Run-only workout prescription contracts."""

from __future__ import annotations

import uuid
from datetime import date, time
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.structured_workout import StructuredWorkout, WorkoutSport


class WorkoutType(str, Enum):
    EASY = "easy"
    LONG_RUN = "long_run"
    TEMPO = "tempo"
    INTERVALS = "intervals"
    HILLS = "hills"
    RACE_PACE = "race_pace"
    FARTLEK = "fartlek"
    STRIDES = "strides"
    RACE = "race"
    BENCHMARK = "benchmark"


class RunningWorkoutPrescription(BaseModel):
    """One approved running session with units encoded in every numeric field."""

    id: str = Field(
        default_factory=lambda: f"w_{uuid.uuid4().hex}",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    date: date
    start_time_local: Optional[time] = None
    sport: Literal["run"] = "run"
    workout_type: WorkoutType
    planned_duration_seconds: int = Field(gt=0, le=86_400)
    planned_distance_meters: float = Field(gt=0, allow_inf_nan=False)
    planned_low_intensity_duration_seconds: int = Field(ge=0)
    planned_moderate_intensity_duration_seconds: int = Field(ge=0)
    planned_high_intensity_duration_seconds: int = Field(ge=0)
    target_rpe_1_to_10: int = Field(ge=1, le=10)
    target_pace_minimum_seconds_per_kilometer: Optional[int] = Field(
        default=None,
        gt=0,
        le=3_600,
    )
    target_pace_maximum_seconds_per_kilometer: Optional[int] = Field(
        default=None,
        gt=0,
        le=3_600,
    )
    target_heart_rate_minimum_beats_per_minute: Optional[int] = Field(
        default=None,
        ge=20,
        le=260,
    )
    target_heart_rate_maximum_beats_per_minute: Optional[int] = Field(
        default=None,
        ge=20,
        le=260,
    )
    purpose: str = Field(min_length=1, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=4_000)
    structured_workout: StructuredWorkout

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        validate_default=True,
    )

    @model_validator(mode="after")
    def validate_session(self) -> "RunningWorkoutPrescription":
        classified_duration_seconds = (
            self.planned_low_intensity_duration_seconds
            + self.planned_moderate_intensity_duration_seconds
            + self.planned_high_intensity_duration_seconds
        )
        if classified_duration_seconds != self.planned_duration_seconds:
            raise ValueError(
                "planned intensity duration seconds must sum to planned_duration_seconds"
            )
        if WorkoutSport(self.structured_workout.sport) != WorkoutSport.RUN:
            raise ValueError("structured_workout must prescribe running")
        if self.structured_workout.nominal_duration_seconds() != self.planned_duration_seconds:
            raise ValueError(
                "structured workout nominal duration must equal planned_duration_seconds"
            )
        if (self.target_pace_minimum_seconds_per_kilometer is None) != (
            self.target_pace_maximum_seconds_per_kilometer is None
        ):
            raise ValueError("pace targets require both minimum and maximum values")
        if (
            self.target_pace_minimum_seconds_per_kilometer is not None
            and self.target_pace_maximum_seconds_per_kilometer is not None
            and self.target_pace_minimum_seconds_per_kilometer
            > self.target_pace_maximum_seconds_per_kilometer
        ):
            raise ValueError("minimum pace seconds per kilometer cannot exceed maximum")
        if (self.target_heart_rate_minimum_beats_per_minute is None) != (
            self.target_heart_rate_maximum_beats_per_minute is None
        ):
            raise ValueError("heart-rate targets require both minimum and maximum values")
        if (
            self.target_heart_rate_minimum_beats_per_minute is not None
            and self.target_heart_rate_maximum_beats_per_minute is not None
            and self.target_heart_rate_minimum_beats_per_minute
            > self.target_heart_rate_maximum_beats_per_minute
        ):
            raise ValueError("minimum heart rate cannot exceed maximum heart rate")
        if self.workout_type == WorkoutType.BENCHMARK:
            if len(self.structured_workout.timed_distance_steps()) != 1:
                raise ValueError("benchmark workouts require exactly one timed-distance step")
            has_pace_target = self.target_pace_minimum_seconds_per_kilometer is not None
            has_heart_rate_target = self.target_heart_rate_minimum_beats_per_minute is not None
            if has_pace_target or has_heart_rate_target:
                raise ValueError("benchmark workouts cannot prescribe pace or heart-rate targets")
        return self
