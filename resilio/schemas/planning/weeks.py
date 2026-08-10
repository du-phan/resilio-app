"""Monday-Sunday run-plan week contracts."""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.planning.workouts import RunningWorkoutPrescription


class PlanPhase(str, Enum):
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"
    RECOVERY = "recovery"
    ASSESSMENT = "assessment"


QualityType = Literal[
    "tempo",
    "intervals",
    "hills",
    "race_pace",
    "fartlek",
    "strides_only",
    "benchmark",
]
LongRunEmphasis = Literal["easy", "steady", "progression", "race_specific"]


class QualitySessionHints(BaseModel):
    maximum_sessions: int = Field(ge=0, le=3)
    types: list[QualityType]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def types_match_count(self) -> "QualitySessionHints":
        if self.maximum_sessions == 0 and self.types:
            raise ValueError("quality types must be empty when maximum_sessions is zero")
        if self.maximum_sessions > 0 and not self.types:
            raise ValueError("quality types are required when maximum_sessions is positive")
        return self


class LongRunHints(BaseModel):
    emphasis: LongRunEmphasis
    minimum_weekly_run_volume_percent: float = Field(
        ge=15,
        le=55,
        allow_inf_nan=False,
    )
    maximum_weekly_run_volume_percent: float = Field(
        ge=15,
        le=55,
        allow_inf_nan=False,
    )
    target_distance_meters: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def percentage_range_is_ascending(self) -> "LongRunHints":
        if self.minimum_weekly_run_volume_percent >= self.maximum_weekly_run_volume_percent:
            raise ValueError("long-run percentage range must be ascending")
        return self


class FitzgeraldIntensityDistribution(BaseModel):
    methodology: Literal["fitzgerald_80_20"] = "fitzgerald_80_20"
    minimum_low_intensity_time_percent: float = Field(
        ge=75,
        le=95,
        allow_inf_nan=False,
    )

    model_config = ConfigDict(extra="forbid")


class WorkoutStructureHints(BaseModel):
    quality: QualitySessionHints
    long_run: Optional[LongRunHints] = None
    intensity_distribution: Optional[FitzgeraldIntensityDistribution] = None

    model_config = ConfigDict(extra="forbid")


class WeekPlan(BaseModel):
    """One Monday-Sunday run-plan week."""

    week_number: int = Field(ge=1)
    phase: PlanPhase
    start_date: date
    end_date: date
    target_run_volume_meters: float = Field(ge=0, allow_inf_nan=False)
    workout_structure_hints: WorkoutStructureHints
    running_workouts: list[RunningWorkoutPrescription] = Field(default_factory=list)
    is_recovery_week: bool = False
    notes: Optional[str] = Field(default=None, max_length=4_000)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def validate_week(self) -> "WeekPlan":
        if self.start_date.weekday() != 0:
            raise ValueError("week start_date must be a Monday")
        if self.end_date != self.start_date + timedelta(days=6):
            raise ValueError("week end_date must be the following Sunday")
        workout_ids = [workout.id for workout in self.running_workouts]
        if len(workout_ids) != len(set(workout_ids)):
            raise ValueError("running workout IDs must be unique within a week")
        for workout in self.running_workouts:
            if not self.start_date <= workout.date <= self.end_date:
                raise ValueError("running workout date must fall within its plan week")
        planned_run_volume_meters = sum(
            workout.planned_distance_meters for workout in self.running_workouts
        )
        if (
            self.running_workouts
            and abs(planned_run_volume_meters - self.target_run_volume_meters) > 1
        ):
            raise ValueError(
                "running_workout planned_distance_meters sum must equal " "target_run_volume_meters"
            )
        return self
