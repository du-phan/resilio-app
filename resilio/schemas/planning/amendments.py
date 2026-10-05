"""Exact, reviewable amendments to the remaining weeks of one race cycle."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning.weeks import WeekPlan


class MacroAmendmentProposal(BaseModel):
    schema_version: Literal[1] = 1
    expected_active_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    weeks: list[WeekPlan] = Field(min_length=1)
    planning_context_references: list[EvidenceArtifactReference] = Field(min_length=1)
    rationale: str = Field(min_length=40, max_length=4_000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def amendment_contains_only_unique_skeletons(self) -> "MacroAmendmentProposal":
        numbers = [week.week_number for week in self.weeks]
        if len(numbers) != len(set(numbers)):
            raise ValueError("amendment week numbers must be unique")
        if any(week.running_workouts for week in self.weeks):
            raise ValueError(
                "macro amendments contain skeletons; exact workouts require weekly approval"
            )
        if len(self.planning_context_references) != len(self.weeks):
            raise ValueError("each amended week requires its own planning context")
        if any(
            ref.artifact_type != "week_planning_context" for ref in self.planning_context_references
        ):
            raise ValueError("macro amendments require week-planning contexts")
        return self


class MacroAmendmentValidation(BaseModel):
    file_sha256: str
    amended_week_numbers: list[int]
    retired_week_numbers: list[int]

    model_config = ConfigDict(extra="forbid")
