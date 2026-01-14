"""
M12 - Data Enrichment

Add interpretive context to raw training data. Transform numbers into meaningful
insights that Claude Code uses to craft natural, conversational responses.

This module provides structured data with interpretations (not prose).
Claude Code handles all response formatting and conversational tone.

Key Design Principles:
- Data, not prose: Return Pydantic models with interpretive fields
- Context tables: Thresholds are data-driven and easy to tune
- Progressive disclosure: Beginners see simple info, advanced users get depth
- No AI/LLM calls: All interpretation is deterministic and testable
"""

from datetime import date, timedelta
from typing import Optional

from sports_coach_engine.schemas.enrichment import (
    DisclosureLevel,
    EnrichedMetrics,
    EnrichedSuggestion,
    EnrichedWorkout,
    HRGuidance,
    LoadInterpretation,
    MetricInterpretation,
    PaceGuidance,
    SyncSummary,
    WorkoutRationale,
)
from sports_coach_engine.schemas.metrics import DailyMetrics
from sports_coach_engine.schemas.plan import WorkoutPrescription
from sports_coach_engine.schemas.profile import AthleteProfile
from sports_coach_engine.schemas.adaptation import Suggestion


# ============================================================
# ERROR TYPES
# ============================================================


class EnrichmentError(Exception):
    """Base exception for enrichment errors."""
    pass


class InvalidMetricNameError(EnrichmentError):
    """Unknown metric name provided."""
    pass


# ============================================================
# CONTEXT TABLES (Thresholds and Interpretations)
# ============================================================


# CTL (Chronic Training Load) interpretation
# Based on typical recreational to elite fitness levels
CTL_CONTEXT: list[tuple[float, float, str, str]] = [
    (0, 20, "building base fitness", "beginner"),
    (20, 40, "developing fitness", "developing"),
    (40, 60, "solid recreational level", "recreational"),
    (60, 80, "well-trained", "trained"),
    (80, 100, "competitive amateur", "competitive"),
    (100, 9999, "elite amateur", "elite"),  # Extended upper bound for very high CTL
]

# TSB (Training Stress Balance) interpretation
# Negative = fatigued, Positive = fresh
TSB_CONTEXT: list[tuple[float, float, str, str]] = [
    (-100, -25, "overreached - recovery needed", "overreached"),
    (-25, -10, "productive training zone", "productive"),
    (-10, 5, "optimal for quality work", "optimal"),
    (5, 15, "fresh - good for racing", "fresh"),
    (15, 100, "peaked - may be detraining", "peaked"),
]

# ACWR (Acute:Chronic Workload Ratio) interpretation
# Based on injury risk research (Gabbett et al.)
ACWR_CONTEXT: list[tuple[float, float, str, str]] = [
    (0, 0.8, "undertrained - fitness declining", "undertrained"),
    (0.8, 1.3, "safe training zone", "safe"),
    (1.3, 1.5, "caution - monitor closely", "caution"),
    (1.5, 3.0, "high injury risk", "high_risk"),
]

# Readiness interpretation
# 0-100 scale combining form, load trend, and wellness
READINESS_CONTEXT: list[tuple[float, float, str, str]] = [
    (0, 35, "rest recommended", "rest_recommended"),
    (35, 50, "easy activity only", "easy_only"),
    (50, 70, "ready for normal training", "ready"),
    (70, 100, "primed for quality work", "primed"),
]

# Load descriptions
# Based on typical training load ranges
LOAD_CONTEXT: list[tuple[float, float, str]] = [
    (0, 100, "light recovery session"),
    (100, 300, "moderate session"),
    (300, 500, "solid workout"),
    (500, 700, "hard session"),
    (700, 2000, "very demanding session"),
]


# ============================================================
# CORE INTERPRETATION FUNCTIONS
# ============================================================


