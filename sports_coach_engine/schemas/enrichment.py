"""
Enrichment schemas - Data models for M12 Data Enrichment.

This module defines Pydantic schemas for enriched training data with
interpretive context. These models bridge raw metrics to natural language
responses by providing zone classifications, human-readable interpretations,
and contextual guidance.

M12 returns structured data (not prose) - Claude Code crafts conversational responses.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# ENUMS
# ============================================================


class DisclosureLevel(str, Enum):
    """Progressive disclosure level for metrics based on data history."""

    BASIC = "basic"                  # < 14 days: Volume and easy/hard distribution only
    INTERMEDIATE = "intermediate"    # 14-28 days: Add CTL/ATL/TSB
    ADVANCED = "advanced"            # 28+ days: Full metrics including ACWR


# ============================================================
# METRIC INTERPRETATION MODELS
# ============================================================


class MetricInterpretation(BaseModel):
    """A metric value with interpretive context for natural language responses."""

    name: str                        # "ctl", "tsb", "acwr", etc.
    display_name: str                # "Fitness (CTL)", "Form (TSB)"
    value: float                     # Raw numeric value
    formatted_value: str             # "44", "+8", "1.15"
    zone: str                        # Classification zone
    interpretation: str              # "solid recreational level"
    trend: Optional[str] = None      # "+2 from last week" or None
    explanation: Optional[str] = None  # Educational text for the metric

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class ReadinessSummary(BaseModel):
    """Primary readiness signal for quick decision-making."""

    score: int
    level: str
    confidence: Optional[str] = None
    data_coverage: Optional[str] = None

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class LoadSpikeSummary(BaseModel):
    """Primary load spike signal based on ACWR."""

    acwr: Optional[float] = None
    zone: Optional[str] = None
    available: bool = False
    caveat: Optional[str] = None

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class PrimarySignals(BaseModel):
    """Primary signals summary for the AI Coach."""

    readiness: ReadinessSummary
    load_spike: LoadSpikeSummary

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class EnrichedMetrics(BaseModel):
    """Complete metrics snapshot with interpretations."""

    date: date
    ctl: MetricInterpretation
    atl: MetricInterpretation
    tsb: MetricInterpretation
    acwr: Optional[MetricInterpretation] = None  # Requires 28+ days
    readiness: MetricInterpretation
    disclosure_level: DisclosureLevel
    primary_signals: Optional[PrimarySignals] = None

    # Intensity distribution (always included)
    low_intensity_percent: float     # Percent in zone 1-2
    intensity_on_target: bool        # Meeting 80/20 guideline?

    # Week-over-week changes
    ctl_weekly_change: Optional[float] = None
    training_load_trend: Optional[str] = None  # "increasing", "stable", "decreasing"

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# WORKOUT ENRICHMENT MODELS
# ============================================================


class WorkoutRationale(BaseModel):
    """Explanation for why a workout is prescribed."""

    primary_reason: str              # "Form is good"
    training_purpose: str            # "threshold work improves lactate clearance"
    phase_context: Optional[str] = None  # "Building aerobic foundation"
    safety_notes: list[str] = Field(default_factory=list)  # Any warnings

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class PaceGuidance(BaseModel):
    """Pace guidance with context."""

    target_min_per_km: float         # 5.25
    target_max_per_km: float         # 5.42
    formatted: str                   # "5:15-5:25/km"
    feel_description: str            # "comfortably hard"

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class HRGuidance(BaseModel):
    """Heart rate guidance with context."""

    target_low: int                  # 160
    target_high: int                 # 170
    formatted: str                   # "160-170 bpm"
    zone_name: str                   # "Threshold"

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


class EnrichedWorkout(BaseModel):
    """Workout prescription with full context for natural language responses."""

    # Core workout data
    workout_id: str
    date: date
    workout_type: str                # "tempo", "easy", "long_run"
    workout_type_display: str        # "Tempo Run"
    duration_minutes: int
    duration_formatted: str          # "45 minutes"

    # Intensity
    target_rpe: int
    intensity_zone: str              # "zone_4"
    intensity_description: str       # "Threshold"

    # Guidance
    pace_guidance: Optional[PaceGuidance] = None
    hr_guidance: Optional[HRGuidance] = None
    purpose: str                     # "Build lactate threshold"

    # Context
    rationale: WorkoutRationale
    current_readiness: MetricInterpretation

    # Adaptations
    has_pending_suggestion: bool = False
    suggestion_summary: Optional[str] = None  # "Consider reducing intensity"

    # Notes
    coach_notes: Optional[str] = None

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# LOAD INTERPRETATION MODELS
# ============================================================


class LoadInterpretation(BaseModel):
    """Load value with sport-specific context."""

    systemic_load_au: float
    lower_body_load_au: float
    systemic_description: str        # "moderate session"
    lower_body_description: str      # "light impact"
    combined_assessment: str         # "Good recovery day with upper body work"

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# SYNC SUMMARY MODELS
# ============================================================


class SyncSummary(BaseModel):
    """Enriched summary of a sync operation."""

    activities_imported: int
    activities_skipped: int
    activities_failed: int

    # What was imported (brief)
    activity_types: list[str]        # ["Running", "Cycling", "Bouldering"]
    total_duration_minutes: int
    total_load_au: float

    # Profile updates
    profile_fields_updated: Optional[list[str]] = None  # Fields auto-filled from Strava athlete profile

    # Metric changes
    metrics_before: Optional[EnrichedMetrics] = None
    metrics_after: Optional[EnrichedMetrics] = None  # None if enrichment fails
    metric_changes: list[str]        # ["CTL +2", "TSB -5"]

    # Suggestions
    suggestions_generated: int
    suggestion_summaries: list[str]  # ["Consider rest day tomorrow"]

    # Errors
    has_errors: bool
    error_summaries: list[str]

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )


# ============================================================
# SUGGESTION ENRICHMENT MODELS
# ============================================================


class EnrichedSuggestion(BaseModel):
    """Adaptation suggestion with full context."""

    suggestion_id: str
    suggestion_type: str             # "downgrade", "skip", "move"
    suggestion_type_display: str     # "Reduce intensity"

    # What's affected
    affected_date: date
    affected_workout_type: str       # "intervals"
    affected_workout_display: str    # "Interval Session"

    # The change
    original_description: str        # "Intervals @ RPE 8"
    proposed_description: str        # "Easy run @ RPE 4"

    # Why
    rationale: str                   # "ACWR is 1.4, approaching caution zone"
    safety_level: str                # "recommended", "suggested", "optional"
    override_risk: str               # "low", "medium", "high"

    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
    )
