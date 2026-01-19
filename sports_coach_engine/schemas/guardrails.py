"""
Guardrails and Recovery schemas.

Pydantic models for volume validation, progression checks, and recovery protocols
based on Daniels' Running Formula and Pfitzinger's guidelines.
"""

from typing import List, Optional, Tuple
from datetime import date
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================
# ENUMS
# ============================================================


class ViolationSeverity(str, Enum):
    """Severity level of a guardrail violation."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryPhase(str, Enum):
    """Phase in recovery progression."""

    REST = "rest"
    EASY_RETURN = "easy_return"
    GRADUAL_BUILD = "gradual_build"
    FULL_TRAINING = "full_training"


class IllnessSeverity(str, Enum):
    """Severity of illness for recovery planning."""

    MILD = "mild"  # 1-3 days, minimal impact
    MODERATE = "moderate"  # 4-7 days, noticeable impact
    SEVERE = "severe"  # 8+ days, significant impact


# ============================================================
# SUPPORTING TYPES
# ============================================================


class Violation(BaseModel):
    """A guardrail violation with context and recommendations."""

    type: str = Field(..., description="Violation type identifier")
    severity: ViolationSeverity = Field(..., description="How serious the violation is")
    message: str = Field(..., description="Clear description of the violation")
    current_value: Optional[float] = Field(None, description="Current value that triggered violation")
    limit_value: Optional[float] = Field(None, description="Safe limit value")
    recommendation: str = Field(..., description="Specific action to resolve violation")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "I_PACE_VOLUME_EXCEEDED",
                "severity": "moderate",
                "message": "I-pace volume (6km) exceeds safe limit (4km)",
                "current_value": 6.0,
                "limit_value": 4.0,
                "recommendation": "Reduce interval session to 4x1000m instead of 6x1000m",
            }
        }


class WeekSchedule(BaseModel):
    """A week in a recovery or return schedule."""

    week_number: int = Field(..., ge=1, description="Week number in schedule")
    load_pct: int = Field(..., ge=0, le=100, description="Percentage of normal training load")
    volume_km: Optional[float] = Field(None, description="Target weekly volume in km")
    description: str = Field(..., description="Guidance for this week")

    class Config:
        json_schema_extra = {
            "example": {
                "week_number": 1,
                "load_pct": 50,
                "volume_km": 15.0,
                "description": "Easy runs only, monitor for soreness",
            }
        }


class DayActivity(BaseModel):
    """A day's activity in a recovery schedule."""

    day_number: int = Field(..., ge=1, description="Day number in recovery")
    activity: str = Field(..., description="Recommended activity")
    load_au: Optional[int] = Field(None, description="Expected load in AU")
    rpe_max: Optional[int] = Field(None, ge=1, le=10, description="Maximum RPE allowed")

    class Config:
        json_schema_extra = {
            "example": {
                "day_number": 1,
                "activity": "20min walk",
                "load_au": 20,
                "rpe_max": 3,
            }
        }


# ============================================================
# VOLUME & LOAD GUARDRAILS
# ============================================================


class QualityVolumeValidation(BaseModel):
    """Validation of T/I/R pace volumes against Daniels' limits."""

    weekly_mileage_km: float = Field(..., description="Total weekly mileage")

    # Threshold pace validation
    t_pace_volume_km: float = Field(..., description="Actual T-pace volume")
    t_pace_limit_km: float = Field(..., description="Safe T-pace limit (10% of weekly)")
    t_pace_ok: bool = Field(..., description="Whether T-pace volume is safe")

    # Interval pace validation
    i_pace_volume_km: float = Field(..., description="Actual I-pace volume")
    i_pace_limit_km: float = Field(..., description="Safe I-pace limit (lesser of 10km or 8%)")
    i_pace_ok: bool = Field(..., description="Whether I-pace volume is safe")

    # Repetition pace validation
    r_pace_volume_km: float = Field(..., description="Actual R-pace volume")
    r_pace_limit_km: float = Field(..., description="Safe R-pace limit (lesser of 8km or 5%)")
    r_pace_ok: bool = Field(..., description="Whether R-pace volume is safe")

    violations: List[Violation] = Field(default_factory=list, description="List of violations found")
    overall_ok: bool = Field(..., description="Whether all quality volumes are safe")

    class Config:
        json_schema_extra = {
            "example": {
                "weekly_mileage_km": 50.0,
                "t_pace_volume_km": 4.5,
                "t_pace_limit_km": 5.0,
                "t_pace_ok": True,
                "i_pace_volume_km": 6.0,
                "i_pace_limit_km": 4.0,
                "i_pace_ok": False,
                "r_pace_volume_km": 2.0,
                "r_pace_limit_km": 2.5,
                "r_pace_ok": True,
                "violations": [],
                "overall_ok": False,
            }
        }


