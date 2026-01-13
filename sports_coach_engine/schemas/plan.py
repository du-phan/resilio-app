"""
Plan schemas - Training plan data models.

This module defines Pydantic schemas for training plan generation (M10),
including master plans, weekly plans, workout prescriptions, and periodization
phases. These schemas support evidence-based plan generation with training
guardrails (80/20 rule, long run caps, hard/easy separation).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date
from enum import Enum


# ============================================================
# ENUMS
# ============================================================


class GoalType(str, Enum):
    """Training goal types supported by the plan generator."""

    GENERAL_FITNESS = "general_fitness"
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"


class PlanPhase(str, Enum):
    """Periodization phases for structured training progression."""

    BASE = "base"          # Build aerobic foundation, high volume low intensity
    BUILD = "build"        # Increase intensity, introduce quality sessions
    PEAK = "peak"          # Race-specific work, highest quality volume
    TAPER = "taper"        # Reduce volume, maintain intensity, arrive fresh
    RECOVERY = "recovery"  # Post-race recovery or deload week


class WorkoutType(str, Enum):
    """Workout classifications for training prescriptions."""

    EASY = "easy"              # Zone 1-2, recovery and aerobic maintenance
    LONG_RUN = "long_run"      # Extended aerobic endurance session
    TEMPO = "tempo"            # Lactate threshold pace work
    INTERVALS = "intervals"    # VO2max intervals
    FARTLEK = "fartlek"        # Unstructured speed play
    STRIDES = "strides"        # Short accelerations for neuromuscular training
    RACE = "race"              # Race effort or time trial
    REST = "rest"              # Scheduled rest day


class IntensityZone(str, Enum):
    """Training intensity zones based on percentage of max heart rate."""

    ZONE_1 = "zone_1"  # Recovery: <65% max HR
    ZONE_2 = "zone_2"  # Easy aerobic: 65-75% max HR
    ZONE_3 = "zone_3"  # Moderate aerobic: 75-85% max HR
    ZONE_4 = "zone_4"  # Threshold: 85-90% max HR
    ZONE_5 = "zone_5"  # VO2max: 90-95% max HR


# ============================================================
# TOOLKIT MODELS (Phase 5: Toolkit Paradigm)
# ============================================================


class PhaseAllocation(BaseModel):
    """
    Suggested phase allocation for periodization.

    Returned by calculate_periodization() toolkit function. Provides
    reference phase split based on goal type and available weeks.
    Claude Code uses this as a reference when designing training plans.
    """

    base_weeks: int = Field(..., ge=0, description="Weeks in base phase")
    build_weeks: int = Field(..., ge=0, description="Weeks in build phase")
    peak_weeks: int = Field(..., ge=0, description="Weeks in peak phase")
    taper_weeks: int = Field(..., ge=0, description="Weeks in taper phase")
    total_weeks: int = Field(..., ge=1, description="Total weeks")
    reasoning: str = Field(..., description="Explanation of phase split rationale")


class VolumeRecommendation(BaseModel):
    """
    Safe volume range recommendation based on current fitness.

    Returned by suggest_volume_adjustment() toolkit function. Provides
    conservative starting and peak volume ranges based on CTL, goal distance,
    and available timeline. Claude Code uses this to set realistic targets.
    """

    start_range_km: tuple[float, float] = Field(..., description="Safe starting volume range (min, max)")
    peak_range_km: tuple[float, float] = Field(..., description="Safe peak volume range (min, max)")
    rationale: str = Field(..., description="Explanation of volume recommendations")
    current_ctl: float = Field(..., ge=0, description="Current CTL used for recommendation")
    goal_distance_km: float = Field(..., gt=0, description="Goal race distance")
    weeks_available: int = Field(..., ge=1, description="Weeks available to train")


class WeeklyVolume(BaseModel):
    """
    Single week's volume recommendation in progression curve.

    Returned by calculate_volume_progression() toolkit function. Represents
    one week's target volume in a linear progression with recovery weeks.
    Claude Code uses these as baseline targets and adjusts based on readiness.
    """

    week_number: int = Field(..., ge=1, description="Week number (1-indexed)")
    volume_km: float = Field(..., ge=0, description="Target volume for this week")
    is_recovery_week: bool = Field(False, description="Is this a scheduled recovery week?")
    phase: PlanPhase = Field(..., description="Periodization phase")
    reasoning: str = Field(..., description="Why this volume (e.g., 'Recovery week -20%')")


class GuardrailViolation(BaseModel):
    """
    Training science guardrail violation (detection only, not enforcement).

    Returned by validate_guardrails() toolkit function. Represents a detected
    violation of evidence-based training principles. Claude Code reviews these
    and decides whether to enforce, override with rationale, or discuss with athlete.
    """

    rule: str = Field(..., description="Guardrail rule violated (e.g., 'max_quality_sessions')")
    week: Optional[int] = Field(None, ge=1, description="Week number if week-specific violation")
    severity: str = Field(..., description="Severity level: 'info' | 'warning' | 'danger'")
    actual: float = Field(..., description="Actual value that triggered violation")
    target: float = Field(..., description="Target/threshold value for the rule")
    message: str = Field(..., description="Human-readable violation message")
    suggestion: str = Field(..., description="Suggested fix (Claude decides whether to apply)")


# ============================================================
# CORE MODELS
# ============================================================


class WorkoutPrescription(BaseModel):
    """
    Complete workout specification with intensity targets and structure.

    Represents a single prescribed workout with all details needed for
    execution: type, duration/distance, intensity guidance (RPE, pace, HR),
    and purpose. Used by athletes to understand what to do and why.
    """

    # Identity
    id: str = Field(..., description="Unique workout identifier")
    week_number: int = Field(..., ge=1, description="Week number in plan (1-indexed)")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    date: date

    # Type and phase
    workout_type: WorkoutType = Field(..., description="Workout classification")
    phase: PlanPhase = Field(..., description="Periodization phase")

    # Duration/distance
    duration_minutes: int = Field(..., gt=0, description="Target duration in minutes")
    distance_km: Optional[float] = Field(None, ge=0, description="Target distance (if distance-based)")

    # Intensity guidance
    intensity_zone: IntensityZone = Field(..., description="Training intensity zone")
    target_rpe: int = Field(..., ge=1, le=10, description="Target RPE on 1-10 scale")

    # Pace/HR ranges (optional, based on profile data)
    pace_range_min_km: Optional[str] = Field(None, description="Minimum pace per km (e.g., '5:30')")
    pace_range_max_km: Optional[str] = Field(None, description="Maximum pace per km (e.g., '5:45')")
    hr_range_low: Optional[int] = Field(None, ge=30, le=220, description="Lower HR bound (bpm)")
    hr_range_high: Optional[int] = Field(None, ge=30, le=220, description="Upper HR bound (bpm)")

    # Structure (for intervals/tempo)
    intervals: Optional[list[dict]] = Field(
        None,
        description="Interval structure (e.g., [{'distance': '800m', 'reps': 4}])"
    )
    warmup_minutes: int = Field(10, ge=0, description="Warmup duration")
    cooldown_minutes: int = Field(10, ge=0, description="Cooldown duration")

    # Purpose and metadata
    purpose: str = Field(..., description="Why this workout (training stimulus)")
    notes: Optional[str] = Field(None, description="Additional guidance or cues")
    key_workout: bool = Field(False, description="Is this a key session for the week?")

    # Status tracking
    status: str = Field("scheduled", description="scheduled | completed | skipped | adapted")
    execution: Optional[dict] = Field(None, description="Actual execution data (filled post-workout)")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class WeekPlan(BaseModel):
    """
    Single week's training plan with volume targets and workouts.

    Represents one week within a master plan, including target volume,
    all scheduled workouts, and metadata about recovery weeks or phase
    transitions. Weeks are the atomic unit of plan refinement.
    """

    week_number: int = Field(..., ge=1, description="Week number (1-indexed)")
    phase: PlanPhase = Field(..., description="Periodization phase for this week")
    start_date: date
    end_date: date

    # Weekly targets
    target_volume_km: float = Field(..., ge=0, description="Target run volume for week")
    target_systemic_load_au: float = Field(..., ge=0, description="Target systemic load (from M8)")

    # Workouts
    workouts: list[WorkoutPrescription] = Field(..., description="All workouts for this week")

    # Metadata
    is_recovery_week: bool = Field(False, description="Is this a scheduled recovery week?")
    notes: Optional[str] = Field(None, description="Week-level notes or adjustments")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class MasterPlan(BaseModel):
    """
    Complete training plan from start date to goal/race date.

    Represents the full periodized training plan with all weeks, phases,
    and volume progression. This is the "master" structure that guides
    training; weekly refinement adjusts details while preserving overall
    structure. Generated by M10 based on goal, constraints, and fitness.
    """

    # Identity
    id: str = Field(..., description="Unique plan identifier")
    created_at: date

    # Goal (stored as dict to avoid circular import with profile.py)
    goal: dict = Field(..., description="Training goal (type, target_date, target_time)")

    # Timeline
    start_date: date
    end_date: date
    total_weeks: int = Field(..., ge=1, description="Total number of weeks in plan")

    # Phase breakdown
    phases: list[dict] = Field(
        ...,
        description="Phase definitions with week ranges (e.g., [{'phase': 'base', 'start_week': 0, ...}])"
    )

    # Weeks
    weeks: list[WeekPlan] = Field(..., description="All weekly plans")

    # Volume progression
    starting_volume_km: float = Field(..., ge=0, description="Initial weekly volume")
    peak_volume_km: float = Field(..., ge=0, description="Peak weekly volume")

    # Metadata
    constraints_applied: list[str] = Field(
        default_factory=list,
        description="Human-readable list of constraints applied"
    )
    conflict_policy: str = Field(..., description="Multi-sport conflict policy applied")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class PlanGenerationResult(BaseModel):
    """
    Result of plan generation with plan, warnings, and guardrails applied.

    Returned by M10.generate_master_plan(). Contains the generated plan
    plus metadata about any warnings (e.g., timeline too short) or guardrails
    that modified the plan (e.g., long run capped, back-to-back hard days fixed).
    """

    plan: MasterPlan = Field(..., description="Generated master plan")
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings (e.g., timeline shorter than recommended)"
    )
    guardrails_applied: list[str] = Field(
        default_factory=list,
        description="Guardrails that modified the plan (e.g., 'Long run capped at 30%')"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )
