"""Exact weekly proposal and application-result contracts."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.plan import WorkoutPrescription
from resilio.schemas.publication import RunWeekSynchronizationReport


class WeekApplication(BaseModel):
    """Approved exact workouts for one existing plan week."""

    week_number: int = Field(ge=1)
    workouts: list[WorkoutPrescription] = Field(min_length=1)
    adjustment_rationale: str = Field(min_length=40, max_length=4_000)

    model_config = ConfigDict(extra="forbid")


class RunSynchronizationError(BaseModel):
    error_type: str = Field(min_length=1)
    message: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class AppliedWeekResult(BaseModel):
    """Local commit result plus independent downstream synchronization outcome."""

    plan_id: str
    plan_revision_id: str
    week_number: int = Field(ge=1)
    applied_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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