class WeeklyProgressionValidation(BaseModel):
    """Validation of weekly volume progression (10% rule)."""

    previous_volume_km: float = Field(..., description="Previous week's volume")
    current_volume_km: float = Field(..., description="Current week's planned volume")
    increase_km: float = Field(..., description="Absolute increase in km")
    increase_pct: float = Field(..., description="Percentage increase")
    safe_max_km: float = Field(..., description="Safe maximum based on 10% rule")
    ok: bool = Field(..., description="Whether progression is safe")
    violation: Optional[str] = Field(None, description="Description of violation if any")
    recommendation: Optional[str] = Field(None, description="Recommended action")

    class Config:
        json_schema_extra = {
            "example": {
                "previous_volume_km": 40.0,
                "current_volume_km": 50.0,
                "increase_km": 10.0,
                "increase_pct": 25.0,
                "safe_max_km": 44.0,
                "ok": False,
                "violation": "Weekly volume increased by 25% (safe max: 10%)",
                "recommendation": "Reduce Week 5 volume to 44km",
            }
        }


class LongRunValidation(BaseModel):
    """Validation of long run against weekly volume and duration limits."""

    long_run_km: float = Field(..., description="Long run distance")
    long_run_duration_minutes: int = Field(..., description="Long run duration")
    weekly_volume_km: float = Field(..., description="Total weekly volume")

    # Percentage of weekly volume check
    pct_of_weekly: float = Field(..., description="Long run as % of weekly volume")
    pct_limit: float = Field(default=30.0, description="Safe percentage limit")
    pct_ok: bool = Field(..., description="Whether percentage is safe")

    # Duration check (Daniels: max 2.5 hours for most runners)
    duration_limit_minutes: int = Field(default=150, description="Duration limit (150 min)")
    duration_ok: bool = Field(..., description="Whether duration is safe")

    violations: List[Violation] = Field(default_factory=list, description="List of violations")
    overall_ok: bool = Field(..., description="Whether long run is safe")

    class Config:
        json_schema_extra = {
            "example": {
                "long_run_km": 18.0,
                "long_run_duration_minutes": 135,
                "weekly_volume_km": 50.0,
                "pct_of_weekly": 36.0,
                "pct_limit": 30.0,
                "pct_ok": False,
                "duration_limit_minutes": 150,
                "duration_ok": True,
                "violations": [],
                "overall_ok": False,
            }
        }


class SafeVolumeRange(BaseModel):
    """Safe weekly volume range based on current fitness and goals."""

    current_ctl: float = Field(..., description="Current chronic training load")
    ctl_zone: str = Field(..., description="CTL fitness zone (beginner/recreational/competitive/advanced)")

    base_volume_range_km: Tuple[int, int] = Field(..., description="Base weekly volume range for CTL")
    goal_adjusted_range_km: Tuple[int, int] = Field(..., description="Adjusted for race goal")
    masters_adjusted_range_km: Optional[Tuple[int, int]] = Field(
        None, description="Adjusted for age if masters athlete"
    )

    recent_weekly_volume_km: Optional[float] = Field(
        None, description="Actual recent running volume (last 4 weeks average)"
    )
    volume_gap_pct: Optional[float] = Field(
        None, description="Percentage gap between recent volume and CTL-based recommendation"
    )

    recommended_start_km: int = Field(..., description="Recommended starting weekly volume")
    recommended_peak_km: int = Field(..., description="Recommended peak weekly volume")
    recommendation: str = Field(..., description="Guidance on volume progression")

    warning: Optional[str] = Field(
        None, description="Warning if target volume conflicts with run frequency (minimum volume constraints)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "current_ctl": 44.0,
                "ctl_zone": "recreational",
                "base_volume_range_km": (30, 45),
                "goal_adjusted_range_km": (35, 50),
                "masters_adjusted_range_km": (30, 45),
                "recommended_start_km": 35,
                "recommended_peak_km": 50,
                "recommendation": "Start at 35km/week, build to 50km over 8-12 weeks",
            }
        }


