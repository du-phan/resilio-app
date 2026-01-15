"""Pydantic schemas for validation functions (Phase 4).

This module defines validation-related schemas for:
- Interval structure validation (Daniels methodology compliance)
- Training plan structure validation (phase duration, volume progression)
- Goal feasibility assessment (VDOT-based reality checks)
"""

from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# Interval Structure Validation
# ============================================================================


class IntervalBout(BaseModel):
    """Single work bout in an interval session."""

    duration_minutes: float = Field(..., description="Work bout duration in minutes")
    pace_per_km_seconds: Optional[int] = Field(
        None, description="Target pace in seconds per km"
    )
    intensity_zone: str = Field(..., description="Intensity zone (e.g., 'I-pace', 'T-pace')")
    ok: bool = Field(..., description="Whether bout duration is appropriate for intensity")
    issue: Optional[str] = Field(None, description="Issue description if not ok")


class RecoveryBout(BaseModel):
    """Recovery interval between work bouts."""

    duration_minutes: float = Field(..., description="Recovery duration in minutes")
    type: str = Field(..., description="Recovery type (e.g., 'jog', 'rest')")
    ok: bool = Field(..., description="Whether recovery is adequate for work bout")
    issue: Optional[str] = Field(None, description="Issue description if not ok")


class Violation(BaseModel):
    """Validation violation."""

    type: str = Field(..., description="Violation type code")
    severity: str = Field(..., description="Severity: LOW, MODERATE, HIGH")
    message: str = Field(..., description="Human-readable violation message")
    recommendation: str = Field(..., description="How to fix the violation")


class IntervalStructureValidation(BaseModel):
    """Validation result for interval workout structure.

    Checks work/recovery ratios per Daniels methodology:
    - I-pace: 3-5min work bouts, equal recovery
    - T-pace: 5-15min work bouts, 1min recovery per 5min work
    - R-pace: 30-90sec work bouts, 2-3x recovery
    """

    workout_type: str = Field(..., description="Workout type (e.g., 'intervals', 'tempo')")
    intensity: str = Field(..., description="Primary intensity (e.g., 'I-pace', 'T-pace')")
    work_bouts: List[IntervalBout] = Field(..., description="Work bout analysis")
    recovery_bouts: List[RecoveryBout] = Field(..., description="Recovery bout analysis")
    violations: List[Violation] = Field(default_factory=list, description="Violations found")
    total_work_volume_minutes: float = Field(..., description="Total work time in minutes")
    total_work_volume_km: Optional[float] = Field(
        None, description="Total work distance in km"
    )
    total_volume_ok: bool = Field(
        ..., description="Whether total I/T/R volume is within safe limits"
    )
    daniels_compliance: bool = Field(
        ..., description="Whether workout complies with Daniels methodology"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for improvement"
    )


# ============================================================================
# Plan Structure Validation
# ============================================================================


class PhaseCheck(BaseModel):
    """Phase duration appropriateness check."""

    weeks: int = Field(..., description="Number of weeks in phase")
    appropriate: bool = Field(..., description="Whether duration is appropriate")
    note: Optional[str] = Field(None, description="Explanation or issue description")
    issue: Optional[str] = Field(None, description="Issue if not appropriate")


class VolumeProgressionCheck(BaseModel):
    """Volume progression safety check."""

    start_volume_km: float = Field(..., description="Starting weekly volume in km")
    peak_volume_km: float = Field(..., description="Peak weekly volume in km")
    total_increase_pct: float = Field(
        ..., description="Total volume increase percentage"
    )
    weeks_to_peak: int = Field(..., description="Number of weeks to reach peak")
    avg_weekly_increase_pct: float = Field(
        ..., description="Average weekly volume increase percentage"
    )
    safe: bool = Field(
        ..., description="Whether progression follows 10% rule (safe: <10% avg increase)"
    )
    note: Optional[str] = Field(None, description="Additional context")


class PeakPlacementCheck(BaseModel):
    """Peak week placement check."""

    peak_week_number: int = Field(..., description="Week number of peak volume")
    weeks_before_race: int = Field(..., description="Weeks between peak and race")
    appropriate: bool = Field(
        ..., description="Whether peak placement is appropriate (2-3 weeks before race)"
    )
    note: Optional[str] = Field(None, description="Explanation")


class RecoveryWeekCheck(BaseModel):
    """Recovery week frequency check."""

    recovery_weeks: List[int] = Field(..., description="Week numbers designated as recovery")
    frequency: str = Field(..., description="Recovery week frequency (e.g., 'every 4 weeks')")
    appropriate: bool = Field(
        ..., description="Whether recovery frequency is appropriate (every 3-4 weeks)"
    )
    note: Optional[str] = Field(None, description="Explanation or issue")


class TaperStructureCheck(BaseModel):
    """Taper volume reduction check."""

    taper_weeks: List[int] = Field(..., description="Week numbers in taper phase")
    week_reductions: Dict[int, float] = Field(
        ..., description="Volume reduction percentage by week (week_number -> pct_of_peak)"
    )
    appropriate: bool = Field(
        ...,
        description="Whether taper follows standard reduction (70%, 50%, 30% for 3-week taper)",
    )
    note: Optional[str] = Field(None, description="Taper structure explanation")


