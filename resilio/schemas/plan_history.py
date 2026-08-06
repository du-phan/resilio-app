"""Immutable plan-history, workout-lineage, and closure contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.vdot import RaceDistance


class PlanWorkoutIdentity(BaseModel):
    """A workout identity qualified by the immutable plan lineage that owns it."""

    plan_id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    plan_revision_id: str = Field(pattern=r"^plan_revision_[a-f0-9]{16}$")
    week_number: int = Field(ge=1)
    local_workout_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )

    model_config = ConfigDict(extra="forbid")


class EvidenceArtifactReference(BaseModel):
    """Reference to immutable, managed JSON bytes."""

    artifact_type: Literal[
        "cycle_review",
        "macro_planning_context",
        "assessment_planning_context",
        "assessment_review",
    ]
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class PlanClosureDisposition(str, Enum):
    COMPLETED_HORIZON = "completed_horizon"
    SUPERSEDED_MIDCYCLE = "superseded_midcycle"
    STOPPED_EARLY = "stopped_early"
    NEVER_STARTED = "never_started"
    MIGRATED_UNCLASSIFIED = "migrated_unclassified"


class OwnedCompletionGoalEvidence(BaseModel):
    evidence_kind: Literal["owned_workout_completion"] = "owned_workout_completion"
    workout_identity: PlanWorkoutIdentity
    local_activity_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class AthleteConfirmedGoalActivityEvidence(BaseModel):
    evidence_kind: Literal[
        "athlete_confirmed_canonical_activity"
    ] = "athlete_confirmed_canonical_activity"
    local_activity_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    athlete_confirmation_reference: str = Field(min_length=10, max_length=1_000)

    model_config = ConfigDict(extra="forbid")


class GoalOutcomeUnavailableEvidence(BaseModel):
    evidence_kind: Literal["unavailable"] = "unavailable"
    reason: str = Field(min_length=10, max_length=1_000)

    model_config = ConfigDict(extra="forbid")


GoalActivityEvidence = Annotated[
    OwnedCompletionGoalEvidence
    | AthleteConfirmedGoalActivityEvidence
    | GoalOutcomeUnavailableEvidence,
    Field(discriminator="evidence_kind"),
]


class GoalOutcome(BaseModel):
    """Athlete-confirmed goal disposition without inferred race matching."""

    status: Literal[
        "completed",
        "did_not_start",
        "did_not_finish",
        "cancelled",
        "deferred",
        "not_applicable",
        "unverified",
    ]
    evidence: GoalActivityEvidence | None = None
    athlete_confirmation_reference: str | None = Field(
        default=None,
        min_length=10,
        max_length=1_000,
    )
    notes: str | None = Field(default=None, max_length=2_000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def evidence_matches_status(self) -> "GoalOutcome":
        if self.status != "unverified" and self.athlete_confirmation_reference is None:
            raise ValueError("confirmed goal outcome requires athlete confirmation")
        if self.status == "completed":
            if self.evidence is None or isinstance(
                self.evidence,
                GoalOutcomeUnavailableEvidence,
            ):
                raise ValueError("completed goal outcome requires exact activity evidence")
        elif self.status == "did_not_finish":
            if isinstance(self.evidence, GoalOutcomeUnavailableEvidence):
                raise ValueError(
                    "did-not-finish outcome accepts exact activity evidence or no activity"
                )
        elif self.status == "unverified":
            if not isinstance(self.evidence, GoalOutcomeUnavailableEvidence):
                raise ValueError("unverified goal outcome requires unavailable evidence")
        elif self.evidence is not None:
            raise ValueError(f"{self.status} goal outcome cannot contain activity evidence")
        return self


class PlanClosure(BaseModel):
    """Final plan lifecycle facts bound to one exact cycle-review artifact."""

    closure_kind: Literal["race_cycle"] = "race_cycle"
    disposition: PlanClosureDisposition
    effective_end_date: date
    reason: str = Field(min_length=20, max_length=2_000)
    athlete_confirmation_reference: str = Field(min_length=10, max_length=1_000)
    cycle_review_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    goal_outcome: GoalOutcome
    closed_at_utc: datetime
    provenance: Literal["recorded", "migrated"] = "recorded"

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("closed_at_utc")
    @classmethod
    def closure_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("closed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def recorded_closure_has_resolved_outcome(self) -> "PlanClosure":
        if self.provenance == "recorded" and self.goal_outcome.status == "unverified":
            raise ValueError("recorded closure cannot leave the goal outcome unverified")
        if (
            self.provenance == "recorded"
            and self.disposition == PlanClosureDisposition.MIGRATED_UNCLASSIFIED
        ):
            raise ValueError("recorded closure cannot use a migrated disposition")
        return self


class BaselineAssessmentResultBase(BaseModel):
    """Immutable facts shared by activity and exact-segment assessment results."""

    workout_identity: PlanWorkoutIdentity
    local_activity_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    race_distance: RaceDistance
    performance_date: date
    performance_timezone: str = Field(min_length=1)
    measured_distance_meters: float = Field(gt=0, allow_inf_nan=False)
    elapsed_time_seconds: int = Field(gt=0)
    official_distance_confirmation_reference: str = Field(
        min_length=10,
        max_length=1_000,
    )
    athlete_confirmation_reference: str = Field(min_length=10, max_length=1_000)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("performance_timezone")
    @classmethod
    def performance_timezone_is_iana(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("performance_timezone must be a recognized IANA timezone") from exc
        return value


class DedicatedActivityAssessmentResult(BaselineAssessmentResultBase):
    result_kind: Literal["dedicated_activity"] = "dedicated_activity"


class ExactSegmentAssessmentResult(BaselineAssessmentResultBase):
    result_kind: Literal["exact_segment"] = "exact_segment"
    segment_index: int = Field(ge=1)
    segment_start_time_utc: datetime | None = None
    segment_start_time_local: datetime | None = None

    @field_validator("segment_start_time_utc", "segment_start_time_local")
    @classmethod
    def segment_times_are_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("segment timestamps must be timezone-aware")
        return value


BaselineAssessmentResult = Annotated[
    DedicatedActivityAssessmentResult | ExactSegmentAssessmentResult,
    Field(discriminator="result_kind"),
]


class AssessmentClosure(BaseModel):
    """Final assessment lifecycle facts bound to one immutable review."""

    closure_kind: Literal["baseline_assessment"] = "baseline_assessment"
    effective_end_date: date
    reason: str = Field(min_length=20, max_length=2_000)
    athlete_confirmation_reference: str = Field(min_length=10, max_length=1_000)
    assessment_review_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    closed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("closed_at_utc")
    @classmethod
    def closure_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("closed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


PlanLifecycleClosure = Annotated[
    PlanClosure | AssessmentClosure,
    Field(discriminator="closure_kind"),
]


class ClosedPlanReference(BaseModel):
    """Integrity-checked pointer from active state to an immutable plan archive."""

    plan_id: str = Field(pattern=r"^plan_[A-Za-z0-9_-]{1,120}$")
    plan_revision_id: str = Field(pattern=r"^plan_revision_[a-f0-9]{16}$")
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    closed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("closed_at_utc")
    @classmethod
    def closed_time_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("closed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class PlanAdaptationDecisionType(str, Enum):
    METHODOLOGY_SELECTION = "methodology_selection"
    STARTING_VOLUME = "starting_volume"
    RUN_FREQUENCY = "run_frequency"
    VOLUME_PROGRESSION = "volume_progression"
    QUALITY_STRUCTURE = "quality_structure"
    LONG_RUN = "long_run"
    RECOVERY_STRUCTURE = "recovery_structure"
    TAPER = "taper"
    MULTISPORT_SCHEDULING = "multisport_scheduling"
    BENCHMARK_SCHEDULING = "benchmark_scheduling"


class PlanAdaptationDecision(BaseModel):
    """One athlete-reviewable planning choice tied to typed historical evidence."""

    decision_type: PlanAdaptationDecisionType
    evidence_ids: list[str] = Field(min_length=1)
    observed_facts: str = Field(min_length=20, max_length=2_000)
    planning_change: str = Field(min_length=20, max_length=2_000)
    affected_week_numbers: list[int] = Field(default_factory=list)
    uncertainty_or_limitation: str | None = Field(default=None, max_length=1_000)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @field_validator("evidence_ids")
    @classmethod
    def evidence_ids_are_unique(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("adaptation evidence IDs cannot be blank")
        if len(value) != len(set(value)):
            raise ValueError("adaptation evidence IDs cannot contain duplicates")
        return value

    @field_validator("affected_week_numbers")
    @classmethod
    def affected_weeks_are_positive_and_unique(
        cls,
        value: list[int],
    ) -> list[int]:
        if any(item < 1 for item in value):
            raise ValueError("affected week numbers must be positive")
        if len(value) != len(set(value)):
            raise ValueError("affected week numbers cannot contain duplicates")
        return value
