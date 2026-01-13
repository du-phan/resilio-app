# M12 — Data Enrichment

## 1. Metadata

| Field        | Value                                                                                   |
| ------------ | --------------------------------------------------------------------------------------- |
| Module ID    | M12                                                                                     |
| Name         | Data Enrichment                                                                         |
| Code Module  | `core/enrichment.py`                                                                    |
| Version      | 2.0.0                                                                                   |
| Status       | Draft                                                                                   |
| Dependencies | M3 (Repository I/O), M9 (Metrics Engine), M10 (Plan Generator), M11 (Adaptation Engine) |

### Changelog

- **2.0.0** (2026-01-12): Complete rewrite as Data Enrichment module. Removed prose generation (now handled by Claude Code). Module returns structured data with interpretive context. Renamed from "Coach Response Formatter" to "Data Enrichment".
- **1.0.1** (2026-01-12): Added complete algorithms for formatter functions.
- **1.0.0** (initial): Initial draft with response formatting algorithms.

## 2. Purpose

Add interpretive context to raw training data. Transform numbers into meaningful insights that Claude Code can use to craft natural, conversational responses.

**Architectural Role:** This module is called by the API layer to enrich workflow results before returning them to Claude Code. It does NOT generate prose—Claude Code handles all response formatting.

### 2.1 What This Module Does

- Add human-readable interpretations to metric values (CTL=44 → "solid recreational level")
- Provide training zone classifications ("safe", "productive", "high_risk")
- Calculate trends and deltas with context
- Enrich workout prescriptions with pace/HR guidance and readiness context
- Return structured data models with interpretive fields (Claude Code crafts coaching messages)

### 2.2 What This Module Does NOT Do

- **Generate prose responses**: Claude Code formats conversational responses
- **Format text for display**: No markdown generation, no templates
- **Make decisions**: M11 handles adaptation logic
- **Compute metrics**: M9 handles metric calculation

### 2.3 Scope Boundaries

**In Scope:**

- Metric contextualization (what does CTL=44 mean?)
- Zone classification (is ACWR 1.4 safe?)
- Trend interpretation (is +5 CTL good?)
- Workout enrichment (pace zones, HR zones, readiness context)
- Progressive disclosure level determination

**Out of Scope:**

- Prose generation (Claude Code)
- Response formatting (Claude Code)
- Metric computation (M9)
- Adaptation decisions (M11)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage                                  |
| ------ | -------------------------------------- |
| M3     | Read data files for historical context |
| M9     | Get metric values for enrichment       |
| M10    | Get plan context for workout rationale |
| M11    | Get suggestion context                 |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Internal Interface

**Note:** These functions are called by the API layer to enrich workflow results. Claude Code receives enriched data models.

### 4.1 Type Definitions

