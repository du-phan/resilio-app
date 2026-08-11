"""Typed, signal-first context consumed by coaching procedures."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.activity import (
    ActivityAnalysisThresholds,
    ActivityFeelObservation,
    AerobicLoad,
    NativeActivityAnalysis,
    NativeAnalysisApplicability,
    SubjectiveSessionEffort,
)
from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryScheduleConstraint,
    TimedBenchmarkIntent,
)
from resilio.schemas.methodology import MethodologySelection
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.constraints import PlanningConstraintsSnapshot
from resilio.schemas.planning.weeks import WorkoutStructureHints
from resilio.schemas.sync import SourceCoverageExclusion, SourceCoverageGap


class TrainingStateSnapshot(BaseModel):
    local_date: date
    fitness_load_points: float = Field(ge=0, allow_inf_nan=False)
    fatigue_load_points: float = Field(ge=0, allow_inf_nan=False)
    form_load_points: float = Field(allow_inf_nan=False)
    ramp_load_points_per_week: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )

    model_config = ConfigDict(extra="forbid")


class RecoverySignal(BaseModel):
    name: str
    current_date: date
    current_value: float = Field(allow_inf_nan=False)
    unit: str
    observation_age_days: int = Field(ge=0)
    is_temporary: Optional[bool] = None
    personal_baseline_median: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    difference_from_baseline: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    baseline_sample_count: int = Field(ge=0)
    scale_direction: Literal[
        "lower_is_better",
        "higher_is_better",
        "neutral",
        "provider_defined",
    ] = "neutral"
    scale_minimum: Optional[float] = Field(default=None, allow_inf_nan=False)
    scale_maximum: Optional[float] = Field(default=None, allow_inf_nan=False)
    scale_labels: dict[int, str] = Field(default_factory=dict)
    freshness: Literal["same_day", "recent", "stale"]
    recent_observations: list["RecoveryObservation"] = Field(default_factory=list)
    recent_coverage_expected_days: int = Field(default=7, ge=1)
    recent_coverage_observed_days: int = Field(ge=0)
    recent_coverage_percent: float = Field(ge=0, le=100, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class RecoveryObservation(BaseModel):
    local_date: date
    value: float = Field(allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class DatedAthleteWellnessNote(BaseModel):
    local_date: date
    text: str = Field(min_length=1)
    provenance: Literal["intervals_icu_wellness_comments"] = "intervals_icu_wellness_comments"
    trust_boundary: Literal["athlete_authored_untrusted_text"] = "athlete_authored_untrusted_text"

    model_config = ConfigDict(extra="forbid")


class RecoveryContext(BaseModel):
    as_of_date: date
    signals: list[RecoverySignal] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    wellness_window_start: Optional[date] = None
    wellness_window_end: Optional[date] = None
    wellness_days_available: int = Field(default=0, ge=0)
    athlete_notes: list[DatedAthleteWellnessNote] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ActivityContext(BaseModel):
    local_activity_id: str
    local_date: date
    sport: str
    name: str
    elapsed_duration_seconds: int = Field(ge=0)
    moving_duration_seconds: int = Field(ge=0)
    distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    elevation_gain_meters: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    aerobic_load: Optional[AerobicLoad] = None
    native_analysis: Optional[NativeActivityAnalysis] = None
    native_analysis_applicability: Optional[NativeAnalysisApplicability] = None
    subjective_effort: Optional[SubjectiveSessionEffort] = None
    provider_description: Optional[str] = None
    local_private_note: Optional[str] = None
    feel: Optional[ActivityFeelObservation] = None
    activity_feedback_trust_boundary: Literal[
        "athlete_authored_untrusted_text"
    ] = "athlete_authored_untrusted_text"
    analysis_thresholds: Optional[ActivityAnalysisThresholds] = None

    model_config = ConfigDict(extra="forbid")


class ExposureSummary(BaseModel):
    session_count: int = Field(ge=0)
    elapsed_duration_seconds: int = Field(ge=0)
    aerobic_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    sessions_with_aerobic_load: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class SportExposure(ExposureSummary):
    sport: str


class RunExposure(ExposureSummary):
    run_count: int = Field(ge=0)
    distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    runs_with_distance: int = Field(ge=0)
    elevation_gain_meters: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    runs_with_elevation_gain: int = Field(ge=0)
    longest_run_distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )


class SourceZoneBucket(BaseModel):
    zone_index: Optional[int] = Field(default=None, ge=1)
    provider_zone_id: Optional[str] = Field(default=None, min_length=1)
    name: Optional[str] = None
    duration_seconds: int = Field(ge=0)
    lower_bound: Optional[float] = Field(default=None, allow_inf_nan=False)
    upper_bound: Optional[float] = Field(default=None, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")


class SourceZoneEvidence(BaseModel):
    local_activity_id: str
    sport: str
    source_sport_type: str
    measurement_method: str
    measurement_unit: str
    covered_duration_seconds: int = Field(ge=0)
    analysis_source_moving_duration_seconds: int = Field(ge=0)
    coverage_percent: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    is_primary_time_in_zones_method: bool
    analysis_settings_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    zones: list[SourceZoneBucket]

    model_config = ConfigDict(extra="forbid")


class IntensityContext(BaseModel):
    source_zone_evidence: list[SourceZoneEvidence] = Field(default_factory=list)
    due_planned_low_intensity_duration_seconds: int = Field(ge=0)
    due_planned_moderate_intensity_duration_seconds: int = Field(ge=0)
    due_planned_high_intensity_duration_seconds: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class PlannedWorkoutContext(BaseModel):
    workout_identity: PlanWorkoutIdentity
    local_workout_id: str
    occurrence_date: date
    sport: str
    workout_type: str
    planned_duration_seconds: int = Field(gt=0)
    planned_distance_meters: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    is_due: bool
    is_outstanding: bool
    fulfillment_status: Literal[
        "unfulfilled",
        "fulfilled_early",
        "fulfilled_on_schedule",
        "fulfilled_late",
    ]
    fulfillment_basis: Optional[
        Literal[
            "provider_paired",
            "athlete_confirmed",
            "provider_paired_and_athlete_confirmed",
        ]
    ] = None
    execution_local_date: Optional[date] = None
    schedule_offset_days: Optional[int] = None
    matched_local_activity_id: Optional[str] = None
    provider_computed_aerobic_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_relative_intensity_percent: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def identity_and_fulfillment_are_coherent(self) -> "PlannedWorkoutContext":
        if self.local_workout_id != self.workout_identity.local_workout_id:
            raise ValueError("local workout ID must match the qualified workout identity")
        fulfillment_fields = (
            self.fulfillment_basis,
            self.execution_local_date,
            self.schedule_offset_days,
            self.matched_local_activity_id,
        )
        if self.fulfillment_status == "unfulfilled":
            if not self.is_outstanding or any(value is not None for value in fulfillment_fields):
                raise ValueError(
                    "unfulfilled workout must be outstanding without fulfillment evidence"
                )
            return self
        if self.is_outstanding or any(value is None for value in fulfillment_fields):
            raise ValueError(
                "fulfilled workout must not be outstanding and requires fulfillment evidence"
            )
        assert self.schedule_offset_days is not None
        expected_status = (
            "fulfilled_early"
            if self.schedule_offset_days < 0
            else "fulfilled_late"
            if self.schedule_offset_days > 0
            else "fulfilled_on_schedule"
        )
        if self.fulfillment_status != expected_status:
            raise ValueError("fulfillment status must match schedule offset")
        return self


class AdherenceContext(BaseModel):
    schema_version: Literal[2] = 2
    status: Literal["available", "no_plan", "unavailable"]
    reason: Optional[str] = None
    planned_workout_count: int = Field(ge=0)
    due_workout_count: int = Field(ge=0)
    fulfilled_workout_count: int = Field(ge=0)
    due_fulfilled_workout_count: int = Field(ge=0)
    due_unfulfilled_workout_count: int = Field(ge=0)
    fulfilled_early_workout_count: int = Field(ge=0)
    fulfilled_late_workout_count: int = Field(ge=0)
    workouts: list[PlannedWorkoutContext] = Field(default_factory=list)
    due_planned_low_intensity_duration_seconds: int = Field(ge=0)
    due_planned_moderate_intensity_duration_seconds: int = Field(ge=0)
    due_planned_high_intensity_duration_seconds: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def aggregate_counts_match_workout_projections(self) -> "AdherenceContext":
        expected_counts = {
            "planned_workout_count": len(self.workouts),
            "due_workout_count": sum(workout.is_due for workout in self.workouts),
            "fulfilled_workout_count": sum(
                workout.fulfillment_status != "unfulfilled" for workout in self.workouts
            ),
            "due_fulfilled_workout_count": sum(
                workout.is_due and workout.fulfillment_status != "unfulfilled"
                for workout in self.workouts
            ),
            "due_unfulfilled_workout_count": sum(
                workout.is_due and workout.fulfillment_status == "unfulfilled"
                for workout in self.workouts
            ),
            "fulfilled_early_workout_count": sum(
                workout.fulfillment_status == "fulfilled_early" for workout in self.workouts
            ),
            "fulfilled_late_workout_count": sum(
                workout.fulfillment_status == "fulfilled_late" for workout in self.workouts
            ),
        }
        for field_name, expected_value in expected_counts.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must match workout projections")
        return self


class CoachingDataQuality(BaseModel):
    activity_count: int = Field(ge=0)
    activities_with_native_aerobic_load: int = Field(ge=0)
    activities_with_zone_evidence: int = Field(ge=0)
    activities_with_native_analysis: int = Field(ge=0)
    activities_with_polarization_observation: int = Field(ge=0)
    activities_with_linked_polarization_evidence: int = Field(ge=0)
    activities_with_decoupling_observation: int = Field(ge=0)
    activities_with_known_decoupling_basis: int = Field(ge=0)
    wellness_days_available: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class SyncEvidenceCoverage(BaseModel):
    """Completeness of source evidence for the context's exact date range."""

    status: Literal[
        "complete",
        "complete_with_declared_exclusions",
        "incomplete",
        "unavailable",
    ]
    requested_window_start: date
    requested_window_end: date
    complete_window_start: Optional[date] = None
    complete_window_end: Optional[date] = None
    last_successful_sync_at_utc: Optional[datetime] = None
    exclusions: list[SourceCoverageExclusion] = Field(default_factory=list)
    gaps: list[SourceCoverageGap] = Field(default_factory=list)
    reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class _WeeklyCoachContextBase(BaseModel):
    week_start: date
    week_end: date
    as_of_date: date
    training_state: Optional[TrainingStateSnapshot] = None
    recovery: RecoveryContext
    activities: list[ActivityContext]
    run_exposure: RunExposure
    other_sport_exposure_by_sport: list[SportExposure]
    intensity: IntensityContext
    data_quality: CoachingDataQuality
    source_evidence_coverage: SyncEvidenceCoverage

    model_config = ConfigDict(extra="forbid")