def interpret_metric(
    metric_name: str,
    value: float,
    previous_value: Optional[float] = None,
) -> MetricInterpretation:
    """
    Create interpretation for a single metric value.

    Args:
        metric_name: "ctl", "atl", "tsb", "acwr", or "readiness"
        value: Current metric value
        previous_value: Optional previous value for trend calculation

    Returns:
        MetricInterpretation with zone, interpretation, and optional trend

    Raises:
        InvalidMetricNameError: If metric_name is not recognized
    """
    # Map metric names to context tables and display names
    context_map = {
        "ctl": (CTL_CONTEXT, "Fitness (CTL)"),
        "atl": (None, "Fatigue (ATL)"),  # ATL doesn't have zones
        "tsb": (TSB_CONTEXT, "Form (TSB)"),
        "acwr": (ACWR_CONTEXT, "ACWR"),
        "readiness": (READINESS_CONTEXT, "Readiness"),
    }

    if metric_name not in context_map:
        raise InvalidMetricNameError(f"Unknown metric name: {metric_name}")

    context_table, display_name = context_map[metric_name]

    # Format value based on metric type
    if metric_name == "tsb":
        # Show sign for TSB
        formatted = f"{value:+.0f}"
    elif metric_name == "acwr":
        # Two decimal places for ACWR
        formatted = f"{value:.2f}"
    elif metric_name == "readiness":
        # Show as score out of 100
        formatted = f"{value:.0f}/100"
    else:
        # Default: round to integer
        formatted = f"{value:.0f}"

    # Find interpretation from context table
    interpretation = ""
    zone = ""
    if context_table:
        for low, high, desc, z in context_table:
            if low <= value < high:
                interpretation = desc
                zone = z
                break

    # Calculate trend if previous value provided
    trend = None
    if previous_value is not None:
        delta = value - previous_value
        if abs(delta) >= 1:
            direction = "+" if delta > 0 else ""
            trend = f"{direction}{delta:.0f} from last week"

    # Educational explanations
    explanations = {
        "ctl": "Long-term fitness level based on 42-day training load average",
        "atl": "Short-term fatigue based on 7-day training load average",
        "tsb": "Balance between fitness and fatigue - higher means fresher",
        "acwr": "Ratio of recent load to chronic load - monitors injury risk",
        "readiness": "Overall readiness score combining form and recent trends",
    }

    return MetricInterpretation(
        name=metric_name,
        display_name=display_name,
        value=value,
        formatted_value=formatted,
        zone=zone,
        interpretation=interpretation,
        trend=trend,
        explanation=explanations.get(metric_name),
    )


def determine_disclosure_level(days_of_data: int) -> DisclosureLevel:
    """
    Determine appropriate metric disclosure level based on data history.

    Progressive disclosure prevents overwhelming new users with complex metrics
    while providing depth to experienced users.

    Args:
        days_of_data: Days of training history available

    Returns:
        BASIC (<14 days), INTERMEDIATE (14-28), ADVANCED (28+)
    """
    if days_of_data < 14:
        return DisclosureLevel.BASIC
    elif days_of_data < 28:
        return DisclosureLevel.INTERMEDIATE
    else:
        return DisclosureLevel.ADVANCED


# ============================================================
# MAIN ENRICHMENT FUNCTIONS
# ============================================================


def enrich_metrics(
    metrics: DailyMetrics,
    repo: "RepositoryIO",
) -> EnrichedMetrics:
    """
    Add interpretive context to raw metrics.

    Args:
        metrics: Raw metrics from M9
        repo: Repository for loading historical metrics

    Returns:
        EnrichedMetrics with interpretations, zones, and trends
    """
    from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
    from sports_coach_engine.core.paths import daily_metrics_path

    # Get previous values for trends (7 days ago)
    prev_ctl = None
    prev_tsb = None

    # Try to load metrics from 7 days ago for trend calculation
    target_date = metrics.date - timedelta(days=7)
    week_ago_path = daily_metrics_path(target_date)
    week_ago_result = repo.read_yaml(week_ago_path, DailyMetrics, ReadOptions(allow_missing=True, validate=True))

    if not isinstance(week_ago_result, Exception) and week_ago_result is not None:
        prev_ctl = week_ago_result.ctl_atl.ctl
        prev_tsb = week_ago_result.ctl_atl.tsb

    # Interpret each metric
    ctl = interpret_metric("ctl", metrics.ctl_atl.ctl, prev_ctl)
    atl = interpret_metric("atl", metrics.ctl_atl.atl)
    tsb = interpret_metric("tsb", metrics.ctl_atl.tsb, prev_tsb)

    # ACWR only if sufficient data
    acwr = None
    if metrics.acwr and metrics.acwr.acwr is not None:
        acwr = interpret_metric("acwr", metrics.acwr.acwr)

    # Readiness
    readiness = interpret_metric("readiness", metrics.readiness.score)

    # Disclosure level
    days_of_data = metrics.data_days_available
    disclosure = determine_disclosure_level(days_of_data)

    # Intensity distribution (from weekly summary if available)
    # For now, use placeholder - will be properly computed when weekly summary exists
    low_pct = 0.0
    on_target = False

    # Weekly change
    ctl_change = None
    if prev_ctl is not None:
        ctl_change = ctl.value - prev_ctl

    # Load trend
    trend = None
    if ctl_change is not None:
        if ctl_change > 2:
            trend = "increasing"
        elif ctl_change < -2:
            trend = "decreasing"
        else:
            trend = "stable"

    return EnrichedMetrics(
        date=metrics.date,
        ctl=ctl,
        atl=atl,
        tsb=tsb,
        acwr=acwr,
        readiness=readiness,
        disclosure_level=disclosure,
        low_intensity_percent=low_pct,
        intensity_on_target=on_target,
        ctl_weekly_change=ctl_change,
        training_load_trend=trend,
    )


def enrich_workout(
    workout: WorkoutPrescription,
    metrics: DailyMetrics,
    profile: AthleteProfile,
    suggestions: Optional[list[Suggestion]] = None,
) -> EnrichedWorkout:
    """
    Add context and rationale to a workout prescription.

    Args:
        workout: Raw workout from M10
        metrics: Current metrics for context
        profile: Athlete profile for personalization
        suggestions: Any pending suggestions for this workout

    Returns:
        EnrichedWorkout with rationale, guidance, and context
    """
    # Display name for workout type
    workout_display = _workout_type_display(workout.workout_type)

    # Format duration
    duration_formatted = _format_duration(workout.duration_minutes)

    # Intensity description
    intensity_desc = _intensity_description(workout.intensity_zone)

    # Pace guidance (if available)
    pace_guidance = None
    if workout.pace_range_min_km:
        pace_min = _parse_pace(workout.pace_range_min_km)
        pace_max = _parse_pace(workout.pace_range_max_km)
        pace_guidance = PaceGuidance(
            target_min_per_km=pace_min,
            target_max_per_km=pace_max,
            formatted=f"{_format_pace(pace_min)}-{_format_pace(pace_max)}",
            feel_description=_pace_feel(workout.intensity_zone),
        )

    # HR guidance (if available)
    hr_guidance = None
    if workout.hr_range_low:
        hr_guidance = HRGuidance(
            target_low=workout.hr_range_low,
            target_high=workout.hr_range_high,
            formatted=f"{workout.hr_range_low}-{workout.hr_range_high} bpm",
            zone_name=intensity_desc,
        )

    # Generate rationale
    rationale = _generate_rationale(workout, metrics, profile)

    # Current readiness
    readiness = interpret_metric("readiness", metrics.readiness.score)

    # Check for suggestions
    has_suggestion = False
    suggestion_summary = None
    if suggestions:
        relevant = [s for s in suggestions if s.affected_workout.date == workout.date]
        if relevant:
            has_suggestion = True
            suggestion_summary = _suggestion_summary(relevant[0])

    return EnrichedWorkout(
        workout_id=workout.id,
        date=workout.date,
        workout_type=workout.workout_type,
        workout_type_display=workout_display,
        duration_minutes=workout.duration_minutes,
        duration_formatted=duration_formatted,
        target_rpe=workout.target_rpe,
        intensity_zone=workout.intensity_zone,
        intensity_description=intensity_desc,
        pace_guidance=pace_guidance,
        hr_guidance=hr_guidance,
        purpose=workout.purpose,
        rationale=rationale,
        current_readiness=readiness,
        has_pending_suggestion=has_suggestion,
        suggestion_summary=suggestion_summary,
        coach_notes=workout.notes,
    )