```python
from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MetricZone(str, Enum):
    """Classification zones for training metrics."""
    # CTL zones
    BEGINNER = "beginner"
    DEVELOPING = "developing"
    RECREATIONAL = "recreational"
    TRAINED = "trained"
    COMPETITIVE = "competitive"
    ELITE = "elite"

    # TSB zones
    OVERREACHED = "overreached"
    PRODUCTIVE = "productive"
    OPTIMAL = "optimal"
    FRESH = "fresh"
    PEAKED = "peaked"

    # ACWR zones
    UNDERTRAINED = "undertrained"
    SAFE = "safe"
    CAUTION = "caution"
    HIGH_RISK = "high_risk"

    # Readiness zones
    REST_RECOMMENDED = "rest_recommended"
    EASY_ONLY = "easy_only"
    READY = "ready"
    PRIMED = "primed"


class DisclosureLevel(str, Enum):
    """Progressive disclosure level for metrics."""
    BASIC = "basic"           # Volume, easy/hard distribution
    INTERMEDIATE = "intermediate"  # CTL/ATL/TSB
    ADVANCED = "advanced"     # ACWR, detailed readiness


class MetricInterpretation(BaseModel):
    """A metric value with interpretive context."""
    name: str                    # "ctl", "tsb", "acwr", etc.
    display_name: str            # "Fitness (CTL)", "Form (TSB)"
    value: float                 # Raw numeric value
    formatted_value: str         # "44", "+8", "1.15"
    zone: MetricZone             # Classification zone
    interpretation: str          # "solid recreational level"
    trend: Optional[str] = None  # "+2 this week" or None
    explanation: Optional[str] = None  # Educational text for the metric


class EnrichedMetrics(BaseModel):
    """Complete metrics snapshot with interpretations."""
    date: date
    ctl: MetricInterpretation
    atl: MetricInterpretation
    tsb: MetricInterpretation
    acwr: Optional[MetricInterpretation] = None  # Requires 28+ days
    readiness: MetricInterpretation
    disclosure_level: DisclosureLevel  # What level of detail to show

    # Intensity distribution (always included)
    low_intensity_percent: float       # Percent in zone 1-2
    intensity_on_target: bool          # Meeting 80/20 guideline?

    # Week-over-week changes
    ctl_weekly_change: Optional[float] = None
    training_load_trend: Optional[str] = None  # "increasing", "stable", "decreasing"


class WorkoutRationale(BaseModel):
    """Explanation for why a workout is prescribed."""
    primary_reason: str          # "Form is good"
    training_purpose: str        # "threshold work improves lactate clearance"
    phase_context: Optional[str] = None  # "Building aerobic foundation"
    safety_notes: list[str] = Field(default_factory=list)  # Any warnings


class PaceGuidance(BaseModel):
    """Pace guidance with context."""
    target_min_per_km: float     # 5.25
    target_max_per_km: float     # 5.42
    formatted: str               # "5:15-5:25/km"
    feel_description: str        # "comfortably hard"


class HRGuidance(BaseModel):
    """Heart rate guidance with context."""
    target_low: int              # 160
    target_high: int             # 170
    formatted: str               # "160-170 bpm"
    zone_name: str               # "Threshold"


class EnrichedWorkout(BaseModel):
    """Workout prescription with full context."""
    # Core workout data
    workout_id: str
    date: date
    workout_type: str            # "tempo", "easy", "long_run"
    workout_type_display: str    # "Tempo Run"
    duration_minutes: int
    duration_formatted: str      # "45 minutes"

    # Intensity
    target_rpe: int
    intensity_zone: str          # "zone_4"
    intensity_description: str   # "Threshold"

    # Guidance
    pace_guidance: Optional[PaceGuidance] = None
    hr_guidance: Optional[HRGuidance] = None
    purpose: str                 # "Build lactate threshold"

    # Context
    rationale: WorkoutRationale
    current_readiness: MetricInterpretation

    # Adaptations
    has_pending_suggestion: bool = False
    suggestion_summary: Optional[str] = None  # "Consider reducing intensity"

    # Notes
    coach_notes: Optional[str] = None


class SyncSummary(BaseModel):
    """Enriched summary of a sync operation."""
    activities_imported: int
    activities_skipped: int
    activities_failed: int

    # What was imported (brief)
    activity_types: list[str]    # ["Running", "Cycling", "Bouldering"]
    total_duration_minutes: int
    total_load_au: float

    # Metric changes
    metrics_before: Optional[EnrichedMetrics] = None
    metrics_after: EnrichedMetrics
    metric_changes: list[str]    # ["CTL +2", "TSB -5"]

    # Suggestions
    suggestions_generated: int
    suggestion_summaries: list[str]  # ["Consider rest day tomorrow"]

    # Errors
    has_errors: bool
    error_summaries: list[str]


class EnrichedSuggestion(BaseModel):
    """Adaptation suggestion with full context."""
    suggestion_id: str
    suggestion_type: str         # "downgrade", "skip", "move"
    suggestion_type_display: str # "Reduce intensity"

    # What's affected
    affected_date: date
    affected_workout_type: str   # "intervals"
    affected_workout_display: str # "Interval Session"

    # The change
    original_description: str    # "Intervals @ RPE 8"
    proposed_description: str    # "Easy run @ RPE 4"

    # Why
    rationale: str               # "ACWR is 1.4, approaching caution zone"
    safety_level: str            # "recommended", "suggested", "optional"
    override_risk: str           # "low", "medium", "high"


class LoadInterpretation(BaseModel):
    """Load value with context."""
    systemic_load_au: float
    lower_body_load_au: float
    systemic_description: str    # "moderate session"
    lower_body_description: str  # "light impact"
    combined_assessment: str     # "Good recovery day with upper body work"
```

### 4.2 Function Signatures

```python
def enrich_metrics(
    metrics: "DailyMetrics",
    historical: Optional[list["DailyMetrics"]] = None,
) -> EnrichedMetrics:
    """
    Add interpretive context to raw metrics.

    Args:
        metrics: Raw metrics from M9
        historical: Optional historical metrics for trend calculation

    Returns:
        EnrichedMetrics with interpretations and trends
    """
    ...


def enrich_workout(
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    profile: "AthleteProfile",
    suggestions: Optional[list["Suggestion"]] = None,
) -> EnrichedWorkout:
    """
    Add context and rationale to a workout prescription.

    Args:
        workout: Raw workout from M10
        metrics: Current metrics for context
        profile: Athlete profile for personalization
        suggestions: Any pending suggestions for this workout

    Returns:
        EnrichedWorkout with rationale and guidance
    """
    ...


def enrich_sync_result(
    sync_result: "SyncWorkflowResult",
) -> SyncSummary:
    """
    Summarize a sync operation with interpretations.

    Args:
        sync_result: Raw sync result from M1 workflow

    Returns:
        SyncSummary with metric changes and suggestions
    """
    ...


def enrich_suggestions(
    suggestions: list["Suggestion"],
) -> list[EnrichedSuggestion]:
    """
    Add context to adaptation suggestions.

    Args:
        suggestions: Raw suggestions from M11

    Returns:
        List of EnrichedSuggestion with display text
    """
    ...


def interpret_metric(
    metric_name: str,
    value: float,
    previous_value: Optional[float] = None,
) -> MetricInterpretation:
    """
    Create interpretation for a single metric value.

    Args:
        metric_name: "ctl", "tsb", "acwr", etc.
        value: Current value
        previous_value: Previous value for trend

    Returns:
        MetricInterpretation with zone and interpretation
    """
    ...


def interpret_load(
    systemic_au: float,
    lower_body_au: float,
    sport_type: str,
) -> LoadInterpretation:
    """
    Interpret load values with sport context.

    Args:
        systemic_au: Systemic load in arbitrary units
        lower_body_au: Lower-body load in arbitrary units
        sport_type: Sport type for context

    Returns:
        LoadInterpretation with descriptions
    """
    ...


def determine_disclosure_level(
    days_of_data: int,
) -> DisclosureLevel:
    """
    Determine appropriate metric disclosure level.

    Args:
        days_of_data: Days of training history

    Returns:
        BASIC (<14 days), INTERMEDIATE (14-28), ADVANCED (28+)
    """
    ...
```

## 5. Core Algorithms

### 5.1 Metric Context Tables

```python
# CTL (Chronic Training Load) interpretation
CTL_CONTEXT: list[tuple[float, float, str, MetricZone]] = [
    (0, 20, "building base fitness", MetricZone.BEGINNER),
    (20, 40, "developing fitness", MetricZone.DEVELOPING),
    (40, 60, "solid recreational level", MetricZone.RECREATIONAL),
    (60, 80, "well-trained", MetricZone.TRAINED),
    (80, 100, "competitive amateur", MetricZone.COMPETITIVE),
    (100, 200, "elite amateur", MetricZone.ELITE),
]

# TSB (Training Stress Balance) interpretation
TSB_CONTEXT: list[tuple[float, float, str, MetricZone]] = [
    (-100, -25, "overreached - recovery needed", MetricZone.OVERREACHED),
    (-25, -10, "productive training zone", MetricZone.PRODUCTIVE),
    (-10, 5, "optimal for quality work", MetricZone.OPTIMAL),
    (5, 15, "fresh - good for racing", MetricZone.FRESH),
    (15, 100, "peaked - may be detraining", MetricZone.PEAKED),
]

# ACWR (Acute:Chronic Workload Ratio) interpretation
ACWR_CONTEXT: list[tuple[float, float, str, MetricZone]] = [
    (0, 0.8, "undertrained - fitness declining", MetricZone.UNDERTRAINED),
    (0.8, 1.3, "safe training zone", MetricZone.SAFE),
    (1.3, 1.5, "caution - monitor closely", MetricZone.CAUTION),
    (1.5, 3.0, "high injury risk", MetricZone.HIGH_RISK),
]

# Readiness interpretation
READINESS_CONTEXT: list[tuple[float, float, str, MetricZone]] = [
    (0, 35, "rest recommended", MetricZone.REST_RECOMMENDED),
    (35, 50, "easy activity only", MetricZone.EASY_ONLY),
    (50, 70, "ready for normal training", MetricZone.READY),
    (70, 100, "primed for quality work", MetricZone.PRIMED),
]

# Load descriptions
LOAD_CONTEXT: list[tuple[float, float, str]] = [
    (0, 100, "light recovery session"),
    (100, 300, "moderate session"),
    (300, 500, "solid workout"),
    (500, 700, "hard session"),
    (700, 2000, "very demanding session"),
]
```

### 5.2 Metric Interpretation

```python
def interpret_metric(
    metric_name: str,
    value: float,
    previous_value: Optional[float] = None,
) -> MetricInterpretation:
    """Create interpretation for a single metric value."""

    context_tables = {
        "ctl": (CTL_CONTEXT, "Fitness (CTL)"),
        "atl": (None, "Fatigue (ATL)"),  # ATL doesn't have zones
        "tsb": (TSB_CONTEXT, "Form (TSB)"),
        "acwr": (ACWR_CONTEXT, "ACWR"),
        "readiness": (READINESS_CONTEXT, "Readiness"),
    }

    table, display_name = context_tables.get(metric_name, (None, metric_name))

    # Format value based on metric type
    if metric_name == "tsb":
        formatted = f"{value:+.0f}"  # Show sign
    elif metric_name == "acwr":
        formatted = f"{value:.2f}"
    elif metric_name == "readiness":
        formatted = f"{value:.0f}/100"
    else:
        formatted = f"{value:.0f}"

    # Find interpretation from context table
    interpretation = ""
    zone = MetricZone.SAFE  # Default
    if table:
        for low, high, desc, z in table:
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

    # Educational explanation (optional)
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
```

### 5.3 Metrics Enrichment

```python
def enrich_metrics(
    metrics: "DailyMetrics",
    historical: Optional[list["DailyMetrics"]] = None,
) -> EnrichedMetrics:
    """Add interpretive context to raw metrics."""

    # Get previous values for trends
    prev_ctl = None
    prev_tsb = None
    if historical and len(historical) > 0:
        # Find metrics from ~7 days ago
        week_ago = [m for m in historical if m.date == metrics.date - timedelta(days=7)]
        if week_ago:
            prev_ctl = week_ago[0].ctl_atl.ctl
            prev_tsb = week_ago[0].ctl_atl.tsb

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
    days_of_data = metrics.acwr.days_of_data if metrics.acwr else 0
    disclosure = determine_disclosure_level(days_of_data)

    # Intensity distribution
    intensity = metrics.intensity_distribution
    low_pct = intensity.low_intensity_percent_7d
    on_target = low_pct >= 80

    # Weekly change
    ctl_change = ctl.value - prev_ctl if prev_ctl else None

    # Load trend
    trend = None
    if ctl_change:
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
```

### 5.4 Workout Enrichment

```python
def enrich_workout(
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    profile: "AthleteProfile",
    suggestions: Optional[list["Suggestion"]] = None,
) -> EnrichedWorkout:
    """Add context and rationale to a workout prescription."""

    # Display name for workout type
    workout_display = _workout_type_display(workout.workout_type)

    # Format duration
    duration_formatted = _format_duration(workout.duration_minutes)

    # Intensity description
    intensity_desc = _intensity_description(workout.intensity_zone)

    # Pace guidance
    pace_guidance = None
    if workout.pace_range_min_km:
        pace_guidance = PaceGuidance(
            target_min_per_km=workout.pace_range_min_km,
            target_max_per_km=workout.pace_range_max_km,
            formatted=f"{_format_pace(workout.pace_range_min_km)}-{_format_pace(workout.pace_range_max_km)}",
            feel_description=_pace_feel(workout.intensity_zone),
        )

    # HR guidance
    hr_guidance = None
    if workout.hr_range_low:
        hr_guidance = HRGuidance(
            target_low=workout.hr_range_low,
            target_high=workout.hr_range_high,
            formatted=f"{workout.hr_range_low}-{workout.hr_range_high} bpm",
            zone_name=intensity_desc,
        )

    # Current readiness (interpret metric only)
    readiness = interpret_metric("readiness", metrics.readiness.score)

    # Check for suggestions (no summary generation - Claude Code crafts message)
    has_suggestion = False
    if suggestions:
        relevant = [s for s in suggestions if s.affected_workout.date == workout.date]
        if relevant:
            has_suggestion = True

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
        current_readiness=readiness,
        has_pending_suggestion=has_suggestion,
        coach_notes=workout.notes,
        # Note: rationale removed - Claude Code generates coaching messages
        # Note: suggestion_summary removed - Claude Code explains with context
    )


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
```

### 5.5 Sync Result Enrichment

```python
def enrich_sync_result(
    sync_result: "SyncWorkflowResult",
) -> SyncSummary:
    """Summarize a sync operation with interpretations."""

    # Collect activity types
    activity_types = list(set(
        a.activity.sport_type.title()
        for a in sync_result.processed_activities
    ))

    # Total duration and load
    total_duration = sum(
        a.activity.duration_minutes
        for a in sync_result.processed_activities
    )
    total_load = sum(
        a.loads.systemic_load_au
        for a in sync_result.processed_activities
    )

    # Enrich metrics
    metrics_before = None
    if sync_result.metrics_before:
        metrics_before = enrich_metrics(sync_result.metrics_before)

    metrics_after = enrich_metrics(sync_result.metrics_after)

    # Calculate metric changes
    changes = []
    if metrics_before:
        ctl_delta = metrics_after.ctl.value - metrics_before.ctl.value
        if abs(ctl_delta) >= 1:
            sign = "+" if ctl_delta > 0 else ""
            changes.append(f"CTL {sign}{ctl_delta:.0f}")

        tsb_delta = metrics_after.tsb.value - metrics_before.tsb.value
        if abs(tsb_delta) >= 1:
            sign = "+" if tsb_delta > 0 else ""
            changes.append(f"TSB {sign}{tsb_delta:.0f}")

    # Summarize suggestions
    suggestion_summaries = [
        _suggestion_summary(s) for s in sync_result.suggestions
    ]

    # Error summaries
    error_summaries = [e.message for e in sync_result.errors]

    return SyncSummary(
        activities_imported=sync_result.activities_imported,
        activities_skipped=sync_result.activities_skipped,
        activities_failed=sync_result.activities_failed,
        activity_types=activity_types,
        total_duration_minutes=total_duration,
        total_load_au=total_load,
        metrics_before=metrics_before,
        metrics_after=metrics_after,
        metric_changes=changes,
        suggestions_generated=len(sync_result.suggestions),
        suggestion_summaries=suggestion_summaries,
        has_errors=len(sync_result.errors) > 0,
        error_summaries=error_summaries,
    )
```

### 5.6 Helper Functions

```python
def determine_disclosure_level(days_of_data: int) -> DisclosureLevel:
    """Determine appropriate metric disclosure level."""
    if days_of_data < 14:
        return DisclosureLevel.BASIC
    elif days_of_data < 28:
        return DisclosureLevel.INTERMEDIATE
    else:
        return DisclosureLevel.ADVANCED


def interpret_load(
    systemic_au: float,
    lower_body_au: float,
    sport_type: str,
) -> LoadInterpretation:
    """Interpret load values with sport context."""

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


def _format_duration(minutes: int) -> str:
    """Format duration human-readably."""
    if minutes < 60:
        return f"{minutes} minutes"
    elif minutes % 60 == 0:
        return f"{minutes // 60} hour{'s' if minutes >= 120 else ''}"
    else:
        return f"{minutes // 60}h {minutes % 60}min"


def _format_pace(min_per_km: float) -> str:
    """Format pace as mm:ss/km."""
    minutes = int(min_per_km)
    seconds = int((min_per_km - minutes) * 60)
    return f"{minutes}:{seconds:02d}/km"


```

## 6. Integration with API Layer

This module is called by the API layer to enrich workflow results before returning to Claude Code.

### 6.1 API to Enrichment Mapping

| API Function                         | Enrichment Function    |
| ------------------------------------ | ---------------------- |
| `api.metrics.get_current_metrics()`  | `enrich_metrics()`     |
| `api.coach.get_todays_workout()`     | `enrich_workout()`     |
| `api.sync.sync_strava()`             | `enrich_sync_result()` |
| `api.plan.get_pending_suggestions()` | `enrich_suggestions()` |

### 6.2 Data Flow

```
M1 Workflow returns: DailyMetrics (raw numbers)
          │
          ▼
API Layer calls: enrich_metrics(raw_metrics)
          │
          ▼
M12 returns: EnrichedMetrics (numbers + interpretations)
          │
          ▼
API Layer returns to Claude Code: EnrichedMetrics
          │
          ▼
Claude Code crafts: Natural conversational response
```

### 6.3 Example API Layer Usage

```python
# In api/metrics.py
from sports_coach_engine.core.enrichment import enrich_metrics
from sports_coach_engine.core.workflows import run_metrics_refresh


def get_current_metrics() -> EnrichedMetrics:
    """
    Public API function called by Claude Code.
    Returns enriched metrics with interpretations.
    """
    repo = get_repository()

    # Call M1 workflow for raw metrics
    result = run_metrics_refresh(repo)

    if not result.success:
        raise MetricsError(result.errors)

    # M12: Enrich with interpretations
    historical = load_historical_metrics(repo, days=14)
    enriched = enrich_metrics(result.metrics, historical)

    return enriched
```

