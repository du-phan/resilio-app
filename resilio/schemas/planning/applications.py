"""Exact weekly proposal and application-result contracts."""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.activity import SportType, is_running_sport
from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning.workouts import RunningWorkoutPrescription
from resilio.schemas.publication import RunWeekSynchronizationReport


class OtherSportRunPlanEffect(str, Enum):
    RUN_VOLUME = "run_volume"
    RUN_FREQUENCY = "run_frequency"
    RUN_INTENSITY = "run_intensity"
    RUN_DAY_PLACEMENT = "run_day_placement"
    RECOVERY_SPACING = "recovery_spacing"
    NO_ADJUSTMENT = "no_adjustment"


class OtherSportPlanningConsideration(BaseModel):
    """Auditable treatment of one observed or expected athlete-managed sport."""

    sport_name: str = Field(min_length=1)
    recent_activity_ids: list[str] = Field(default_factory=list)
    effects_on_running_plan: list[OtherSportRunPlanEffect] = Field(min_length=1)
    rationale: str = Field(min_length=20, max_length=2_000)
    uncertainty_or_limitation: str | None = Field(default=None, max_length=1_000)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("sport_name")
    @classmethod
    def sport_is_canonical_non_run(cls, value: str) -> str:
        try:
            sport = SportType(value.strip().casefold())
        except ValueError as exc:
            raise ValueError("considered sport must be a canonical Resilio sport type") from exc
        if is_running_sport(sport):
            raise ValueError("other-sport consideration cannot reference running")
        return sport.value

    @model_validator(mode="after")
    def effects_are_coherent(self) -> "OtherSportPlanningConsideration":
        if len(self.recent_activity_ids) != len(set(self.recent_activity_ids)):
            raise ValueError("recent_activity_ids must be unique")
        if len(self.effects_on_running_plan) != len(set(self.effects_on_running_plan)):
            raise ValueError("effects_on_running_plan must be unique")
        if (
            OtherSportRunPlanEffect.NO_ADJUSTMENT.value in self.effects_on_running_plan
            and len(self.effects_on_running_plan) != 1
        ):
            raise ValueError("no_adjustment cannot be combined with another run-plan effect")
        return self


class WeekApplication(BaseModel):
    """Approved exact running workouts for one existing plan week."""

    schema_version: Literal[2] = 2
    week_number: int = Field(ge=1)
    planning_context_reference: EvidenceArtifactReference
    running_workouts: list[RunningWorkoutPrescription] = Field(min_length=1)
    other_sport_considerations: list[OtherSportPlanningConsideration]
    adjustment_rationale: str = Field(min_length=40, max_length=4_000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def consideration_sports_are_unique(self) -> "WeekApplication":
        if self.planning_context_reference.artifact_type != "week_planning_context":
            raise ValueError("weekly proposal requires week-planning context evidence")
        sports = [item.sport_name for item in self.other_sport_considerations]
        if len(sports) != len(set(sports)):
            raise ValueError("other-sport considerations must be unique by sport")
        return self


class RunSynchronizationError(BaseModel):
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class AppliedWeekResult(BaseModel):
    """Local commit result plus independent downstream synchronization outcome."""

    plan_id: str
    plan_revision_id: str
    week_number: int = Field(ge=1)
    applied_running_workouts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_application_status: Literal["applied"] = "applied"
    run_synchronization_status: Literal[
        "disabled",
        "synchronized",
        "blocked",
        "failed",
    ]
    run_synchronization_report: Optional[RunWeekSynchronizationReport] = None
    run_synchronization_error: Optional[RunSynchronizationError] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def synchronization_evidence_matches_status(self) -> "AppliedWeekResult":
        if self.run_synchronization_status == "disabled":
            if self.run_synchronization_report or self.run_synchronization_error:
                raise ValueError("disabled synchronization cannot include an outcome")
        elif self.run_synchronization_status == "failed":
            if self.run_synchronization_error is None:
                raise ValueError("failed synchronization requires a typed error")
        else:
            if self.run_synchronization_report is None:
                raise ValueError("synchronization outcome requires a report")
            if self.run_synchronization_error is not None:
                raise ValueError("successful or blocked synchronization has no error")
        return self
