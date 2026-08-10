"""Immutable race-macro and baseline-assessment plan contracts."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryScheduleConstraint,
    TimedBenchmarkIntent,
)
from resilio.schemas.methodology import MethodologySelection
from resilio.schemas.plan_history import (
    EvidenceArtifactReference,
    PlanAdaptationDecision,
    PlanAdaptationDecisionType,
)
from resilio.schemas.planning.constraints import PlanningConstraintsSnapshot
from resilio.schemas.planning.weeks import PlanPhase, WeekPlan
from resilio.schemas.planning.workouts import WorkoutType
from resilio.schemas.profile import GoalType
from resilio.schemas.vdot import RaceDistance


class PlanSchemaDescriptor(BaseModel):
    name: Literal["resilio.plan"] = "resilio.plan"
    version: Literal[5] = 5

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
    """Fields and invariants shared by every run-plan lifecycle."""

    schema_info: PlanSchemaDescriptor = Field(
        default_factory=PlanSchemaDescriptor,
        validation_alias="_schema",
        serialization_alias="_schema",
    )
    id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    plan_revision_id: str = Field(pattern=r"^plan_revision_[a-f0-9]{16}$")
    planning_context_reference: EvidenceArtifactReference
    planning_inputs_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    planning_rationale: str = Field(min_length=40, max_length=4_000)
    adaptation_decisions: list[PlanAdaptationDecision] = Field(min_length=2)
    weeks: list[WeekPlan] = Field(min_length=1)
    constraints_snapshot: PlanningConstraintsSnapshot

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
        week_numbers = [week.week_number for week in self.weeks]
        if week_numbers != list(range(1, len(self.weeks) + 1)):
            raise ValueError("plan weeks must be stored in week-number order starting at one")
        for previous, current in zip(self.weeks, self.weeks[1:]):
            if current.start_date != previous.end_date + timedelta(days=1):
                raise ValueError("plan weeks must be contiguous")
        workout_ids = [workout.id for week in self.weeks for workout in week.running_workouts]
        if len(workout_ids) != len(set(workout_ids)):
            raise ValueError("running workout IDs must be unique across the plan")
        decision_types = [str(decision.decision_type) for decision in self.adaptation_decisions]
        if len(decision_types) != len(set(decision_types)):
            raise ValueError("plan adaptation decision types must be unique")
        return self

    @property
    def start_date(self) -> date:
        return self.weeks[0].start_date

    @property
    def end_date(self) -> date:
        return self.weeks[-1].end_date

    @property
    def total_weeks(self) -> int:
        return len(self.weeks)

    @property
    def starting_run_volume_meters(self) -> float:
        return self.weeks[0].target_run_volume_meters

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
            week.workout_structure_hints.intensity_distribution is not None for week in self.weeks
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


def validate_assessment_week_structure(
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
    temporary_schedule_constraints: list[TemporaryScheduleConstraint] = Field(default_factory=list)
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
        validate_assessment_week_structure(self.weeks, intent)
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
        benchmarks = [
            workout
            for week in self.weeks
            for workout in week.running_workouts
            if workout.workout_type == WorkoutType.BENCHMARK.value
        ]
        if len(benchmarks) > 1:
            raise ValueError("assessment plan can contain only one benchmark workout")
        if benchmarks:
            benchmark = benchmarks[0]
            if not intent.fallback_window_start <= benchmark.date <= intent.fallback_window_end:
                raise ValueError("benchmark workout must fall within its approved window")
            timed_step = benchmark.structured_workout.timed_distance_steps()[0]
            expected_distance_meters = RaceDistance(intent.race_distance).distance_meters
            if abs(timed_step.distance_meters - expected_distance_meters) > 0.01:
                raise ValueError("benchmark timed-distance step must match its approved distance")
        for week in self.weeks:
            for workout in week.running_workouts:
                if any(
                    constraint.contains(workout.date)
                    for constraint in self.temporary_schedule_constraints
                ):
                    raise ValueError("running workout falls in a temporary unavailable date range")
        return self


TrainingPlan = Annotated[
    RaceMacroPlan | BaselineAssessmentPlan,
    Field(discriminator="kind"),
]
