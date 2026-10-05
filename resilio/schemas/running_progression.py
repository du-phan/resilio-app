"""Evidence and coach decisions for running progression; never an injury score."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.recovery_context import RecoveryContext

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=20, max_length=4000)]


class ProgressionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunningRecording(ProgressionModel):
    activity_id: str
    canonical_sha256: Digest
    local_date: date
    start_time_utc: datetime | None
    distance_meters: NonNegative | None
    moving_duration_seconds: int = Field(ge=0)
    elapsed_duration_seconds: int = Field(gt=0)
    surface: str
    feedback: list[str]
    feedback_trust_boundary: Literal[
        "athlete_authored_untrusted_text"
    ] = "athlete_authored_untrusted_text"


class RunningSession(ProgressionModel):
    activity_ids: list[str] = Field(min_length=1)
    local_date: date
    distance_meters: NonNegative | None
    moving_duration_seconds: int = Field(ge=0)
    elapsed_duration_seconds: int = Field(gt=0)
    pause_duration_seconds: int = Field(ge=0)
    wall_span_seconds: int | None = Field(ge=0)


class RunningWeek(ProgressionModel):
    start_date: date
    observed_end_date: date
    session_count: int = Field(ge=0)
    running_day_count: int = Field(ge=0)
    distance_meters: NonNegative | None
    moving_duration_seconds: int = Field(ge=0)
    elapsed_duration_seconds: int = Field(ge=0)
    supporting_distance_meters: NonNegative | None


class RunningProgressionEvidenceV1(ProgressionModel):
    schema_version: Literal[1] = 1
    as_of_date: date
    window_start_date: date
    source_state_sha256: Digest
    recordings: list[RunningRecording]
    sessions: list[RunningSession]
    weeks: list[RunningWeek]
    recovery: RecoveryContext
    coverage_by_week: list[dict[str, object]]
    other_sport_exposure_by_week: list[dict[str, object]]
    intensity_evidence_by_week: list[dict[str, object]]
    limitations: list[str]


class SessionProgressionComparison(ProgressionModel):
    key: str
    week_number: int
    candidate_date: date | None
    candidate_distance_meters: NonNegative | None
    nominal_duration_seconds: int | None = Field(ge=0)
    comparator_start_date: date
    comparator_end_date: date
    observed_comparator_end_date: date
    longest_distance_activity_ids: list[str]
    longest_recorded_distance_meters: NonNegative | None
    longest_moving_duration_activity_ids: list[str]
    longest_recorded_moving_duration_seconds: int | None
    longest_elapsed_duration_activity_ids: list[str]
    longest_recorded_elapsed_duration_seconds: int | None
    distance_change_percent: float | None = Field(allow_inf_nan=False)
    weekly_distance_share_percent: NonNegative | None


class WeekProgressionComparison(ProgressionModel):
    week_number: int
    target_distance_meters: NonNegative
    intended_running_day_count: int | None = Field(ge=1)
    nominal_duration_seconds: int | None = Field(ge=0)
    moderate_intensity_duration_seconds: int | None = Field(ge=0)
    high_intensity_duration_seconds: int | None = Field(ge=0)
    supporting_distance_meters: NonNegative | None


class ProgressionAssessmentV1(ProgressionModel):
    policy_version: Literal["run_progression_review_v1"] = "run_progression_review_v1"
    kind: Literal["macro", "amendment", "week"]
    candidate_sha256: Digest
    evidence_sha256: Digest
    evidence: RunningProgressionEvidenceV1
    minimum_run_days_per_week: int = Field(ge=0, le=7)
    maximum_run_days_per_week: int = Field(ge=0, le=7)
    weeks: list[WeekProgressionComparison]
    sessions: list[SessionProgressionComparison]


class DatedAthleteProgressionReport(ProgressionModel):
    local_date: date
    confirmation_reference: str = Field(min_length=10, max_length=1000)
    report: Text
    trust_boundary: Literal["athlete_authored_untrusted_text"] = "athlete_authored_untrusted_text"


class ProgressionReasoning(ProgressionModel):
    distance_and_duration: Text
    duration_estimate_basis: Text
    frequency_and_supporting_volume: Text
    combined_volume_frequency_quality: Text
    terrain_and_travel: Text
    recovery_and_feedback: Text
    other_sports: Text
    evidence_activity_ids: list[str]
    unknowns: list[str]

    @model_validator(mode="after")
    def citations_or_unknowns_are_required(self) -> "ProgressionReasoning":
        if not self.evidence_activity_ids and not self.unknowns:
            raise ValueError("Reasoning requires evidence citations or explicit unknowns")
        return self


class ProgressionJudgment(ProgressionModel):
    key: str
    decision: Literal["proceed", "conditional", "revise", "defer"]
    intended_running_day_count: int = Field(ge=1)
    reasoning_id: str = Field(min_length=1)
    recommendation: Text
    execution_conditions: Text
    fallback: Text
    future_prerequisites: list[str]

    @model_validator(mode="after")
    def conditional_decision_has_prerequisites(self) -> "ProgressionJudgment":
        if self.decision == "conditional" and not self.future_prerequisites:
            raise ValueError("Conditional progression requires future prerequisites")
        if self.decision == "proceed" and self.future_prerequisites:
            raise ValueError("Proceed cannot assert unmet future prerequisites")
        return self


class RunProgressionReviewV1(ProgressionModel):
    schema_version: Literal[1] = 1
    candidate_sha256: Digest
    evidence_sha256: Digest
    acknowledged_limitations: list[str]
    athlete_reports: list[DatedAthleteProgressionReport]
    reasoning: dict[str, ProgressionReasoning] = Field(min_length=1, max_length=200)
    judgments: list[ProgressionJudgment] = Field(min_length=1, max_length=200)


class RunProgressionBindingV1(ProgressionModel):
    bound_at_utc: datetime
    assessment: ProgressionAssessmentV1
    review: RunProgressionReviewV1