class WeeklyCoachContext(_WeeklyCoachContextBase):
    """Current fulfillment-aware weekly coaching evidence."""

    schema_version: Literal[2] = 2
    adherence: AdherenceContext


class CoachHistoryContext(BaseModel):
    as_of_date: date
    target_week_start: date
    target_week_end: date
    evidence_window_start: date
    evidence_window_end: date
    requested_week_count: int = Field(ge=1, le=52)
    weeks: list[WeeklyCoachContext]

    model_config = ConfigDict(extra="forbid")


class TargetWeekSkeletonContext(BaseModel):
    plan_kind: Literal["race_macro", "baseline_assessment"]
    plan_id: str
    plan_revision_id: str
    plan_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_week_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    week_number: int = Field(ge=1)
    phase: str
    start_date: date
    end_date: date
    target_run_volume_meters: float = Field(ge=0, allow_inf_nan=False)
    workout_structure_hints: WorkoutStructureHints
    is_recovery_week: bool

    model_config = ConfigDict(extra="forbid")


class ApprovedVDOTContext(BaseModel):
    approval_id: str
    approved_vdot: int = Field(ge=30, le=85)
    evidence_type: str

    model_config = ConfigDict(extra="forbid")


class WeekPlanningContext(BaseModel):
    """Future-target skeleton plus evidence ending on a separate as-of date."""

    schema_version: Literal[1] = 1
    generated_at_utc: datetime
    source_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_as_of_date: date
    target_week: TargetWeekSkeletonContext
    recent_history: CoachHistoryContext
    approved_vdot: ApprovedVDOTContext | None = None
    methodology: MethodologySelection | None = None
    assessment_reasons: list[AssessmentReason] = Field(default_factory=list)
    benchmark_intent: TimedBenchmarkIntent | None = None
    temporary_schedule_constraints: list[TemporaryScheduleConstraint] = Field(default_factory=list)
    constraints: PlanningConstraintsSnapshot

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at_utc")
    @classmethod
    def generation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def plan_specific_context_is_complete(self) -> "WeekPlanningContext":
        generation_local_date = self.generated_at_utc.astimezone(
            ZoneInfo(self.constraints.training_timezone)
        ).date()
        if self.evidence_as_of_date > generation_local_date:
            raise ValueError("evidence_as_of_date cannot postdate context generation")
        if self.recent_history.as_of_date != self.evidence_as_of_date:
            raise ValueError("recent history must end on the context evidence date")
        is_race_plan = self.target_week.plan_kind == "race_macro"
        if is_race_plan != (self.approved_vdot is not None and self.methodology is not None):
            raise ValueError("race planning context requires approved VDOT and methodology")
        if is_race_plan and (
            self.assessment_reasons
            or self.benchmark_intent is not None
            or self.temporary_schedule_constraints
        ):
            raise ValueError("race planning context cannot contain assessment intent")
        if not is_race_plan and (not self.assessment_reasons or self.benchmark_intent is None):
            raise ValueError("assessment planning context requires reasons and benchmark intent")
        return self
