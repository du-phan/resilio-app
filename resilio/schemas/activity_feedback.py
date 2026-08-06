"""Athlete feedback contracts for completed activities."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class SubjectiveEffortProvenance(str, Enum):
    INTERVALS_ACTIVITY_FIELD = "intervals_activity_field"
    RESILIO_ATHLETE_INPUT = "resilio_athlete_input"


class SubjectiveSessionEffort(BaseModel):
    """Subjective effort kept separate from provider aerobic load points."""

    rpe_1_to_10: float = Field(ge=1, le=10, allow_inf_nan=False)
    session_rpe_load_au: Optional[NonNegativeFloat] = None
    session_rpe_duration_basis: Optional[Literal["provider_defined", "elapsed_time"]] = None
    provenance: SubjectiveEffortProvenance
    is_athlete_confirmed: bool

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def load_requires_duration_basis(self) -> "SubjectiveSessionEffort":
        if (self.session_rpe_load_au is None) != (self.session_rpe_duration_basis is None):
            raise ValueError("session RPE load and duration basis must be provided together")
        return self


class ActivityFeelObservation(BaseModel):
    """Intervals.icu Feel value; one is strongest and five is weakest."""

    value_1_to_5: int = Field(ge=1, le=5)
    scale_direction: Literal["lower_is_better"] = "lower_is_better"
    strongest_value: Literal[1] = 1
    weakest_value: Literal[5] = 5

    model_config = ConfigDict(extra="forbid")


class ActivityFeedback(BaseModel):
    """Provider-owned feedback plus separately athlete-owned local notes."""

    provider_description: Optional[str] = None
    local_private_note: Optional[str] = None
    subjective_effort: Optional[SubjectiveSessionEffort] = None
    feel: Optional[ActivityFeelObservation] = None

    model_config = ConfigDict(extra="forbid")