def interpret_load(
    systemic_au: float,
    lower_body_au: float,
    sport_type: str,
) -> LoadInterpretation:
    """
    Interpret load values with sport-specific context.

    Args:
        systemic_au: Systemic load in arbitrary units
        lower_body_au: Lower-body load in arbitrary units
        sport_type: Sport type for context

    Returns:
        LoadInterpretation with descriptions and assessment
    """
    # Find systemic description
    systemic_desc = "minimal"
    for low, high, desc in LOAD_CONTEXT:
        if low <= systemic_au < high:
            systemic_desc = desc
            break

    # Find lower-body description
    lb_desc = "minimal"
    for low, high, desc in LOAD_CONTEXT:
        if low <= lower_body_au < high:
            lb_desc = desc.replace("session", "impact")
            break

    # Combined assessment based on sport
    if sport_type in {"climb", "bouldering", "swimming"}:
        combined = f"Good {systemic_desc} with minimal leg stress"
    elif sport_type in {"cycling"}:
        combined = f"{systemic_desc.title()} with low running-specific stress"
    elif sport_type in {"run", "trail_run"}:
        combined = f"{systemic_desc.title()} running session"
    else:
        combined = f"{systemic_desc.title()}"

    return LoadInterpretation(
        systemic_load_au=systemic_au,
        lower_body_load_au=lower_body_au,
        systemic_description=systemic_desc,
        lower_body_description=lb_desc,
        combined_assessment=combined,
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _workout_type_display(workout_type: str) -> str:
    """Convert workout type to display name."""
    return {
        "easy": "Easy Run",
        "long_run": "Long Run",
        "tempo": "Tempo Run",
        "intervals": "Interval Session",
        "fartlek": "Fartlek",
        "rest": "Rest Day",
        "strides": "Easy + Strides",
        "recovery": "Recovery Run",
    }.get(workout_type, workout_type.replace("_", " ").title())


def _intensity_description(zone: str) -> str:
    """Get intensity zone description."""
    return {
        "zone_1": "Recovery",
        "zone_2": "Easy aerobic",
        "zone_3": "Moderate aerobic",
        "zone_4": "Threshold",
        "zone_5": "VO2max",
    }.get(zone, zone)


def _pace_feel(zone: str) -> str:
    """Get feel description for pace."""
    return {
        "zone_1": "very easy, conversational",
        "zone_2": "easy, can hold conversation",
        "zone_3": "moderate, sentences only",
        "zone_4": "comfortably hard",
        "zone_5": "hard, short phrases",
    }.get(zone, "moderate")


def _format_duration(minutes: int) -> str:
    """Format duration human-readably."""
    if minutes < 60:
        return f"{minutes} minutes"
    elif minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours >= 2 else ''}"
    else:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}min"


def _parse_pace(pace_str: str) -> float:
    """Parse pace string like '5:15' to float 5.25."""
    if ":" in pace_str:
        parts = pace_str.split(":")
        minutes = int(parts[0])
        seconds = int(parts[1])
        return minutes + (seconds / 60.0)
    else:
        return float(pace_str)


def _format_pace(min_per_km: float) -> str:
    """Format pace as mm:ss/km."""
    minutes = int(min_per_km)
    seconds = int((min_per_km - minutes) * 60)
    return f"{minutes}:{seconds:02d}/km"


def _suggestion_summary(suggestion: Suggestion) -> str:
    """Create brief summary of a suggestion."""
    summaries = {
        "downgrade": f"Consider reducing intensity on {suggestion.affected_workout.date}",
        "skip": f"Consider skipping {suggestion.affected_workout.date} workout",
        "move": f"Consider moving {suggestion.affected_workout.date} workout",
        "shorten": f"Consider shortening {suggestion.affected_workout.date} workout",
        "force_rest": "Rest day recommended",
    }
    return summaries.get(
        suggestion.suggestion_type,
        f"Adjustment suggested for {suggestion.affected_workout.date}"
    )


def _generate_rationale(
    workout: WorkoutPrescription,
    metrics: DailyMetrics,
    profile: AthleteProfile,
) -> WorkoutRationale:
    """
    Generate context-aware rationale for a workout.

    Rationale adapts based on TSB (form), ACWR (injury risk), and workout type.
    """
    # TSB-based primary reason
    tsb = metrics.ctl_atl.tsb
    if tsb > 5:
        primary = "You're feeling fresh"
    elif tsb > -10:
        primary = "Form is good"
    elif tsb > -20:
        primary = "Training load is building nicely"
    else:
        primary = "You've been working hard"

    # Workout-specific purpose
    purposes = {
        "easy": "recovery and aerobic base maintenance",
        "long_run": "endurance building and fat oxidation",
        "tempo": "lactate threshold improvement",
        "intervals": "VO2max development",
        "fartlek": "neuromuscular coordination and fun",
        "rest": "recovery and adaptation",
    }
    training_purpose = purposes.get(workout.workout_type, "general fitness")

    # Phase context (if available)
    phase_context = None
    if workout.phase:
        phases = {
            "base": "Building your aerobic foundation",
            "build": "Increasing intensity progressively",
            "peak": "Race-specific sharpening",
            "taper": "Reducing volume while staying sharp",
        }
        phase_context = phases.get(workout.phase)

    # Safety notes
    safety_notes = []
    if metrics.acwr and metrics.acwr.acwr and metrics.acwr.acwr > 1.3:
        safety_notes.append("ACWR approaching caution zone - listen to your body")
    if metrics.readiness.score < 50:
        safety_notes.append("Readiness is lower than usual - adjust if needed")

    return WorkoutRationale(
        primary_reason=primary,
        training_purpose=training_purpose,
        phase_context=phase_context,
        safety_notes=safety_notes,
    )