class PlanStructureValidation(BaseModel):
    """Validation result for training plan structure.

    Checks:
    - Phase duration appropriateness (base, build, peak, taper)
    - Volume progression safety (10% rule)
    - Peak placement (2-3 weeks before race)
    - Recovery week frequency (every 3-4 weeks)
    - Taper structure (gradual volume reduction)
    """

    total_weeks: int = Field(..., description="Total number of weeks in plan")
    goal_type: str = Field(..., description="Goal race type (e.g., 'half_marathon')")
    phase_duration_check: Dict[str, PhaseCheck] = Field(
        ..., description="Phase duration checks by phase name"
    )
    volume_progression_check: VolumeProgressionCheck = Field(
        ..., description="Volume progression safety analysis"
    )
    peak_placement_check: PeakPlacementCheck = Field(
        ..., description="Peak week placement analysis"
    )
    recovery_week_check: RecoveryWeekCheck = Field(
        ..., description="Recovery week frequency analysis"
    )
    taper_structure_check: TaperStructureCheck = Field(
        ..., description="Taper volume reduction analysis"
    )
    violations: List[Violation] = Field(default_factory=list, description="Violations found")
    overall_quality_score: int = Field(
        ..., ge=0, le=100, description="Overall plan quality score (0-100)"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for improvement"
    )


# ============================================================================
# Goal Feasibility Assessment
# ============================================================================


class CurrentFitness(BaseModel):
    """Athlete's current fitness state."""

    vdot: Optional[int] = Field(None, description="Current VDOT (if available)")
    ctl: float = Field(..., description="Current CTL (Chronic Training Load)")
    equivalent_race_time: Optional[str] = Field(
        None, description="Equivalent race time for goal distance based on current VDOT"
    )
    recent_race_result: Optional[str] = Field(
        None, description="Most recent race result (e.g., '10K @ 45:30')"
    )


class GoalFitnessNeeded(BaseModel):
    """Fitness required to achieve goal."""

    vdot_for_goal: Optional[int] = Field(
        None, description="VDOT required to achieve goal time"
    )
    vdot_gap: Optional[int] = Field(
        None, description="VDOT improvement needed (positive if improvement needed)"
    )
    ctl_recommended: float = Field(
        ..., description="Recommended CTL for goal race distance"
    )
    ctl_gap: float = Field(
        ..., description="CTL improvement needed (positive if build needed)"
    )


class TimeAvailable(BaseModel):
    """Time available for training."""

    weeks_until_race: int = Field(..., description="Weeks from now to race date")
    typical_training_duration: str = Field(
        ..., description="Typical training duration for this race type"
    )
    sufficient: bool = Field(
        ..., description="Whether time available is sufficient for typical training"
    )


class FeasibilityAnalysis(BaseModel):
    """Detailed feasibility analysis."""

    vdot_improvement_needed: Optional[int] = Field(
        None, description="VDOT points to gain"
    )
    vdot_improvement_pct: Optional[float] = Field(
        None, description="VDOT improvement as percentage"
    )
    typical_vdot_gain_per_month: float = Field(
        1.5, description="Typical VDOT gain per month with consistent training"
    )
    months_needed: Optional[float] = Field(
        None, description="Months needed for required VDOT improvement"
    )
    months_available: float = Field(..., description="Months available until race")
    buffer: Optional[float] = Field(None, description="Time buffer in months")
    limiting_factor: Optional[str] = Field(
        None, description="Primary limiting factor (e.g., 'insufficient time', 'large VDOT gap')"
    )


class AlternativeScenario(BaseModel):
    """Alternative goal scenario."""

    adjusted_goal_time: str = Field(..., description="Adjusted goal time")
    vdot_needed: Optional[int] = Field(None, description="VDOT needed for adjusted goal")
    feasibility: str = Field(
        ..., description="Feasibility level: VERY_REALISTIC, REALISTIC, AMBITIOUS"
    )
    note: str = Field(..., description="Explanation of scenario")


class GoalFeasibilityAssessment(BaseModel):
    """Goal feasibility assessment result.

    Uses VDOT calculations and CTL analysis to assess whether a goal
    is realistic given current fitness and time available.
    """

    goal: str = Field(..., description="Goal description (e.g., 'Half Marathon 1:30:00 on 2026-06-01')")
    current_fitness: CurrentFitness = Field(..., description="Current fitness state")
    goal_fitness_needed: GoalFitnessNeeded = Field(..., description="Fitness required for goal")
    time_available: TimeAvailable = Field(..., description="Time available for training")
    feasibility_verdict: str = Field(
        ...,
        description="Overall verdict: VERY_REALISTIC, REALISTIC, AMBITIOUS_BUT_REALISTIC, AMBITIOUS, UNREALISTIC",
    )
    feasibility_analysis: FeasibilityAnalysis = Field(
        ..., description="Detailed feasibility analysis"
    )
    confidence_level: str = Field(
        ..., description="Confidence in assessment: HIGH, MODERATE, LOW"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations and next steps"
    )
    alternative_scenarios: List[AlternativeScenario] = Field(
        default_factory=list, description="Alternative goal options"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Warnings about goal or training approach"
    )