# ============================================================
# RECOVERY CALCULATIONS
# ============================================================


class BreakReturnPlan(BaseModel):
    """Structured return-to-training plan after a break."""

    break_duration_days: int = Field(..., description="Length of training break")
    pre_break_ctl: float = Field(..., description="CTL before the break")
    cross_training_level: str = Field(..., description="Level of cross-training during break")

    # Daniels Table 9.2 adjustments
    load_phase_1_pct: int = Field(..., description="Load % for first half of return")
    load_phase_2_pct: int = Field(..., description="Load % for second half of return")
    vdot_adjustment_pct: int = Field(..., description="VDOT adjustment % (95-100)")

    return_schedule: List[WeekSchedule] = Field(..., description="Week-by-week return plan")
    estimated_full_return_weeks: int = Field(..., description="Weeks to full training")

    red_flags: List[str] = Field(default_factory=list, description="Warning signs to watch for")

    class Config:
        json_schema_extra = {
            "example": {
                "break_duration_days": 21,
                "pre_break_ctl": 44.0,
                "cross_training_level": "moderate",
                "load_phase_1_pct": 50,
                "load_phase_2_pct": 75,
                "vdot_adjustment_pct": 95,
                "return_schedule": [],
                "estimated_full_return_weeks": 3,
                "red_flags": ["Monitor for excessive soreness"],
            }
        }


class MastersRecoveryAdjustment(BaseModel):
    """Age-specific recovery adjustments for masters athletes (Pfitzinger)."""

    age: int = Field(..., ge=18, description="Athlete age")
    age_bracket: str = Field(..., description="Age bracket (e.g., '46-55')")
    base_recovery_days: int = Field(..., description="Base recovery days for workout type")

    # Adjustments by workout type
    adjustments: dict[str, int] = Field(..., description="Additional recovery days by workout type")
    recommended_recovery_days: dict[str, int] = Field(..., description="Total recovery days by type")

    note: str = Field(..., description="Additional guidance")

    class Config:
        json_schema_extra = {
            "example": {
                "age": 52,
                "age_bracket": "46-55",
                "base_recovery_days": 1,
                "adjustments": {"vo2max": 2, "tempo": 1, "long_run": 1},
                "recommended_recovery_days": {"vo2max": 3, "tempo": 2, "long_run": 2},
                "note": "Consider additional rest if fatigue elevated",
            }
        }


class RaceRecoveryPlan(BaseModel):
    """Post-race recovery protocol based on distance and age."""

    race_distance: str = Field(..., description="Race distance")
    athlete_age: int = Field(..., description="Athlete age")
    effort: str = Field(..., description="Finishing effort level")

    # Pfitzinger masters table
    minimum_recovery_days: int = Field(..., description="Minimum recovery needed")
    recommended_recovery_days: int = Field(..., description="Recommended total recovery")

    recovery_schedule: List[str] = Field(..., description="Day-by-day recovery guidance")
    quality_work_resume_day: int = Field(..., description="Day to resume quality workouts")

    red_flags: List[str] = Field(default_factory=list, description="Warning signs")

    class Config:
        json_schema_extra = {
            "example": {
                "race_distance": "half_marathon",
                "athlete_age": 52,
                "effort": "hard",
                "minimum_recovery_days": 9,
                "recommended_recovery_days": 11,
                "recovery_schedule": [],
                "quality_work_resume_day": 11,
                "red_flags": ["If soreness persists >3 days, extend easy period"],
            }
        }


class IllnessRecoveryPlan(BaseModel):
    """Structured return after illness."""

    illness_duration_days: int = Field(..., description="Days of illness")
    severity: IllnessSeverity = Field(..., description="Illness severity")
    estimated_ctl_drop: float = Field(..., description="Expected CTL drop during illness")

    return_protocol: List[DayActivity] = Field(..., description="Day-by-day return plan")
    full_training_resume_day: int = Field(..., description="Day to resume full training")

    red_flags: List[str] = Field(default_factory=list, description="Signs to stop training")
    medical_consultation_triggers: List[str] = Field(
        default_factory=list, description="When to seek medical advice"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "illness_duration_days": 5,
                "severity": "moderate",
                "estimated_ctl_drop": 8.0,
                "return_protocol": [],
                "full_training_resume_day": 14,
                "red_flags": ["Elevated resting HR", "Persistent fatigue"],
                "medical_consultation_triggers": ["Symptoms persist >7 days"],
            }
        }
