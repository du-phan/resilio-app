"""Provider-neutral, methodology-explicit training-plan contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.activity import SportType
from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryOtherSportCommitmentOverride,
    TemporaryScheduleConstraint,
    TimedBenchmarkIntent,
)
from resilio.schemas.methodology import MethodologySelection
from resilio.schemas.plan_history import (
    EvidenceArtifactReference,
    PlanAdaptationDecision,
    PlanAdaptationDecisionType,
)
from resilio.schemas.profile import ConflictPolicy, GoalType
from resilio.schemas.structured_workout import StructuredWorkout
from resilio.schemas.vdot import RaceDistance


class PlanSchemaDescriptor(BaseModel):
    name: Literal["resilio.plan"] = "resilio.plan"
    version: Literal[4] = 4

    model_config = ConfigDict(extra="forbid")


class PlanPhase(str, Enum):
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"
    RECOVERY = "recovery"
    ASSESSMENT = "assessment"


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


class WorkoutPrescription(BaseModel):
    """One explicit planned session; units are encoded in every numeric field."""

    id: str = Field(
        default_factory=lambda: f"w_{uuid.uuid4().hex}",
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
        if self.workout_type == WorkoutType.BENCHMARK:
            if self.structured_workout is None:
                raise ValueError("benchmark workouts require a structured workout")
            if len(self.structured_workout.timed_distance_steps()) != 1:
                raise ValueError("benchmark workouts require exactly one timed-distance step")
            has_pace_target = self.target_pace_minimum_seconds_per_kilometer is not None
            has_heart_rate_target = (
                self.target_heart_rate_minimum_beats_per_minute is not None
            )
            if has_pace_target or has_heart_rate_target:
                raise ValueError("benchmark workouts cannot prescribe pace or heart-rate targets")
        return self


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


class TrainingPlanBase(BaseModel):
    """Fields and invariants shared by every plan lifecycle."""

    schema_info: PlanSchemaDescriptor = Field(
        default_factory=PlanSchemaDescriptor,
        validation_alias="_schema",
        serialization_alias="_schema",
    )
    id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    plan_revision_id: str = Field(pattern=r"^plan_revision_[a-f0-9]{16}$")
    planning_context_reference: EvidenceArtifactReference
    planning_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    planning_rationale: str = Field(min_length=40, max_length=4_000)
    adaptation_decisions: list[PlanAdaptationDecision] = Field(min_length=2)
    weeks: list[WeekPlan] = Field(min_length=1)
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
    def common_plan_invariants(self) -> "TrainingPlanBase":
        ordered = sorted(self.weeks, key=lambda week: week.week_number)
        if [week.week_number for week in ordered] != list(range(1, len(ordered) + 1)):
            raise ValueError("plan week numbers must be contiguous from one")
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_date != previous.end_date + timedelta(days=1):
                raise ValueError("plan weeks must be contiguous")
        workout_ids = [workout.id for week in ordered for workout in week.workouts]
        if len(workout_ids) != len(set(workout_ids)):
            raise ValueError("workout IDs must be unique across the plan")
        decision_types = [str(decision.decision_type) for decision in self.adaptation_decisions]
        if len(decision_types) != len(set(decision_types)):
            raise ValueError("plan adaptation decision types must be unique")
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


class RaceMacroPlan(TrainingPlanBase):
    """Methodology-explicit race plan populated one approved week at a time."""

    kind: Literal["race_macro"] = "race_macro"
    vdot_approval_id: str = Field(pattern=r"^vdot_approval_[a-f0-9]{16}$")
    goal: PlanGoal
    methodology: MethodologySelection
    baseline_vdot: float = Field(ge=30, le=85, allow_inf_nan=False)

    @model_validator(mode="after")
    def race_plan_invariants(self) -> "RaceMacroPlan":
        if not self.start_date <= self.goal.target_date <= self.end_date:
            raise ValueError("goal target_date must fall within the plan horizon")
        uses_fitzgerald_distribution = [
            week.workout_structure_hints.intensity_distribution is not None
            for week in self.weeks
        ]
        selected_fitzgerald = self.methodology.identifier == "fitzgerald_80_20"
        if selected_fitzgerald and not all(uses_fitzgerald_distribution):
            raise ValueError("Fitzgerald plans require a weekly time-based intensity distribution")
        if not selected_fitzgerald and any(uses_fitzgerald_distribution):
            raise ValueError("time-based 80/20 targets are only valid for Fitzgerald plans")
        if self.planning_context_reference.artifact_type != "macro_planning_context":
            raise ValueError("race macro plan requires macro-planning context evidence")
        required = {
            PlanAdaptationDecisionType.METHODOLOGY_SELECTION.value,
            PlanAdaptationDecisionType.STARTING_VOLUME.value,
        }
        decision_types = {str(decision.decision_type) for decision in self.adaptation_decisions}
        if not required.issubset(decision_types):
            raise ValueError("race macro plan must explain methodology and starting volume")
        return self


def _validate_assessment_week_structure(
    weeks: list[WeekPlan],
    benchmark_intent: TimedBenchmarkIntent,
) -> None:
    benchmark_weeks = [
        week
        for week in weeks
        if week.start_date <= benchmark_intent.fallback_window_start
        and benchmark_intent.fallback_window_end <= week.end_date
    ]
    if len(benchmark_weeks) != 1:
        raise ValueError("assessment requires exactly one benchmark week")
    benchmark_week = benchmark_weeks[0]
    for week in weeks:
        quality = week.workout_structure_hints.quality
        if week.week_number == benchmark_week.week_number:
            if (
                week.phase != PlanPhase.ASSESSMENT.value
                or quality.maximum_sessions != 1
                or quality.types != ["benchmark"]
            ):
                raise ValueError(
                    "assessment benchmark week requires assessment phase and one benchmark"
                )
        elif quality.maximum_sessions != 0 or quality.types:
            raise ValueError("return weeks before the benchmark cannot prescribe quality work")


class BaselineAssessmentPlan(TrainingPlanBase):
    """Short non-rehabilitation return block ending in one timed benchmark."""

    kind: Literal["baseline_assessment"] = "baseline_assessment"
    assessment_reasons: list[AssessmentReason] = Field(min_length=1)
    benchmark_intent: TimedBenchmarkIntent
    temporary_schedule_constraints: list[TemporaryScheduleConstraint] = Field(
        default_factory=list
    )
    temporary_other_sport_commitment_overrides: list[
        TemporaryOtherSportCommitmentOverride
    ] = Field(default_factory=list)
    medical_rehabilitation_excluded: Literal[True] = True

    @model_validator(mode="after")
    def assessment_plan_invariants(self) -> "BaselineAssessmentPlan":
        if self.planning_context_reference.artifact_type != "assessment_planning_context":
            raise ValueError("assessment plan requires assessment-planning context evidence")
        if len(self.assessment_reasons) != len(set(self.assessment_reasons)):
            raise ValueError("assessment reasons must be unique")
        required = {
            PlanAdaptationDecisionType.STARTING_VOLUME.value,
            PlanAdaptationDecisionType.BENCHMARK_SCHEDULING.value,
        }
        decision_types = {str(decision.decision_type) for decision in self.adaptation_decisions}
        if not required.issubset(decision_types):
            raise ValueError(
                "assessment plan must explain starting volume and benchmark scheduling"
            )
        intent = self.benchmark_intent
        if not self.start_date <= intent.fallback_window_start:
            raise ValueError("benchmark fallback window must fall within the plan horizon")
        if intent.fallback_window_end > self.end_date:
            raise ValueError("benchmark fallback window must fall within the plan horizon")
        _validate_assessment_week_structure(self.weeks, intent)
        if any(
            constraint.contains(intent.preferred_date)
            for constraint in self.temporary_schedule_constraints
        ):
            raise ValueError("benchmark preferred date falls in a temporary unavailable range")
        fallback_dates = (
            intent.fallback_window_start + timedelta(days=offset)
            for offset in range(
                (intent.fallback_window_end - intent.fallback_window_start).days + 1
            )
        )
        if any(
            constraint.contains(candidate_date)
            for candidate_date in fallback_dates
            for constraint in self.temporary_schedule_constraints
        ):
            raise ValueError("benchmark fallback window overlaps temporary unavailability")
        override_keys = [
            (override.week_start_date, override.sport_name)
            for override in self.temporary_other_sport_commitment_overrides
        ]
        if len(override_keys) != len(set(override_keys)):
            raise ValueError("temporary other-sport overrides must be unique by week and sport")
        plan_week_starts = {week.start_date for week in self.weeks}
        active_sports = {
            constraint.sport_name for constraint in self.constraints_snapshot.active_other_sports
        }
        for override in self.temporary_other_sport_commitment_overrides:
            if override.week_start_date not in plan_week_starts:
                raise ValueError("temporary other-sport override falls outside the plan")
            if override.sport_name not in active_sports:
                raise ValueError("temporary override references an inactive other sport")
        benchmarks = [
            workout
            for week in self.weeks
            for workout in week.workouts
            if workout.workout_type == WorkoutType.BENCHMARK.value
        ]
        if len(benchmarks) > 1:
            raise ValueError("assessment plan can contain only one benchmark workout")
        if benchmarks:
            benchmark = benchmarks[0]
            if not intent.fallback_window_start <= benchmark.date <= intent.fallback_window_end:
                raise ValueError("benchmark workout must fall within its approved window")
            assert benchmark.structured_workout is not None
            timed_step = benchmark.structured_workout.timed_distance_steps()[0]
            expected_distance_meters = RaceDistance(intent.race_distance).distance_meters
            if abs(timed_step.distance_meters - expected_distance_meters) > 0.01:
                raise ValueError("benchmark timed-distance step must match its approved distance")
        for week in self.weeks:
            for workout in week.workouts:
                if any(
                    constraint.contains(workout.date)
                    for constraint in self.temporary_schedule_constraints
                ):
                    raise ValueError("workout falls in a temporary unavailable date range")
        return self


TrainingPlan = Annotated[
    RaceMacroPlan | BaselineAssessmentPlan,
    Field(discriminator="kind"),
]


class AssessmentPlanDraft(BaseModel):
    """Coach-authored assessment block before repository identity is assigned."""

    weeks: list[WeekPlan] = Field(min_length=1)
    planning_context_reference: EvidenceArtifactReference
    planning_rationale: str = Field(min_length=40, max_length=4_000)
    adaptation_decisions: list[PlanAdaptationDecision] = Field(min_length=2)
    assessment_reasons: list[AssessmentReason] = Field(min_length=1)
    benchmark_intent: TimedBenchmarkIntent
    temporary_schedule_constraints: list[TemporaryScheduleConstraint] = Field(
        default_factory=list
    )
    temporary_other_sport_commitment_overrides: list[
        TemporaryOtherSportCommitmentOverride
    ] = Field(default_factory=list)
    medical_rehabilitation_excluded: Literal[True] = True

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def assessment_weeks_are_unpopulated(self) -> "AssessmentPlanDraft":
        if any(week.workouts for week in self.weeks):
            raise ValueError("assessment plan weeks must not contain exact workouts")
        if self.planning_context_reference.artifact_type != "assessment_planning_context":
            raise ValueError("assessment draft requires assessment-planning context evidence")
        if len(self.assessment_reasons) != len(set(self.assessment_reasons)):
            raise ValueError("assessment reasons must be unique")
        _validate_assessment_week_structure(self.weeks, self.benchmark_intent)
        decision_types = [str(decision.decision_type) for decision in self.adaptation_decisions]
        if len(decision_types) != len(set(decision_types)):
            raise ValueError("assessment draft adaptation decision types must be unique")
        required = {
            PlanAdaptationDecisionType.STARTING_VOLUME.value,
            PlanAdaptationDecisionType.BENCHMARK_SCHEDULING.value,
        }
        if not required.issubset(set(decision_types)):
            raise ValueError(
                "assessment draft must explain starting volume and benchmark scheduling"
            )
        return self
