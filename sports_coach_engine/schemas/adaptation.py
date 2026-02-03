"""
Adaptation schemas - Workout adaptation and suggestion data models.

This module defines Pydantic schemas for M11 Adaptation Engine, including
triggers, suggestions, safety overrides, and adaptation results. These schemas
support intelligent workout adjustments based on athlete state (CTL/ATL/TSB,
ACWR, readiness, injury/illness flags).

Key concepts:
- Suggestions: Proposed adaptations that require user approval
- Safety Overrides: Auto-applied changes for safety-critical situations
- Triggers: Conditions that generate adaptation suggestions
- Override Risk: Severity level if user declines suggestion
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from enum import Enum


# ============================================================
# ENUMS
# ============================================================


class TriggerType(str, Enum):
    """
    Types of adaptation triggers (Toolkit Paradigm).

    These triggers are detected by M11 toolkit and returned to Claude Code
    for interpretation with athlete context.
    """

    # ACWR-based triggers
    ACWR_ELEVATED = "acwr_elevated"           # 1.3-1.5 (caution zone)
    ACWR_HIGH_RISK = "acwr_high_risk"         # >1.5 (significant load spike)

    # Readiness-based triggers
    READINESS_LOW = "readiness_low"           # 35-50 (reduce intensity)
    READINESS_VERY_LOW = "readiness_very_low" # <35 (rest recommended)

    # TSB-based triggers
    TSB_OVERREACHED = "tsb_overreached"       # TSB < -25 (excessive fatigue)

    # Load-based triggers
    LOWER_BODY_LOAD_HIGH = "lower_body_load_high"       # Yesterday's lower-body load > threshold
    SESSION_DENSITY_HIGH = "session_density_high"       # ≥2 hard sessions in last 7 days


class SuggestionType(str, Enum):
    """Types of workout adaptations that can be suggested."""

    DOWNGRADE = "downgrade"       # Reduce intensity (tempo→easy, intervals→easy)
    SKIP = "skip"                 # Change to rest day
    MOVE = "move"                 # Reschedule to different day
    SUBSTITUTE = "substitute"     # Replace with different workout type
    SHORTEN = "shorten"           # Reduce duration by X%
    FORCE_REST = "force_rest"     # Mandatory rest (safety override, no user choice)


class SuggestionStatus(str, Enum):
    """Lifecycle status of an adaptation suggestion."""

    PENDING = "pending"           # Awaiting user decision
    ACCEPTED = "accepted"         # User accepted, changes applied
    DECLINED = "declined"         # User declined, workout unchanged
    EXPIRED = "expired"           # Past workout date, no longer actionable
    AUTO_APPLIED = "auto_applied" # Applied automatically (safety override)


class OverrideRisk(str, Enum):
    """Risk level if user overrides a suggestion."""

    LOW = "low"           # Minimal risk (e.g., ACWR 1.35, readiness 45)
    MODERATE = "moderate" # Moderate risk (e.g., ACWR 1.45, readiness 38)
    HIGH = "high"         # High risk (e.g., ACWR 1.6, readiness 30, mild illness)
    SEVERE = "severe"     # Cannot override (e.g., fever, severe illness, ACWR >1.8 + readiness <30)


# ============================================================
# TOOLKIT MODELS (Phase 5: Toolkit Paradigm)
# ============================================================


class RiskLevel(str, Enum):
    """Risk levels for injury if athlete overrides triggers."""

    LOW = "low"           # Low risk index
    MODERATE = "moderate" # Moderate risk index
    HIGH = "high"         # High risk index
    SEVERE = "severe"     # Severe risk index


class AdaptationTrigger(BaseModel):
    """
    Detected trigger that warrants coaching attention (Toolkit Paradigm).

    Returned by detect_adaptation_triggers() toolkit function. Represents
    a quantitative threshold breach. Claude Code interprets with athlete
    context (M13 memories, conversation history) to decide adaptations.
    """

    trigger_type: TriggerType = Field(..., description="Type of trigger detected")
    value: float = Field(..., description="Actual metric value (e.g., ACWR=1.45)")
    threshold: float = Field(..., description="Threshold that was breached")
    zone: str = Field(..., description="Severity zone: 'caution' | 'warning' | 'danger'")
    applies_to: list[str] = Field(
        default_factory=list,
        description="Workout types affected (e.g., ['tempo', 'intervals'])"
    )
    detected_at: date = Field(..., description="Date when trigger was detected")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class OverrideRiskAssessment(BaseModel):
    """
    Risk assessment if athlete ignores triggers (Toolkit Paradigm).

    Returned by assess_override_risk() toolkit function. Provides quantitative
    risk index based on triggers, workout intensity, and injury history.
    Claude Code presents this to athlete when discussing adaptation options.
    """

    risk_level: RiskLevel = Field(..., description="Overall risk level")
    risk_index: float = Field(
        ..., ge=0.0, le=1.0, description="Heuristic risk index (0.0-1.0), not a medical probability"
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Contributing risk factors (e.g., 'ACWR 1.45', 'Knee history')"
    )
    recommendation: str = Field(..., description="Risk-based recommendation")
    evidence: list[str] = Field(
        default_factory=list,
        description="Training science evidence citations"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class RecoveryEstimate(BaseModel):
    """
    Estimated recovery time needed from trigger (Toolkit Paradigm).

    Returned by estimate_recovery_time() toolkit function. Estimates days
    needed to resolve trigger based on trigger type, severity, and athlete
    fitness level. Claude Code uses this when proposing workout rescheduling.
    """

    days: int = Field(..., ge=0, description="Estimated recovery days needed")
    confidence: str = Field(..., description="Confidence level: 'low' | 'medium' | 'high'")
    factors: list[str] = Field(
        default_factory=list,
        description="Factors affecting recovery (e.g., 'ACWR spike', 'High CTL')"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class AdaptationThresholds(BaseModel):
    """
    Athlete-specific adaptation thresholds (Toolkit Paradigm).

    Stored in AthleteProfile. Defines when triggers fire for this athlete.
    Elite athletes may have higher thresholds; beginners may have lower.
    Claude Code can adjust these based on athlete feedback patterns.
    """

    acwr_elevated: float = Field(1.3, ge=1.0, le=2.0, description="ACWR caution threshold")
    acwr_high_risk: float = Field(1.5, ge=1.0, le=2.0, description="ACWR danger threshold")
    readiness_low: int = Field(50, ge=0, le=100, description="Readiness warning threshold")
    readiness_very_low: int = Field(35, ge=0, le=100, description="Readiness danger threshold")
    tsb_overreached: int = Field(-25, le=0, description="TSB overreaching threshold")
    lower_body_load_threshold: float = Field(
        1.5,
        ge=1.0,
        le=3.0,
        description="Multiple of 14-day median for high lower-body load"
    )
    session_density_max: int = Field(2, ge=1, le=5, description="Max quality sessions in 7 days")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# COMPONENT MODELS
# ============================================================


class WorkoutReference(BaseModel):
    """Reference to a workout file and basic metadata."""

    file_path: str = Field(..., description="Path to workout YAML file")
    date: date
    workout_type: str = Field(..., description="Type of workout (easy, tempo, intervals, etc.)")
    is_key_workout: bool = Field(False, description="Is this a key session for the week?")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class ProposedChange(BaseModel):
    """Proposed modifications to a workout."""

    workout_type: Optional[str] = Field(None, description="New workout type (if changing)")
    duration_minutes: Optional[int] = Field(None, ge=0, description="New duration")
    distance_km: Optional[float] = Field(None, ge=0, description="New distance")
    intensity_zone: Optional[str] = Field(None, description="New intensity zone")
    target_rpe: Optional[int] = Field(None, ge=1, le=10, description="New target RPE")
    notes: Optional[str] = Field(None, description="Explanation of changes")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class Suggestion(BaseModel):
    """
    Adaptation suggestion requiring user approval.

    Represents a proposed workout modification based on athlete state.
    User can accept (apply changes) or decline (keep original).
    """

    # Identity
    id: str = Field(..., description="Unique suggestion identifier")
    created_at: datetime = Field(default_factory=datetime.now, description="When suggestion was generated")
    expires_at: datetime = Field(..., description="When suggestion expires (end of workout day)")

    # Trigger information
    trigger: AdaptationTrigger = Field(..., description="What triggered this suggestion")
    trigger_value: Optional[float] = Field(None, description="Metric value that triggered (e.g., ACWR=1.45)")

    # Affected workout
    affected_workout: WorkoutReference = Field(..., description="Workout to be modified")

    # Changes
    suggestion_type: SuggestionType = Field(..., description="Type of adaptation")
    proposed: ProposedChange = Field(..., description="Proposed modifications")

    # Rationale
    rationale: str = Field(..., description="Human-readable explanation of why")
    override_risk: OverrideRisk = Field(..., description="Risk level if user declines")

    # Status
    status: SuggestionStatus = Field(SuggestionStatus.PENDING, description="Current status")
    user_comment: Optional[str] = Field(None, description="User's comment when accepting/declining")
    resolved_at: Optional[datetime] = Field(None, description="When user made decision")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class SafetyOverride(BaseModel):
    """
    Auto-applied adaptation for safety-critical situations.

    Unlike suggestions, these are applied immediately without user approval.
    User may be able to override with explicit acknowledgment of risk.
    """

    # Identity
    id: str = Field(..., description="Unique override identifier")
    applied_at: datetime = Field(default_factory=datetime.now)

    # Trigger information
    trigger: AdaptationTrigger = Field(..., description="Safety trigger")
    trigger_details: dict = Field(default_factory=dict, description="Additional context")

    # Affected workout
    affected_workout: WorkoutReference = Field(..., description="Workout that was modified")

    # Action taken
    action_taken: str = Field(..., description="What was changed (e.g., 'Changed to rest day')")
    duration_days: int = Field(1, ge=1, description="How many days affected (for illness/injury)")

    # Override capability
    user_can_override: bool = Field(False, description="Can user override this?")
    override_warning: Optional[str] = Field(None, description="Warning if user attempts override")

    # Outcome
    user_overrode: bool = Field(False, description="Did user override?")
    override_comment: Optional[str] = Field(None, description="User's override comment")

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class AdaptationResult(BaseModel):
    """
    Complete result of adaptation analysis.

    Returned by M11.generate_adaptation_suggestions(). Contains all
    suggestions, safety overrides, and warnings for upcoming workouts.
    """

    # Analysis metadata
    analyzed_at: datetime = Field(default_factory=datetime.now)
    analysis_date_range: dict = Field(
        ...,
        description="Date range analyzed (e.g., {'start': '2026-01-15', 'end': '2026-01-18'})"
    )

    # Suggestions (require user approval)
    suggestions: list[Suggestion] = Field(
        default_factory=list,
        description="Pending suggestions for user review"
    )

    # Safety overrides (already applied)
    safety_overrides: list[SafetyOverride] = Field(
        default_factory=list,
        description="Auto-applied safety modifications"
    )

    # Warnings (informational, no action required)
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings (e.g., 'Approaching ACWR caution zone')"
    )

    # Metrics snapshot
    metrics_snapshot: Optional[dict] = Field(
        None,
        description="Current metrics (CTL/ATL/TSB/ACWR/readiness) at analysis time"
    )

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )
