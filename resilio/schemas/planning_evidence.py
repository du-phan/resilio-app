"""Typed retrospective evidence used to close and renew training plans."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.coaching import (
    ActivityContext,
    SportExposure,
    WeeklyCoachContext,
)
from resilio.schemas.plan import PlanGoal, PlanningConstraintsSnapshot
from resilio.schemas.plan_history import (
    AthleteConfirmedGoalActivityEvidence,
    EvidenceArtifactReference,
    GoalOutcome,
    OwnedCompletionGoalEvidence,
    PlanClosureDisposition,
)
from resilio.schemas.profile import Goal as AthleteGoal


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
    macro_revision_id: str = Field(pattern=r"^macro_revision_[a-f0-9]{16}$")
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
    macro_revision_id: str
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


class PlanningEvidencePointer(BaseModel):
    """Stable identifier that a macro-planning decision can cite."""

    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,159}$")
    category: Literal[
        "profile",
        "vdot",
        "recent_week",
        "closed_plan",
        "goal_outcome",
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