## 7. Test Scenarios

### 7.1 Metric Interpretation Tests

```python
def test_ctl_interpretation():
    """CTL values get appropriate zones."""
    interp = interpret_metric("ctl", 45)

    assert interp.zone == MetricZone.RECREATIONAL
    assert "recreational" in interp.interpretation.lower()
    assert interp.formatted_value == "45"


def test_tsb_shows_sign():
    """TSB formatted value includes sign."""
    positive = interpret_metric("tsb", 8)
    assert positive.formatted_value == "+8"

    negative = interpret_metric("tsb", -15)
    assert negative.formatted_value == "-15"


def test_acwr_zones():
    """ACWR correctly identifies risk zones."""
    safe = interpret_metric("acwr", 1.1)
    assert safe.zone == MetricZone.SAFE

    caution = interpret_metric("acwr", 1.4)
    assert caution.zone == MetricZone.CAUTION

    risk = interpret_metric("acwr", 1.6)
    assert risk.zone == MetricZone.HIGH_RISK


def test_trend_calculation():
    """Trends calculated from previous values."""
    interp = interpret_metric("ctl", 45, previous_value=40)

    assert interp.trend is not None
    assert "+5" in interp.trend
```

### 7.2 Workout Enrichment Tests

```python
def test_workout_rationale_includes_tsb_context():
    """Workout rationale reflects current form."""
    workout = mock_workout(workout_type="tempo")
    metrics = mock_metrics(tsb=8)
    profile = mock_profile()

    enriched = enrich_workout(workout, metrics, profile)

    assert "fresh" in enriched.rationale.primary_reason.lower()


def test_pace_guidance_formatting():
    """Pace guidance properly formatted."""
    workout = mock_workout(pace_range_min_km=5.25, pace_range_max_km=5.42)
    metrics = mock_metrics()
    profile = mock_profile()

    enriched = enrich_workout(workout, metrics, profile)

    assert enriched.pace_guidance is not None
    assert "5:15" in enriched.pace_guidance.formatted
    assert "5:25" in enriched.pace_guidance.formatted


def test_suggestion_included_when_present():
    """Pending suggestions noted in enriched workout."""
    workout = mock_workout()
    metrics = mock_metrics()
    profile = mock_profile()
    suggestions = [mock_suggestion(affected_date=workout.date)]

    enriched = enrich_workout(workout, metrics, profile, suggestions)

    assert enriched.has_pending_suggestion
    assert enriched.suggestion_summary is not None
```

### 7.3 Disclosure Level Tests

```python
def test_disclosure_basic():
    """New users get basic disclosure."""
    level = determine_disclosure_level(7)
    assert level == DisclosureLevel.BASIC


def test_disclosure_intermediate():
    """2-4 week users get intermediate."""
    level = determine_disclosure_level(21)
    assert level == DisclosureLevel.INTERMEDIATE


def test_disclosure_advanced():
    """Established users get full metrics."""
    level = determine_disclosure_level(45)
    assert level == DisclosureLevel.ADVANCED
```

## 8. Configuration

### 8.1 Enrichment Settings

```python
ENRICHMENT_CONFIG = {
    "disclosure_thresholds": {
        "basic": 0,
        "intermediate": 14,
        "advanced": 28,
    },
    "include_explanations": True,  # Educational text for metrics
    "trend_lookback_days": 7,      # Days for trend calculation
}
```

## 9. Design Principles

### 9.1 Data, Not Prose

This module returns **structured data**, not formatted strings. Claude Code decides how to present information conversationally.

**Correct pattern:**

```python
return MetricInterpretation(
    value=44,
    interpretation="solid recreational level",
    zone=MetricZone.RECREATIONAL,
)
```

**Incorrect pattern (removed):**

```python
return "Your CTL is 44, which is a solid recreational level."
```

### 9.2 Rich Type Annotations

All return types are Pydantic models with comprehensive fields. This lets Claude Code access any detail it needs for response crafting.

### 9.3 Context Tables

Interpretations come from data-driven context tables, not hardcoded conditionals. This makes it easy to adjust thresholds and add new interpretations.

### 9.4 Separation of Concerns

- **M9** computes raw metrics
- **M12** adds interpretations
- **Claude Code** crafts responses

Each layer has a clear responsibility.
