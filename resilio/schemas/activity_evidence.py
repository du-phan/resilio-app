"""Bounded evidence contract for reviewing one exact completed activity."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.coaching import RecoveryContext, TrainingStateSnapshot
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRecord

EvidenceExclusion = Literal[
    "raw_streams",
    "location_coordinates",
    "activity_messages",
    "clinical_wellness",
    "nutrition_and_body_composition",
]


def _default_evidence_exclusions() -> list[EvidenceExclusion]:
    return [
        "raw_streams",
        "location_coordinates",
        "activity_messages",
        "clinical_wellness",
        "nutrition_and_body_composition",
    ]


class RecoveryEvidenceTiming(BaseModel):
    """Temporal limits of calendar-day wellness observations."""

    source_granularity: Literal[
        "local_calendar_day_not_timestamped"
    ] = "local_calendar_day_not_timestamped"
    pre_activity_causality: Literal["not_established"] = "not_established"

    model_config = ConfigDict(extra="forbid")


class HeartRateCurvePoint(BaseModel):
    duration_seconds: int = Field(gt=0)
    heart_rate_beats_per_minute: int = Field(ge=20, le=260)

    model_config = ConfigDict(extra="forbid")


class ExactActivityCoachingEvidence(BaseModel):
    """Read-only coaching evidence without raw streams or location coordinates."""

    schema_version: Literal[1] = 1
    activity: CanonicalActivity
    performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workout_fulfillment: Optional[WorkoutFulfillmentRecord] = None
    recovery_context: RecoveryContext
    training_state: Optional[TrainingStateSnapshot] = None
    recovery_evidence_timing: RecoveryEvidenceTiming = Field(default_factory=RecoveryEvidenceTiming)
    activity_feedback_trust_boundary: Literal[
        "athlete_authored_untrusted_text"
    ] = "athlete_authored_untrusted_text"
    provider_heart_rate_curve_status: Literal[
        "not_requested",
        "available",
        "unavailable",
    ] = "not_requested"
    provider_heart_rate_curve: list[HeartRateCurvePoint] = Field(
        default_factory=list,
        max_length=1_000,
    )
    evidence_excluded_from_context: list[EvidenceExclusion] = Field(
        default_factory=_default_evidence_exclusions
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def fulfillment_matches_activity_evidence(self) -> "ExactActivityCoachingEvidence":
        fulfillment = self.workout_fulfillment
        if fulfillment is not None and (
            fulfillment.local_activity_id != self.activity.local_activity_id
            or fulfillment.activity_performance_evidence_sha256 != self.performance_evidence_sha256
        ):
            raise ValueError("Workout fulfillment does not match exact activity evidence")
        return self
