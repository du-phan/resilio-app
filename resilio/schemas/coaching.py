"""Typed, signal-first context consumed by coaching procedures."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resilio.schemas.activity import (
    ActivityAnalysisThresholds,
    AerobicLoad,
    NativeActivityAnalysis,
    NativeAnalysisApplicability,
    SubjectiveSessionEffort,
)
from resilio.schemas.methodology import MethodologySelection
from resilio.schemas.plan import (
    PlanningConstraintsSnapshot,
    WorkoutStructureHints,
)
from resilio.schemas.plan_history import PlanWorkoutIdentity
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

    model_config = ConfigDict(extra="forbid")


class RecoveryContext(BaseModel):
    as_of_date: date
    signals: list[RecoverySignal] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    wellness_window_start: Optional[date] = None
    wellness_window_end: Optional[date] = None
    wellness_days_available: int = Field(default=0, ge=0)

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
    def local_id_matches_qualified_identity(self) -> "PlannedWorkoutContext":
        if self.local_workout_id != self.workout_identity.local_workout_id:
            raise ValueError("local workout ID must match the qualified workout identity")
        return self


class AdherenceContext(BaseModel):
    status: Literal["available", "no_plan", "unavailable"]
    reason: Optional[str] = None
    planned_workout_count: int = Field(ge=0)
    due_workout_count: int = Field(ge=0)
    verified_completed_workout_count: int = Field(ge=0)
    due_unmatched_workout_count: int = Field(ge=0)
    workouts: list[PlannedWorkoutContext] = Field(default_factory=list)
    due_planned_low_intensity_duration_seconds: int = Field(ge=0)
    due_planned_moderate_intensity_duration_seconds: int = Field(ge=0)
    due_planned_high_intensity_duration_seconds: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


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


class WeeklyCoachContext(BaseModel):
    week_start: date
    week_end: date
    as_of_date: date
    training_state: Optional[TrainingStateSnapshot] = None
    recovery: RecoveryContext
    activities: list[ActivityContext]
    run_exposure: RunExposure
    other_sport_exposure_by_sport: list[SportExposure]
    adherence: AdherenceContext
    intensity: IntensityContext
    data_quality: CoachingDataQuality
    source_evidence_coverage: SyncEvidenceCoverage

    model_config = ConfigDict(extra="forbid")


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
    plan_id: str
    macro_revision_id: str
    macro_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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

    evidence_as_of_date: date
    target_week: TargetWeekSkeletonContext
    recent_history: CoachHistoryContext
    approved_vdot: ApprovedVDOTContext
    methodology: MethodologySelection
    constraints: PlanningConstraintsSnapshot

    model_config = ConfigDict(extra="forbid")
