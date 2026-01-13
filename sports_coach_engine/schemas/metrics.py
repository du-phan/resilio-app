"""
Metrics schemas - Training metrics data models.

This module defines all Pydantic schemas for training metrics computation,
including CTL/ATL/TSB (fitness/fatigue/form), ACWR (injury risk), and
readiness scores. These schemas support the M9 Metrics Engine.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from enum import Enum


# ============================================================
# ENUMS
# ============================================================


class TSBZone(str, Enum):
    """Training Stress Balance zones."""
    OVERREACHED = "overreached"      # < -25 (excessive fatigue)
    PRODUCTIVE = "productive"         # -25 to -10 (building fitness)
    OPTIMAL = "optimal"              # -10 to +5 (ready for quality)
    FRESH = "fresh"                  # +5 to +15 (good for racing)
    PEAKED = "peaked"                # > +15 (possibly detrained)


class ACWRZone(str, Enum):
    """Acute:Chronic Workload Ratio zones for injury risk."""
    UNDERTRAINED = "undertrained"    # < 0.8 (fitness declining)
    SAFE = "safe"                    # 0.8-1.3 (optimal adaptation)
    CAUTION = "caution"              # 1.3-1.5 (elevated injury risk)
    HIGH_RISK = "high_risk"          # > 1.5 (2-4x injury probability)


class ReadinessLevel(str, Enum):
    """Readiness level classifications."""
    REST_RECOMMENDED = "rest_recommended"      # < 35
    EASY_ONLY = "easy_only"                   # 35-49
    REDUCE_INTENSITY = "reduce_intensity"     # 50-64
    READY = "ready"                           # 65-79
    PRIMED = "primed"                         # 80-100


class ConfidenceLevel(str, Enum):
    """Confidence level for computed metrics."""
    LOW = "low"          # < 14 days data or missing subjective inputs
    MEDIUM = "medium"    # 14-42 days data or partial inputs
    HIGH = "high"        # 42+ days data with complete inputs


class CTLZone(str, Enum):
    """CTL (fitness) level zones."""
    BEGINNER = "beginner"              # < 20
    DEVELOPING = "developing"          # 20-40
    RECREATIONAL = "recreational"      # 40-60
    TRAINED = "trained"                # 60-80
    COMPETITIVE = "competitive"        # 80-100
    ELITE = "elite"                    # > 100


# ============================================================
# COMPONENT MODELS
# ============================================================


class DailyLoad(BaseModel):
    """Aggregated load for a single day from all activities."""

    date: date
    systemic_load_au: float
    lower_body_load_au: float
    activity_count: int
    activities: list[dict] = Field(default_factory=list)  # Summary info per activity

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class CTLATLMetrics(BaseModel):
    """CTL/ATL/TSB metrics with zone classification."""

    ctl: float                      # Chronic Training Load (42-day EWMA)
    atl: float                      # Acute Training Load (7-day EWMA)
    tsb: float                      # Training Stress Balance (CTL - ATL)

    # Zone classifications
    ctl_zone: CTLZone               # Fitness level classification
    tsb_zone: TSBZone               # Form status classification

    # Trends (optional, computed if history available)
    ctl_trend: Optional[str] = None          # "building", "maintaining", "declining"
    ctl_change_7d: Optional[float] = None    # Change from 7 days ago

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class ACWRMetrics(BaseModel):
    """ACWR metrics with safety zone classification."""

    acwr: float                     # Acute:Chronic ratio
    zone: ACWRZone                  # Risk zone classification

    # Components
    acute_load_7d: float            # Sum of last 7 days
    chronic_load_28d: float         # Average of last 28 days

    # Safety flag
    injury_risk_elevated: bool      # True if > 1.3

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class ReadinessComponents(BaseModel):
    """Breakdown of readiness score components."""

    tsb_contribution: float                    # 0-100, weighted by 20%
    load_trend_contribution: float             # 0-100, weighted by 25%
    sleep_contribution: Optional[float] = None      # 0-100, weighted by 25%
    wellness_contribution: Optional[float] = None   # 0-100, weighted by 30%

    # Actual weights used (sum to 100%, redistributed if components missing)
    weights_used: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class ReadinessScore(BaseModel):
    """Complete readiness assessment with confidence."""

    score: int  # 0-100
    level: ReadinessLevel
    confidence: ConfidenceLevel

    # Components breakdown
    components: ReadinessComponents

    # Recommendation text
    recommendation: str  # "Execute as planned", "Consider easy effort", etc.

    # Safety overrides applied
    injury_flag_override: bool = False
    illness_flag_override: bool = False
    override_reason: Optional[str] = None

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class IntensityDistribution(BaseModel):
    """Weekly intensity breakdown for 80/20 tracking."""

    low_minutes: float        # RPE 1-4 or easy sessions
    moderate_minutes: float   # RPE 5-6 or moderate sessions
    high_minutes: float       # RPE 7-10 or quality/race sessions

    # Percentage calculations
    low_percent: float
    moderate_percent: float
    high_percent: float

    # 80/20 compliance (only checked if >= 3 run days/week)
    is_compliant: Optional[bool] = None
    target_low_percent: Optional[float] = None  # Target ~80%

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# MAIN MODELS
# ============================================================


class DailyMetrics(BaseModel):
    """Complete daily metrics output (persisted to metrics/daily/YYYY-MM-DD.yaml)."""

    # Schema metadata
    schema_metadata: dict = Field(
        default_factory=lambda: {
            "format_version": "1.0.0",
            "schema_type": "daily_metrics"
        },
        alias="_schema",
    )

    # Basic info
    date: date
    calculated_at: datetime

    # Daily load aggregation
    daily_load: DailyLoad

    # CTL/ATL/TSB metrics
    ctl_atl: CTLATLMetrics

    # ACWR (None if < 28 days history)
    acwr: Optional[ACWRMetrics] = None

    # Readiness assessment
    readiness: ReadinessScore

    # Data quality flags
    baseline_established: bool      # False if < 14 days
    acwr_available: bool           # False if < 28 days
    data_days_available: int       # Total days with data

    # Activity flags (injury, illness, etc.)
    flags: list[str] = Field(default_factory=list)  # e.g., ["injury:knee", "illness:cold"]

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class WeeklySummary(BaseModel):
    """Weekly aggregation of training metrics (persisted to metrics/weekly_summary.yaml)."""

    # Schema metadata
    schema_metadata: dict = Field(
        default_factory=lambda: {
            "format_version": "1.0.0",
            "schema_type": "weekly_summary"
        },
        alias="_schema",
    )

    # Week identification
    week_start: date              # Monday
    week_end: date                # Sunday
    week_number: int              # ISO week number

    # Load totals
    total_systemic_load_au: float
    total_lower_body_load_au: float

    # Activity counts
    total_activities: int
    run_sessions: int
    other_sport_sessions: int

    # Session type breakdown
    easy_sessions: int
    moderate_sessions: int
    quality_sessions: int
    race_sessions: int

    # Intensity distribution (for 80/20 tracking)
    intensity_distribution: IntensityDistribution

    # High-intensity count (across ALL sports for fatigue gating)
    high_intensity_sessions_7d: int  # Quality + race sessions

    # End-of-week metrics snapshot
    ctl_end: float
    atl_end: float
    tsb_end: float
    acwr_end: Optional[float] = None

    # Notes
    notes: Optional[str] = None

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# ENRICHMENT MODELS (for M12 Data Enrichment, kept for compatibility)
# ============================================================


class MetricInterpretation(BaseModel):
    """A metric value with interpretive context."""
    value: float
    formatted_value: str
    zone: str
    interpretation: str
    trend: Optional[str] = None


class EnrichedMetrics(BaseModel):
    """Metrics with enriched context (for API layer display)."""
    date: date
    ctl: MetricInterpretation
    atl: MetricInterpretation
    tsb: MetricInterpretation
    acwr: Optional[MetricInterpretation] = None
    readiness: MetricInterpretation


class TrainingStatus(BaseModel):
    """Current training status (for API layer)."""
    fitness: MetricInterpretation
    fatigue: MetricInterpretation
    form: MetricInterpretation
    acwr: Optional[MetricInterpretation] = None
    readiness: MetricInterpretation


class WeeklyStatus(BaseModel):
    """Weekly status overview (for API layer)."""
    week_number: int
    phase: str
    days: list
    progress: dict
    load_summary: dict
    metrics: EnrichedMetrics
