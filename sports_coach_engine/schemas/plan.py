"""
Plan schemas - Training plan data models.

This module defines Pydantic schemas for training plan generation (M10),
including master plans, weekly plans, workout prescriptions, and periodization
phases. These schemas support evidence-based plan generation with training
guardrails (80/20 rule, long run caps, hard/easy separation).
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Literal
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


# ============================================================
# MACRO STRUCTURE HINTS (Progressive Disclosure)
# ============================================================


QualityType = Literal[
    "tempo",
    "intervals",
    "hills",
    "race_pace",
    "fartlek",
    "strides_only",
]


LongRunEmphasis = Literal[
    "easy",
    "steady",
    "progression",
    "race_specific",
]


class QualitySessionHints(BaseModel):
    """Macro-level guidance for non-long-run quality sessions."""

    max_sessions: int = Field(
        ...,
        ge=0,
        le=3,
        description="Upper bound on quality sessions (excluding long run)"
    )
    types: List[QualityType] = Field(
        ...,
        description="Quality session focus types (e.g., ['tempo', 'intervals'])"
    )

    @model_validator(mode="after")
    def validate_quality_types(self) -> "QualitySessionHints":
        if self.max_sessions == 0:
            if self.types:
                raise ValueError("quality.types must be empty when quality.max_sessions is 0")
        elif not self.types:
            raise ValueError("quality.types must be non-empty when quality.max_sessions > 0")
        return self

    model_config = ConfigDict(use_enum_values=True)


class LongRunHints(BaseModel):
    """Macro-level guidance for long run emphasis and sizing."""

    emphasis: LongRunEmphasis = Field(..., description="Long run emphasis for the week")
    pct_range: List[float] = Field(
        ...,
        description="Preferred long-run percentage range of weekly volume (e.g., [24, 30])"
    )

    @field_validator("pct_range")
    @classmethod
    def validate_pct_range(cls, value: List[float]) -> List[float]:
        if len(value) != 2:
            raise ValueError("long_run.pct_range must have exactly two values")
        if value[0] >= value[1]:
            raise ValueError("long_run.pct_range must be ascending (min < max)")
        if value[0] < 15 or value[1] > 35:
            raise ValueError("long_run.pct_range must be within 15-35%")
        return value

    model_config = ConfigDict(use_enum_values=True)


class IntensityBalanceHints(BaseModel):
    """Macro-level intensity distribution guidance (80/20-style)."""

    low_intensity_pct: float = Field(
        ...,
        ge=0.75,
        le=0.95,
        description="Target proportion of low-intensity volume (0.75-0.95)"
    )

    model_config = ConfigDict(use_enum_values=True)


class WorkoutStructureHints(BaseModel):
    """Compact macro-level hints to guide weekly plan generation."""

    quality: QualitySessionHints = Field(..., description="Quality session guidance")
    long_run: LongRunHints = Field(..., description="Long run guidance")
    intensity_balance: IntensityBalanceHints = Field(..., description="Intensity distribution guidance")

    model_config = ConfigDict(use_enum_values=True)


class WeekPlan(BaseModel):
    """
    Single week's training plan with explicit workout specifications.

    Represents one week within a master plan, including:
    - Strategic guidance (workout_structure_hints from macro planning)
    - Target volume (target_volume_km from macro planning)
    - Exact workout prescriptions (designed by AI Coach using hints + athlete state)

    The workout_structure_hints provide macro-level strategic guidance
    (e.g., "max 2 quality sessions", "long run 25-30%"). AI Coach uses these
    hints plus current athlete state to design exact workouts for each week.
    """

    week_number: int = Field(..., ge=1, description="Week number (1-indexed)")
    phase: PlanPhase = Field(..., description="Periodization phase for this week")
    start_date: date
    end_date: date

    # Weekly targets
    target_volume_km: float = Field(..., ge=0, description="Target run volume for week")
    target_systemic_load_au: float = Field(..., ge=0, description="Target systemic load (from M8)")

    # Strategic guidance from macro planning (REQUIRED)
    workout_structure_hints: WorkoutStructureHints = Field(
        ...,
        description="Macro-level workout structure hints to guide weekly planning"
    )

    # Workouts (explicit specification - REQUIRED)
    workouts: list[WorkoutPrescription] = Field(
        ...,
        description="Explicit workouts designed by AI Coach using hints + athlete state"
    )

    # Metadata
    is_recovery_week: bool = Field(False, description="Is this a scheduled recovery week?")
    notes: Optional[str] = Field(None, description="Week-level notes or adjustments")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class VDOTHistoryEntry(BaseModel):
    """Record of VDOT changes over time."""

    week: int = Field(..., ge=1, description="Week number when VDOT was recorded")
    vdot: float = Field(..., ge=30, le=85, description="VDOT value")
    source: str = Field(..., description="Source: race | estimate | manual")
    confidence: Optional[str] = Field(None, description="Confidence: low | medium | high")


class PlanState(BaseModel):
    """Plan state for progressive disclosure workflows."""

    last_populated_week: Optional[int] = Field(
        default=None,
        ge=0,
        description="Last week number with populated workouts"
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

    # VDOT context
    baseline_vdot: Optional[float] = Field(
        default=None,
        ge=30,
        le=85,
        description="Baseline VDOT approved for macro plan"
    )
    current_vdot: Optional[float] = Field(
        default=None,
        ge=30,
        le=85,
        description="Current VDOT for weekly planning"
    )
    vdot_history: list[VDOTHistoryEntry] = Field(
        default_factory=list,
        description="VDOT history entries"
    )

    # Plan state
    plan_state: Optional[PlanState] = Field(
        default=None,
        description="Progressive disclosure state tracking"
    )

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


# ============================================================
# PROGRESSIVE DISCLOSURE MODELS (Phase 2: Monthly Planning)
# ============================================================


class PhaseStructure(BaseModel):
    """
    Single phase definition in macro plan structure.

    Defines the boundaries and focus of one periodization phase
    (base, build, peak, taper) within the overall training plan.
    """

    name: PlanPhase = Field(..., description="Phase name")
    weeks: list[int] = Field(..., description="Week numbers in this phase (1-indexed)")
    start_week: int = Field(..., ge=1, description="First week of phase")
    end_week: int = Field(..., ge=1, description="Last week of phase")
    focus: str = Field(..., description="Training focus for this phase")

    model_config = ConfigDict(use_enum_values=True)


class WeeklyVolumeTarget(BaseModel):
    """
    Weekly volume target in macro plan progression.

    Simple volume target for one week, used in macro plan to show
    the overall volume trajectory without detailed workout prescriptions.
    """

    week_number: int = Field(..., ge=1, description="Week number (1-indexed)")
    target_volume_km: float = Field(..., ge=0, description="Target weekly volume")
    is_recovery_week: bool = Field(False, description="Is this a recovery week?")
    phase: PlanPhase = Field(..., description="Phase this week belongs to")

    model_config = ConfigDict(use_enum_values=True)


class MonthlyPlan(BaseModel):
    """
    Detailed 4-week training plan with complete workout prescriptions.

    Contains detailed execution guidance for the next month (4 weeks).
    Generated every 4 weeks based on current fitness, macro plan structure,
    and previous month's performance. Replaces full 16-week detailed planning
    with progressive disclosure approach.

    Each monthly plan:
    - Follows macro plan volume targets and phase boundaries
    - Uses updated VDOT from recent workouts
    - Accounts for previous month's response (if applicable)
    - Contains 16-28 complete workout prescriptions
    """

    # Identity
    id: str = Field(..., description="Unique monthly plan identifier")
    created_at: date
    macro_plan_id: str = Field(..., description="Parent macro plan this belongs to")

    # Coverage
    month_number: int = Field(..., ge=1, description="Month number (1-indexed)")
    week_numbers: list[int] = Field(..., description="Week numbers covered (e.g., [1,2,3,4])")
    start_date: date
    end_date: date

    # Context
    phase: PlanPhase = Field(..., description="Primary phase for this month")
    current_vdot: float = Field(..., ge=30, le=85, description="VDOT used for pace calculations")
    current_ctl: float = Field(..., ge=0, description="CTL at generation time")

    # Based on previous month (if not first month)
    previous_month_summary: Optional[str] = Field(
        None,
        description="Brief summary of previous month completion and response"
    )

    # Weeks (detailed)
    weeks: list[WeekPlan] = Field(..., description="4 weeks of detailed plans")

    # Training paces for this month
    training_paces: dict = Field(
        ...,
        description="VDOT-based paces (e.g., {'e_pace': '6:15-6:45', 't_pace': '4:55-5:10'})"
    )

    # Multi-sport integration
    multi_sport_schedule: Optional[list[dict]] = Field(
        None,
        description="Non-running activities (e.g., [{'day': 'tue', 'sport': 'climbing', 'duration': 120}])"
    )

    model_config = ConfigDict(use_enum_values=True)


class MonthlyAssessment(BaseModel):
    """
    Assessment of completed month for planning next month.

    Analyzes previous month's execution to inform next month's generation:
    - Adherence and completion rates
    - VDOT drift (pace changes suggesting fitness change)
    - Injury/illness signals from notes
    - Volume tolerance and adaptation response
    - CTL progression vs. target

    Used as input to generate-month for adaptive planning.
    """

    # Identity
    month_number: int = Field(..., ge=1, description="Month that was assessed")
    week_numbers: list[int] = Field(..., description="Weeks assessed")
    assessment_date: date

    # Adherence
    planned_workouts: int = Field(..., ge=0, description="Total workouts planned")
    completed_workouts: int = Field(..., ge=0, description="Workouts completed")
    adherence_pct: float = Field(..., ge=0, le=100, description="Completion percentage")

    # CTL progression
    starting_ctl: float = Field(..., ge=0, description="CTL at month start")
    ending_ctl: float = Field(..., ge=0, description="CTL at month end")
    target_ctl: float = Field(..., ge=0, description="Target CTL for month end")
    ctl_delta: float = Field(..., description="Actual CTL change (ending - starting)")
    ctl_on_target: bool = Field(..., description="Did CTL progression meet expectations?")

    # VDOT analysis
    current_vdot: float = Field(..., ge=30, le=85, description="VDOT at month start")
    suggested_vdot: Optional[float] = Field(
        None,
        ge=30,
        le=85,
        description="Suggested VDOT based on workout paces (if recalibration needed)"
    )
    vdot_recalibration_needed: bool = Field(
        False,
        description="Should VDOT be updated for next month?"
    )

    # Signals and patterns
    injury_signals: list[str] = Field(
        default_factory=list,
        description="Injury mentions from workout notes/descriptions"
    )
    illness_signals: list[str] = Field(
        default_factory=list,
        description="Illness mentions from workout notes/descriptions"
    )
    patterns_detected: list[str] = Field(
        default_factory=list,
        description="Patterns observed (e.g., 'Consistently skips Tuesday runs')"
    )

    # Volume tolerance
    volume_well_tolerated: bool = Field(
        ...,
        description="Did athlete handle monthly volume well?"
    )
    volume_adjustment_suggestion: Optional[str] = Field(
        None,
        description="Volume adjustment for next month (e.g., 'Reduce 5%', 'Maintain', 'Increase 5%')"
    )

    # Overall assessment
    overall_response: str = Field(
        ...,
        description="High-level assessment (e.g., 'Excellent adaptation', 'Struggled with volume', 'Illness disruption')"
    )
    recommendations_for_next_month: list[str] = Field(
        ...,
        description="Specific recommendations for next month's planning"
    )

    model_config = ConfigDict(use_enum_values=True)
