"""
Weekly analysis and risk assessment schemas.

Pydantic models for intensity distribution validation, activity gap detection,
load distribution, capacity checks, risk assessment, recovery windows,
training stress forecasting, and taper status tracking.
"""

from typing import List, Optional, Dict, Tuple, Any
from datetime import date
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================
# ENUMS
# ============================================================


class RiskLevel(str, Enum):
    """Risk level for injury or overtraining."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    DANGER = "danger"


class ComplianceLevel(str, Enum):
    """Compliance level for intensity distribution (80/20 rule)."""

    EXCELLENT = "excellent"  # Within 5% of target
    GOOD = "good"  # Within 10% of target
    FAIR = "fair"  # Within 15% of target
    POOR = "poor"  # >15% deviation
    MODERATE_INTENSITY_RUT = "moderate_intensity_rut"  # Too much Zone 3


class TaperPhase(str, Enum):
    """Phase in taper progression."""

    WEEK_3_OUT = "week_3_out"
    WEEK_2_OUT = "week_2_out"
    RACE_WEEK = "race_week"
    POST_RACE = "post_race"


# ============================================================
# SUPPORTING TYPES
# ============================================================


class ActivityGap(BaseModel):
    """Detected gap in training."""

    start_date: date = Field(..., description="Gap start date")
    end_date: date = Field(..., description="Gap end date")
    duration_days: int = Field(..., description="Gap duration in days")
    ctl_before: Optional[float] = Field(None, description="CTL before gap")
    ctl_after: Optional[float] = Field(None, description="CTL after gap")
    ctl_drop_pct: Optional[float] = Field(None, description="CTL drop percentage")
    potential_cause: Optional[str] = Field(None, description="Potential reason (injury, illness, etc.)")
    evidence: List[str] = Field(default_factory=list, description="Evidence for cause (keywords from notes)")


class RiskFactor(BaseModel):
    """Contributing factor to injury/overtraining risk."""

    name: str = Field(..., description="Factor identifier (e.g., ACWR_ELEVATED)")
    value: float = Field(..., description="Current value")
    threshold: float = Field(..., description="Safe threshold")
    severity: str = Field(..., description="Severity level (low/moderate/high)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight in overall risk (0-1)")


class RiskOption(BaseModel):
    """Option for managing current risk."""

    action: str = Field(..., description="Action identifier")
    risk_reduction_pct: float = Field(..., description="Expected risk reduction percentage")
    description: str = Field(..., description="Human-readable description")
    pros: List[str] = Field(..., description="Advantages of this option")
    cons: List[str] = Field(..., description="Disadvantages of this option")


class RecoveryCheckpoint(BaseModel):
    """Checkpoint in recovery timeline."""

    day: int = Field(..., description="Day number")
    action: str = Field(..., description="Recommended action")
    check: str = Field(..., description="What to check/monitor")


class WeekForecast(BaseModel):
    """Forecast for a single week."""

    week_number: int = Field(..., description="Week number in plan")
    end_date: date = Field(..., description="Week end date")
    projected_ctl: float = Field(..., description="Projected CTL")
    projected_atl: float = Field(..., description="Projected ATL")
    projected_tsb: float = Field(..., description="Projected TSB")
    projected_acwr: float = Field(..., description="Projected ACWR")
    readiness_estimate: str = Field(..., description="Estimated readiness level")
    risk_level: RiskLevel = Field(..., description="Projected risk level")
    warning: Optional[str] = Field(None, description="Warning if elevated risk")


class RiskWindow(BaseModel):
    """Period of elevated risk."""

    week_number: int = Field(..., description="Week with elevated risk")
    risk_level: RiskLevel = Field(..., description="Risk level")
    reason: str = Field(..., description="Why risk is elevated")
    recommendation: str = Field(..., description="Suggested mitigation")


class VolumeReductionCheck(BaseModel):
    """Volume reduction verification for taper."""

    week_label: str = Field(..., description="Week label (e.g., 'week_minus_3')")
    target_pct: int = Field(..., description="Target volume percentage")
    actual_pct: Optional[int] = Field(None, description="Actual volume percentage")
    on_track: bool = Field(..., description="Whether reduction is on track")
    status: str = Field(..., description="Status description")


class TSBTrajectory(BaseModel):
    """TSB progression toward race day."""

    current_tsb: float = Field(..., description="Current TSB value")
    target_race_day_tsb_range: Tuple[float, float] = Field(..., description="Target TSB range for race")
    projected_race_day_tsb: float = Field(..., description="Projected race day TSB")
    on_track: bool = Field(..., description="Whether TSB trajectory is good")


class ReadinessTrend(BaseModel):
    """Readiness trend during taper."""

    week_minus_3_avg: Optional[float] = Field(None, description="Average readiness 3 weeks out")
    week_minus_2_avg: Optional[float] = Field(None, description="Average readiness 2 weeks out")
    current_avg: float = Field(..., description="Current average readiness")
    trend: str = Field(..., description="Trend direction (improving/stable/declining)")
    on_track: bool = Field(..., description="Whether trend is positive")


class IntensityDistributionAnalysis(BaseModel):
    """Validation of intensity distribution (80/20 rule)."""

    date_range_days: int = Field(..., description="Rolling window in days (typically 28)")
    total_activities: int = Field(..., description="Total activities analyzed")
    total_duration_minutes: int = Field(..., description="Total training duration")

    distribution: Dict[str, float] = Field(
        ..., description="Intensity distribution: low/moderate/high percentages"
    )

    target_distribution: Dict[str, float] = Field(
        ..., description="Target 80/20 distribution"
    )

    compliance: ComplianceLevel = Field(..., description="Compliance level with 80/20 rule")

    violations: List[str] = Field(
        default_factory=list, description="Violations of 80/20 rule"
    )

    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations to improve distribution"
    )

    polarization_score: int = Field(
        ..., ge=0, le=100, description="Polarization score (0-100, higher = better 80/20)"
    )

    note: Optional[str] = Field(None, description="Additional context or notes")


class ActivityGapAnalysis(BaseModel):
    """Analysis of training breaks/gaps."""

    gaps: List[ActivityGap] = Field(..., description="Detected training gaps")

    total_gaps: int = Field(..., description="Total number of gaps found")
    total_gap_days: int = Field(..., description="Total days of gaps")

    patterns: List[str] = Field(
        default_factory=list, description="Patterns detected in gaps"
    )

    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations based on gap analysis"
    )


class LoadDistributionAnalysis(BaseModel):
    """Multi-sport load breakdown."""

    date_range_days: int = Field(..., description="Analysis window in days")

    systemic_load_by_sport: Dict[str, float] = Field(
        ..., description="Systemic load in AU by sport with percentages"
    )

    lower_body_load_by_sport: Dict[str, float] = Field(
        ..., description="Lower-body load in AU by sport with percentages"
    )

    total_systemic_load: float = Field(..., description="Total systemic load across all sports")
    total_lower_body_load: float = Field(..., description="Total lower-body load")

    sport_priority_adherence: Dict[str, Any] = Field(
        ..., description="Adherence to sport priority preferences"
    )

    fatigue_risk_flags: List[str] = Field(
        default_factory=list, description="Flags for fatigue risk from sport distribution"
    )

    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for load distribution"
    )


class WeeklyCapacityCheck(BaseModel):
    """Validation of planned volume against proven capacity."""

    week_number: int = Field(..., description="Week number in plan")
    planned_volume_km: float = Field(..., description="Planned weekly volume")
    planned_systemic_load_au: float = Field(..., description="Planned systemic load")

    historical_max_volume_km: float = Field(..., description="Historical maximum weekly volume")
    historical_max_systemic_load_au: float = Field(..., description="Historical maximum systemic load")

    capacity_utilization_km: float = Field(..., description="Volume capacity utilization percentage")
    capacity_utilization_load: float = Field(..., description="Load capacity utilization percentage")

    exceeds_proven_capacity: bool = Field(..., description="Whether plan exceeds proven capacity")

    risk_assessment: str = Field(..., description="Risk level (low/moderate/high)")
    risk_factors: List[str] = Field(
        default_factory=list, description="Specific risk factors identified"
    )

    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for capacity management"
    )


# ============================================================
# RISK ASSESSMENT SCHEMAS
# ============================================================


class CurrentRiskAssessment(BaseModel):
    """Holistic risk assessment combining all factors."""

    overall_risk_level: RiskLevel = Field(..., description="Overall risk level")
    risk_index_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Heuristic risk index (0-100), not a medical probability"
    )

    contributing_factors: List[RiskFactor] = Field(
        ..., description="Factors contributing to current risk"
    )

    recommended_action: str = Field(..., description="Primary recommended action")

    options: List[RiskOption] = Field(..., description="Options for managing risk")

    rationale: str = Field(..., description="Explanation of risk assessment and recommendation")

    recommendation: Optional[str] = Field(None, description="Final recommendation with context")


class RecoveryWindowEstimate(BaseModel):
    """Estimated time until metrics return to safe zone."""

    trigger: str = Field(..., description="Trigger type (e.g., ACWR_ELEVATED)")
    current_value: float = Field(..., description="Current metric value")
    safe_threshold: float = Field(..., description="Safe threshold value")

    estimated_recovery_days_min: int = Field(..., description="Minimum recovery days")
    estimated_recovery_days_typical: int = Field(..., description="Typical recovery days")
    estimated_recovery_days_max: int = Field(..., description="Maximum recovery days")

    recovery_checklist: List[RecoveryCheckpoint] = Field(
        ..., description="Day-by-day recovery checklist"
    )

    monitoring_metrics: List[str] = Field(..., description="Metrics to monitor during recovery")

    note: Optional[str] = Field(None, description="Additional context")


class TrainingStressForecast(BaseModel):
    """Projection of future CTL/ATL/TSB/ACWR."""

    weeks_ahead: int = Field(..., description="Number of weeks forecasted")
    current_date: date = Field(..., description="Forecast start date")

    forecast: List[WeekForecast] = Field(..., description="Week-by-week forecast")

    risk_windows: List[RiskWindow] = Field(
        default_factory=list, description="Periods of elevated risk"
    )

    proactive_adjustments: List[str] = Field(
        default_factory=list, description="Suggested proactive plan adjustments"
    )


class TaperStatusAssessment(BaseModel):
    """Taper progression verification."""

    race_date: date = Field(..., description="Upcoming race date")
    weeks_until_race: int = Field(..., description="Weeks remaining until race")
    taper_phase: TaperPhase = Field(..., description="Current taper phase")

    volume_reduction_check: Dict[str, VolumeReductionCheck] = Field(
        ..., description="Volume reduction verification by week"
    )

    tsb_trajectory: TSBTrajectory = Field(..., description="TSB progression toward race")

    readiness_trend: ReadinessTrend = Field(..., description="Readiness trend during taper")

    overall_taper_status: str = Field(..., description="Overall taper status (on_track/adjust_needed/concern)")

    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for taper adjustments"
    )

    red_flags: List[str] = Field(
        default_factory=list, description="Warning signs requiring attention"
    )
