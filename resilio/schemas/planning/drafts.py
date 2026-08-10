"""Coach-authored planning drafts before repository identity assignment."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryScheduleConstraint,
    TimedBenchmarkIntent,
)
from resilio.schemas.plan_history import EvidenceArtifactReference, PlanAdaptationDecision
from resilio.schemas.planning.plans import validate_assessment_week_structure
from resilio.schemas.planning.weeks import WeekPlan


class AssessmentPlanDraft(BaseModel):
    """Coach-authored assessment block before repository identity is assigned."""

    weeks: list[WeekPlan] = Field(min_length=1)
    planning_context_reference: EvidenceArtifactReference
    planning_rationale: str = Field(min_length=40, max_length=4_000)
    adaptation_decisions: list[PlanAdaptationDecision] = Field(min_length=2)
    assessment_reasons: list[AssessmentReason] = Field(min_length=1)
    benchmark_intent: TimedBenchmarkIntent
    temporary_schedule_constraints: list[TemporaryScheduleConstraint] = Field(default_factory=list)
    medical_rehabilitation_excluded: Literal[True] = True

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def assessment_weeks_are_unpopulated(self) -> "AssessmentPlanDraft":
        if any(week.running_workouts for week in self.weeks):
            raise ValueError("assessment plan weeks must not contain exact running workouts")
        if self.planning_context_reference.artifact_type != "assessment_planning_context":
            raise ValueError("assessment draft requires assessment-planning context evidence")
        if len(self.assessment_reasons) != len(set(self.assessment_reasons)):
            raise ValueError("assessment reasons must be unique")
        validate_assessment_week_structure(self.weeks, self.benchmark_intent)
        decision_types = [str(decision.decision_type) for decision in self.adaptation_decisions]
        if len(decision_types) != len(set(decision_types)):
            raise ValueError("assessment draft adaptation decision types must be unique")
        required = {"starting_volume", "benchmark_scheduling"}
        if not required.issubset(set(decision_types)):
            raise ValueError(
                "assessment draft must explain starting volume and benchmark scheduling"
            )
        return self
