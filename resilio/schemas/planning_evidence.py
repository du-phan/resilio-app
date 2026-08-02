"""Typed retrospective evidence used to close and renew training plans."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryOtherSportCommitmentOverride,
    TemporaryScheduleConstraint,
    TimedBenchmarkIntent,
)
from resilio.schemas.coaching import (
    ActivityContext,
    SportExposure,
    WeeklyCoachContext,
)
from resilio.schemas.plan import (
    PlanGoal,
    PlanningConstraintsSnapshot,
)
from resilio.schemas.plan_history import (
    AthleteConfirmedGoalActivityEvidence,
    BaselineAssessmentResult,
    EvidenceArtifactReference,
    GoalOutcome,
    OwnedCompletionGoalEvidence,
    PlanClosureDisposition,
    PlanWorkoutIdentity,
)
from resilio.schemas.profile import Goal as AthleteGoal
from resilio.schemas.vdot import RaceDistance


class CompactTrainingWeek(BaseModel):
    """Lossless key totals for one reviewed Monday-Sunday training week."""

    week_start: date
    week_end: date
    evidence_as_of_date: date
    adherence_status: Literal["available", "no_plan", "unavailable"]
    due_planned_workout_count: int = Field(ge=0)
    verified_completed_workout_count: int = Field(ge=0)
    due_unmatched_workout_count: int = Field(ge=0)
    actual_run_count: int = Field(ge=0)
    actual_run_distance_km: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    actual_run_elapsed_duration_seconds: int = Field(ge=0)
    actual_other_sport_exposure: list[SportExposure] = Field(default_factory=list)
    source_coverage_status: Literal[
        "complete",
        "complete_with_declared_exclusions",
        "incomplete",
        "unavailable",
    ]
    limitation: str | None = Field(default=None, max_length=1_000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def dates_are_one_coherent_week(self) -> "CompactTrainingWeek":
        if self.week_start.weekday() != 0:
            raise ValueError("compact training week must start on Monday")
        if (self.week_end - self.week_start).days != 6:
            raise ValueError("compact training week must end on Sunday")
        if not self.week_start <= self.evidence_as_of_date <= self.week_end:
            raise ValueError("weekly evidence date must fall within the week")
        return self


class PlanCycleTotals(BaseModel):
    """Plan and execution totals kept separate to avoid false equivalence."""

    planned_week_count: int = Field(ge=1)
    reviewed_week_count: int = Field(ge=0)
    planned_target_run_volume_meters: float = Field(
        ge=0,
        allow_inf_nan=False,
    )
    due_planned_workout_count: int = Field(ge=0)
    verified_completed_workout_count: int = Field(ge=0)
    due_unmatched_workout_count: int = Field(ge=0)
    actual_run_count: int = Field(ge=0)
    actual_run_distance_km: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    actual_run_elapsed_duration_seconds: int = Field(ge=0)
    incomplete_source_coverage_week_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class PlanCycleReview(BaseModel):
    """Immutable, coverage-aware review of one exact active plan revision."""

    schema_version: Literal[1] = 1
    plan_id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    plan_revision_id: str = Field(pattern=r"^plan_revision_[a-f0-9]{16}$")
    plan_start_date: date
    planned_end_date: date
    effective_end_date: date
    evidence_as_of_date: date
    generated_at_utc: datetime
    plan_started: bool
    active_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    goal_outcome: GoalOutcome
    goal_activity: ActivityContext | None = None
    totals: PlanCycleTotals
    compact_weeks: list[CompactTrainingWeek] = Field(max_length=52)
    recent_detailed_weeks: list[WeeklyCoachContext] = Field(max_length=12)
    source_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_limitations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at_utc")
    @classmethod
    def generated_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def review_window_is_coherent(self) -> "PlanCycleReview":
        if self.plan_start_date.weekday() != 0:
            raise ValueError("reviewed plan must start on Monday")
        if self.planned_end_date < self.plan_start_date:
            raise ValueError("planned end date cannot precede plan start")
        if self.effective_end_date > self.planned_end_date:
            raise ValueError("effective end date cannot follow the planned horizon")
        if self.evidence_as_of_date < self.effective_end_date:
            raise ValueError("review evidence cannot end before the effective plan end")
        if self.plan_started != bool(self.compact_weeks):
            raise ValueError("plan_started must reflect whether reviewed plan weeks exist")
        if self.totals.reviewed_week_count != len(self.compact_weeks):
            raise ValueError("reviewed week total must match compact week evidence")
        if len(self.recent_detailed_weeks) > len(self.compact_weeks):
            raise ValueError("detailed review weeks must be a subset of compact weeks")
        evidence = self.goal_outcome.evidence
        exact_activity_evidence = isinstance(
            evidence,
            (
                AthleteConfirmedGoalActivityEvidence,
                OwnedCompletionGoalEvidence,
            ),
        )
        if exact_activity_evidence != (self.goal_activity is not None):
            raise ValueError("goal activity summary must match exact goal outcome evidence")
        if (
            self.goal_activity is not None
            and isinstance(
                evidence,
                (
                    AthleteConfirmedGoalActivityEvidence,
                    OwnedCompletionGoalEvidence,
                ),
            )
            and self.goal_activity.local_activity_id != evidence.local_activity_id
        ):
            raise ValueError("goal activity summary must match the goal evidence identity")
        return self


class HistoricalPlanSummary(BaseModel):
    """Bounded plan-level evidence retained for every closed cycle."""

    plan_id: str
    plan_revision_id: str
    plan_start_date: date
    planned_end_date: date
    effective_end_date: date
    methodology_identifier: str
    goal: PlanGoal
    goal_outcome: GoalOutcome
    goal_activity: ActivityContext | None = None
    closure_disposition: PlanClosureDisposition
    totals: PlanCycleTotals
    cycle_review_reference: EvidenceArtifactReference

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def goal_activity_matches_outcome(self) -> "HistoricalPlanSummary":
        evidence = self.goal_outcome.evidence
        exact_activity_evidence = isinstance(
            evidence,
            (
                AthleteConfirmedGoalActivityEvidence,
                OwnedCompletionGoalEvidence,
            ),
        )
        if exact_activity_evidence != (self.goal_activity is not None):
            raise ValueError("historical goal activity must match exact outcome evidence")
        if (
            self.goal_activity is not None
            and isinstance(
                evidence,
                (
                    AthleteConfirmedGoalActivityEvidence,
                    OwnedCompletionGoalEvidence,
                ),
            )
            and self.goal_activity.local_activity_id != evidence.local_activity_id
        ):
            raise ValueError("historical goal activity must match the outcome identity")
        return self


class AssessmentPlanningContext(BaseModel):
    """Immutable evidence gate for a short baseline-assessment plan."""

    schema_version: Literal[1] = 1
    evidence_as_of_date: date
    intended_plan_start_date: date
    generated_at_utc: datetime
    planning_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_goal: AthleteGoal
    current_constraints: PlanningConstraintsSnapshot
    assessment_reasons: list[AssessmentReason] = Field(min_length=1)
    temporary_schedule_constraints: list[TemporaryScheduleConstraint] = Field(
        default_factory=list
    )
    temporary_other_sport_commitment_overrides: list[
        TemporaryOtherSportCommitmentOverride
    ] = Field(default_factory=list)
    recent_detailed_weeks: list[WeeklyCoachContext] = Field(min_length=1, max_length=12)
    evidence_index: list["PlanningEvidencePointer"] = Field(min_length=2)
    source_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("generated_at_utc")
    @classmethod
    def context_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def context_window_and_evidence_are_coherent(self) -> "AssessmentPlanningContext":
        if self.intended_plan_start_date.weekday() != 0:
            raise ValueError("intended assessment start date must be a Monday")
        if self.intended_plan_start_date <= self.evidence_as_of_date:
            raise ValueError("intended assessment start must follow the evidence date")
        if len(self.assessment_reasons) != len(set(self.assessment_reasons)):
            raise ValueError("assessment context reasons must be unique")
        evidence_ids = [pointer.evidence_id for pointer in self.evidence_index]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("assessment context evidence IDs must be unique")
        schedule_evidence_present = (
            "assessment.temporary_schedule_constraints" in evidence_ids
        )
        if schedule_evidence_present != bool(self.temporary_schedule_constraints):
            raise ValueError(
                "assessment schedule evidence pointer must match temporary constraints"
            )
        sport_override_evidence_present = (
            "assessment.temporary_other_sport_commitment_overrides" in evidence_ids
        )
        if sport_override_evidence_present != bool(
            self.temporary_other_sport_commitment_overrides
        ):
            raise ValueError(
                "assessment sport-override evidence pointer must match temporary overrides"
            )
        override_keys = [
            (override.week_start_date, override.sport_name)
            for override in self.temporary_other_sport_commitment_overrides
        ]
        if len(override_keys) != len(set(override_keys)):
            raise ValueError(
                "assessment sport overrides must be unique by week and sport"
            )
        active_sport_names = {
            commitment.sport_name
            for commitment in self.current_constraints.active_other_sports
        }
        for override in self.temporary_other_sport_commitment_overrides:
            if override.sport_name not in active_sport_names:
                raise ValueError("assessment override references an inactive other sport")
            if override.week_start_date < self.intended_plan_start_date:
                raise ValueError("assessment sport override predates the intended plan")
        return self


class BaselineAssessmentReview(BaseModel):
    """Immutable athlete-confirmed result for one owned assessment benchmark."""

    schema_version: Literal[1] = 1
    plan_id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    plan_revision_id: str = Field(pattern=r"^plan_revision_[a-f0-9]{16}$")
    plan_start_date: date
    planned_end_date: date
    evidence_as_of_date: date
    generated_at_utc: datetime
    active_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    benchmark_intent: TimedBenchmarkIntent
    benchmark_workout_identity: PlanWorkoutIdentity
    result: BaselineAssessmentResult
    review_summary: str = Field(min_length=40, max_length=2_000)
    source_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at_utc")
    @classmethod
    def review_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def result_and_plan_lineage_are_coherent(self) -> "BaselineAssessmentReview":
        identity = self.benchmark_workout_identity
        if identity.plan_id != self.plan_id or identity.plan_revision_id != self.plan_revision_id:
            raise ValueError("benchmark workout identity references another assessment plan")
        if self.result.workout_identity != identity:
            raise ValueError("assessment result must reference the benchmark workout")
        if self.result.race_distance != self.benchmark_intent.race_distance:
            raise ValueError("assessment result distance must match the benchmark intent")
        if not self.plan_start_date <= self.result.performance_date <= self.planned_end_date:
            raise ValueError("assessment result date must fall within the plan horizon")
        if self.evidence_as_of_date < self.result.performance_date:
            raise ValueError("assessment evidence date cannot predate the result")
        return self


class AssessmentResultCandidate(BaseModel):
    """One explicit result selection from an ownership-paired activity."""

    candidate_id: str = Field(min_length=5, max_length=300)
    result_kind: Literal["dedicated_activity", "exact_segment"]
    workout_identity: PlanWorkoutIdentity
    local_activity_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    canonical_activity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_activity_fingerprint_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    race_distance: RaceDistance
    performance_date: date
    performance_timezone: str = Field(min_length=1)
    measured_distance_meters: float = Field(gt=0, allow_inf_nan=False)
    elapsed_time_seconds: int = Field(gt=0)
    segment_index: int | None = Field(default=None, ge=1)
    segment_start_time_utc: datetime | None = None
    segment_start_time_local: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def segment_fields_match_candidate_kind(self) -> "AssessmentResultCandidate":
        is_segment = self.result_kind == "exact_segment"
        if is_segment != (self.segment_index is not None):
            raise ValueError("segment candidate kind must match segment identity")
        return self


class HistoricalAssessmentSummary(BaseModel):
    """Bounded latest-baseline evidence retained for future macro planning."""

    plan_id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    plan_revision_id: str = Field(pattern=r"^plan_revision_[a-f0-9]{16}$")
    plan_start_date: date
    planned_end_date: date
    benchmark_intent: TimedBenchmarkIntent
    result: BaselineAssessmentResult
    assessment_review_reference: EvidenceArtifactReference

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def review_reference_has_assessment_type(self) -> "HistoricalAssessmentSummary":
        if self.assessment_review_reference.artifact_type != "assessment_review":
            raise ValueError("assessment summary requires assessment-review evidence")
        return self


class PlanningEvidencePointer(BaseModel):
    """Stable identifier that a macro-planning decision can cite."""

    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,159}$")
    category: Literal[
        "profile",
        "vdot",
        "recent_week",
        "closed_plan",
        "goal_outcome",
        "assessment_result",
        "schedule_constraint",
        "coverage_limitation",
    ]
    description: str = Field(min_length=20, max_length=500)
    artifact_reference: EvidenceArtifactReference | None = None

    model_config = ConfigDict(extra="forbid")


class MacroPlanningContext(BaseModel):
    """Bounded, immutable evidence package required for a new macro plan."""

    schema_version: Literal[1] = 1
    evidence_as_of_date: date
    intended_plan_start_date: date
    generated_at_utc: datetime
    planning_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_goal: AthleteGoal
    current_constraints: PlanningConstraintsSnapshot
    active_vdot_approval_id: str = Field(
        pattern=r"^vdot_approval_[a-f0-9]{16}$",
    )
    historical_plan_summaries: list[HistoricalPlanSummary]
    historical_assessment_summaries: list[HistoricalAssessmentSummary]
    historical_compact_weeks: list[CompactTrainingWeek] = Field(max_length=52)
    recent_detailed_weeks: list[WeeklyCoachContext] = Field(max_length=12)
    evidence_index: list[PlanningEvidencePointer] = Field(min_length=2)
    source_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at_utc")
    @classmethod
    def context_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def future_plan_and_evidence_index_are_coherent(
        self,
    ) -> "MacroPlanningContext":
        if self.intended_plan_start_date.weekday() != 0:
            raise ValueError("intended plan start date must be a Monday")
        if self.intended_plan_start_date <= self.evidence_as_of_date:
            raise ValueError("intended plan start date must be after the evidence date")
        evidence_ids = [pointer.evidence_id for pointer in self.evidence_index]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("macro context evidence IDs must be unique")
        if (
            self.current_goal.target_date is not None
            and self.current_goal.target_date < self.intended_plan_start_date
        ):
            raise ValueError("current goal must not predate the new plan")
        return self


AssessmentPlanningContext.model_rebuild()
