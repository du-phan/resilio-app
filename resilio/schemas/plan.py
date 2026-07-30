"""Provider-neutral, methodology-explicit training-plan contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.activity import SportType
from resilio.schemas.methodology import MethodologyChoice, MethodologySelection
from resilio.schemas.profile import ConflictPolicy, GoalType
from resilio.schemas.structured_workout import StructuredWorkout


class PlanSchemaDescriptor(BaseModel):
    name: Literal["resilio.plan"] = "resilio.plan"
    version: Literal[3] = 3

    model_config = ConfigDict(extra="forbid")


class PlanPhase(str, Enum):
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"
    RECOVERY = "recovery"


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


class WorkoutPrescription(BaseModel):
    """One explicit planned session; units are encoded in every numeric field."""

    id: str = Field(
        default_factory=lambda: f"w_{uuid.uuid4().hex[:12]}",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    date: date
    start_time_local: Optional[time] = None
    sport: SportType = SportType.RUN
    workout_type: WorkoutType
    planned_duration_seconds: int = Field(gt=0, le=86_400)
    planned_distance_meters: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
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
    structured_workout: Optional[StructuredWorkout] = None

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def validate_session(self) -> "WorkoutPrescription":
        if (
            self.sport
            in {
                SportType.RUN,
                SportType.TRAIL_RUN,
                SportType.TREADMILL_RUN,
                SportType.TRACK_RUN,
            }
            and self.planned_distance_meters is None
        ):
            raise ValueError("run sessions require planned_distance_meters")
        classified_duration_seconds = (
            self.planned_low_intensity_duration_seconds
            + self.planned_moderate_intensity_duration_seconds
            + self.planned_high_intensity_duration_seconds
        )
        if classified_duration_seconds != self.planned_duration_seconds:
            raise ValueError(
                "planned intensity duration seconds must sum to " "planned_duration_seconds"
            )
        if self.structured_workout is not None and str(self.structured_workout.sport) != str(
            self.sport
        ):
            raise ValueError("structured_workout sport must match workout sport")
        if self.structured_workout is not None:
            if self.start_time_local is None:
                raise ValueError(
                    "structured workouts require an exact start_time_local "
                    "before athlete approval"
                )
            structured_duration_seconds = self.structured_workout.nominal_duration_seconds()
            if structured_duration_seconds != self.planned_duration_seconds:
                raise ValueError(
                    "structured workout nominal duration must equal " "planned_duration_seconds"
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
        return self


QualityType = Literal[
    "tempo",
    "intervals",
    "hills",
    "race_pace",
    "fartlek",
    "strides_only",
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
    """One Monday-Sunday plan week."""

    week_number: int = Field(ge=1)
    phase: PlanPhase
    start_date: date
    end_date: date
    target_run_volume_meters: float = Field(ge=0, allow_inf_nan=False)
    workout_structure_hints: WorkoutStructureHints
    workouts: list[WorkoutPrescription] = Field(default_factory=list)
    is_recovery_week: bool = False
    notes: Optional[str] = Field(default=None, max_length=4_000)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def validate_week(self) -> "WeekPlan":
        if self.start_date.weekday() != 0:
            raise ValueError("week start_date must be a Monday")
        if self.end_date != self.start_date + timedelta(days=6):
            raise ValueError("week end_date must be the following Sunday")
        workout_ids = [workout.id for workout in self.workouts]
        if len(workout_ids) != len(set(workout_ids)):
            raise ValueError("workout IDs must be unique within a week")
        for workout in self.workouts:
            if not self.start_date <= workout.date <= self.end_date:
                raise ValueError("workout date must fall within its plan week")
        planned_run_volume_meters = sum(
            workout.planned_distance_meters or 0
            for workout in self.workouts
            if workout.sport
            in {
                SportType.RUN,
                SportType.TRAIL_RUN,
                SportType.TREADMILL_RUN,
                SportType.TRACK_RUN,
            }
        )
        if self.workouts and abs(planned_run_volume_meters - self.target_run_volume_meters) > 1:
            raise ValueError(
                "run workout planned_distance_meters sum must equal " "target_run_volume_meters"
            )
        return self


class OtherSportPlanningConstraint(BaseModel):
    sport_name: str = Field(min_length=1)
    sessions_per_week: int = Field(ge=1, le=7)
    unavailable_days: list[str] = Field(default_factory=list)
    typical_session_duration_seconds: int = Field(gt=0)
    typical_intensity: str

    model_config = ConfigDict(extra="forbid")


class PlanningConstraintsSnapshot(BaseModel):
    unavailable_run_days: list[str] = Field(default_factory=list)
    minimum_run_days_per_week: int = Field(ge=0, le=7)
    maximum_run_days_per_week: int = Field(ge=0, le=7)
    maximum_session_duration_seconds: Optional[int] = Field(default=None, gt=0)
    active_other_sports: list[OtherSportPlanningConstraint] = Field(default_factory=list)
    running_priority: str
    primary_sport_name: Optional[str] = None
    training_timezone: str

    model_config = ConfigDict(extra="forbid")


class PlanGoal(BaseModel):
    type: GoalType
    target_date: date
    target_time: Optional[str] = Field(
        default=None,
        pattern=r"^(?:[0-9]{1,2}:)?[0-5][0-9]:[0-5][0-9]$",
    )

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class MasterPlan(BaseModel):
    """Current approved macro structure and progressively populated weeks."""

    schema_info: PlanSchemaDescriptor = Field(
        default_factory=PlanSchemaDescriptor,
        validation_alias="_schema",
        serialization_alias="_schema",
    )
    id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    macro_revision_id: str = Field(
        pattern=r"^macro_revision_[a-f0-9]{16}$",
    )
    vdot_approval_id: str = Field(
        pattern=r"^vdot_approval_[a-f0-9]{16}$",
    )
    planning_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    goal: PlanGoal
    methodology: MethodologySelection
    weeks: list[WeekPlan] = Field(min_length=1)
    baseline_vdot: float = Field(ge=30, le=85, allow_inf_nan=False)
    constraints_snapshot: PlanningConstraintsSnapshot
    conflict_policy: ConflictPolicy

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )

    @field_validator("created_at_utc")
    @classmethod
    def creation_timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_plan(self) -> "MasterPlan":
        ordered = sorted(self.weeks, key=lambda week: week.week_number)
        if [week.week_number for week in ordered] != list(range(1, len(ordered) + 1)):
            raise ValueError("plan week numbers must be contiguous from one")
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_date != previous.end_date + timedelta(days=1):
                raise ValueError("plan weeks must be contiguous")
        workout_ids = [workout.id for week in ordered for workout in week.workouts]
        if len(workout_ids) != len(set(workout_ids)):
            raise ValueError("workout IDs must be unique across the plan")
        if not self.start_date <= self.goal.target_date <= self.end_date:
            raise ValueError("goal target_date must fall within the plan horizon")
        uses_fitzgerald_distribution = [
            week.workout_structure_hints.intensity_distribution is not None for week in ordered
        ]
        selected_fitzgerald = self.methodology.identifier == "fitzgerald_80_20"
        if selected_fitzgerald and not all(uses_fitzgerald_distribution):
            raise ValueError("Fitzgerald plans require a weekly time-based intensity distribution")
        if not selected_fitzgerald and any(uses_fitzgerald_distribution):
            raise ValueError("time-based 80/20 targets are only valid for Fitzgerald plans")
        return self

    @property
    def start_date(self) -> date:
        return min(week.start_date for week in self.weeks)

    @property
    def end_date(self) -> date:
        return max(week.end_date for week in self.weeks)

    @property
    def total_weeks(self) -> int:
        return len(self.weeks)

    @property
    def starting_run_volume_meters(self) -> float:
        return min(
            self.weeks,
            key=lambda week: week.week_number,
        ).target_run_volume_meters

    @property
    def peak_run_volume_meters(self) -> float:
        return max(week.target_run_volume_meters for week in self.weeks)


class MacroPlanDraft(BaseModel):
    """Coach-authored macro plan before repository identity is assigned."""

    goal: PlanGoal
    methodology: MethodologyChoice
    weeks: list[WeekPlan] = Field(min_length=1)
    vdot_approval_id: str = Field(
        pattern=r"^vdot_approval_[a-f0-9]{16}$",
    )
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def macro_weeks_are_unpopulated(self) -> "MacroPlanDraft":
        if any(week.workouts for week in self.weeks):
            raise ValueError("macro plan weeks must not contain exact workouts")
        return self


class WeekApplication(BaseModel):
    """Approved exact workouts for one existing macro week."""

    week_number: int = Field(ge=1)
    workouts: list[WorkoutPrescription] = Field(min_length=1)
    adjustment_rationale: str = Field(min_length=40, max_length=4_000)

    model_config = ConfigDict(extra="forbid")
