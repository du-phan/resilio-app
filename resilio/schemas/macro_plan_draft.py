"""Coach-authored race-macro proposal before repository identity assignment."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.methodology import MethodologyChoice
from resilio.schemas.plan_history import (
    EvidenceArtifactReference,
    PlanAdaptationDecision,
    PlanAdaptationDecisionType,
)
from resilio.schemas.planning.plans import PlanGoal
from resilio.schemas.planning.weeks import WeekPlan


class MacroPlanDraft(BaseModel):
    """Methodology-explicit race plan skeleton awaiting creation and approval."""

    goal: PlanGoal
    methodology: MethodologyChoice
    weeks: list[WeekPlan] = Field(min_length=1)
    vdot_approval_id: str = Field(pattern=r"^vdot_approval_[a-f0-9]{16}$")
    planning_context_reference: EvidenceArtifactReference
    planning_rationale: str = Field(min_length=40, max_length=4_000)
    adaptation_decisions: list[PlanAdaptationDecision] = Field(min_length=2)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def macro_weeks_are_unpopulated(self) -> "MacroPlanDraft":
        if any(week.running_workouts for week in self.weeks):
            raise ValueError("macro plan weeks must not contain exact workouts")
        if self.planning_context_reference.artifact_type != "macro_planning_context":
            raise ValueError("macro draft requires macro-planning context evidence")
        decision_types = [str(decision.decision_type) for decision in self.adaptation_decisions]
        if len(decision_types) != len(set(decision_types)):
            raise ValueError("macro draft adaptation decision types must be unique")
        required = {
            PlanAdaptationDecisionType.METHODOLOGY_SELECTION.value,
            PlanAdaptationDecisionType.STARTING_VOLUME.value,
        }
        if not required.issubset(set(decision_types)):
            raise ValueError("macro draft must explain methodology and starting-volume decisions")
        return self
