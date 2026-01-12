# M12 — Coach Response Formatter

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M12 |
| Name | Coach Response Formatter |
| Version | 1.0.1 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M9 (Metrics Engine), M10 (Plan Generator), M11 (Adaptation Engine) |

### Changelog
- **1.0.1** (2026-01-12): Converted all dataclass types to BaseModel for consistency. Added complete algorithms for `format_metrics_explanation()`, `format_plan_overview()`, `format_error()`, and `format_load()` to remove `...` placeholders and make spec LLM-implementable.
- **1.0.0** (initial): Initial draft with comprehensive response formatting algorithms

## 2. Purpose

Render structured training data into human-readable, conversational coach responses. Translates metrics, plans, and suggestions into actionable guidance that explains the "why" behind every recommendation.

### 2.1 Scope Boundaries

**In Scope:**
- Formatting workout prescriptions
- Rendering weekly status displays
- Presenting metrics with context
- Displaying adaptation suggestions
- Sync result summaries
- Progressive metric disclosure (educate over time)
- Multi-sport activity display

**Out of Scope:**
- Computing metrics (M9)
- Generating plans (M10)
- Making adaptation decisions (M11)
- Parsing user intent (M1)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Read plan, workout, and metric files |
| M9 | Get metric values and trends |
| M10 | Get plan structure and workouts |
| M11 | Get pending suggestions |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
```

## 4. Public Interface

### 4.1 Type Definitions

```python
from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    """Types of coach responses"""
    WORKOUT_TODAY = "workout_today"
    WEEKLY_STATUS = "weekly_status"
    SYNC_SUMMARY = "sync_summary"
    SUGGESTION_PROMPT = "suggestion_prompt"
    METRICS_EXPLANATION = "metrics_explanation"
    PLAN_OVERVIEW = "plan_overview"
    ERROR_MESSAGE = "error_message"


class MetricLevel(str, Enum):
    """Progressive disclosure level for metrics"""
    BASIC = "basic"           # Volume, easy/hard distribution
    INTERMEDIATE = "intermediate"  # CTL/ATL/TSB
    ADVANCED = "advanced"     # ACWR, detailed readiness


class FormattedResponse(BaseModel):
    """Complete formatted response"""
    response_type: ResponseType
    content: str              # Main formatted text
    metrics_shown: list[str]  # Which metrics were included
    suggestions_count: int    # Pending suggestions mentioned
    follow_up_questions: list[str]  # Optional clarifying questions


class WorkoutDisplay(BaseModel):
    """Formatted workout for display"""
    date_str: str            # "Tuesday March 18th"
    workout_type: str        # "Tempo Run"
    duration_str: str        # "45 minutes"
    intensity_str: str       # "Zone 4 (threshold)"
    pace_guidance: Optional[str] = None  # "5:15-5:25/km"
    hr_guidance: Optional[str] = None    # "160-170 bpm"
    purpose: str             # "Build lactate threshold"
    notes: Optional[str] = None
    status_icon: str         # "→", "✓", "⏭"


class MetricDisplay(BaseModel):
    """Formatted metric with context"""
    name: str                # "Fitness (CTL)"
    value: str               # "44"
    context: str             # "solid recreational level"
    trend: Optional[str] = None     # "+2 this week"
    zone: Optional[str] = None      # "productive training zone"
```

### 4.2 Function Signatures

```python
def format_workout_today(
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    suggestions: list["Suggestion"],
    profile: "AthleteProfile",
) -> FormattedResponse:
    """
    Format today's workout with context and rationale.

    Includes:
    - Workout prescription
    - Why this workout today
    - Current readiness/metrics
    - Any pending suggestions
    """
    ...


def format_weekly_status(
    week_plan: "WeekPlan",
    activities: list["NormalizedActivity"],
    metrics: "DailyMetrics",
    profile: "AthleteProfile",
) -> FormattedResponse:
    """
    Format weekly status display.

    Shows all activities (not just running) with load breakdown.
    """
    ...


def format_sync_summary(
    sync_result: "SyncResult",
    new_activities: list["NormalizedActivity"],
    metrics_delta: dict,
    suggestions: list["Suggestion"],
) -> FormattedResponse:
    """
    Format Strava sync results summary.
    """
    ...


def format_suggestions(
    suggestions: list["Suggestion"],
    profile: "AthleteProfile",
) -> FormattedResponse:
    """
    Format pending adaptation suggestions for user decision.
    """
    ...


def format_metrics_explanation(
    metrics: "DailyMetrics",
    disclosure_level: MetricLevel,
) -> FormattedResponse:
    """
    Format metrics with educational context.

    Adjusts detail based on how long user has been training.

    Process:
        1. Determine which metrics to show based on disclosure_level
        2. For each metric, add educational explanation
        3. Format with context and trends
        4. Return formatted response

    Args:
        metrics: Current metrics to display
        disclosure_level: BASIC, INTERMEDIATE, or ADVANCED

    Returns:
        Formatted educational metrics display
    """
    lines = []
    lines.append("## Your Training Metrics")
    lines.append("")

    metrics_shown = []

    # Basic level: Volume and simple concepts
    if disclosure_level >= MetricLevel.BASIC:
        # Fitness (CTL)
        ctl = metrics.ctl_atl.ctl
        ctl_context, _ = contextualize_metric("ctl", ctl)
        lines.append(f"**Fitness (CTL):** {ctl:.0f}")
        lines.append(f"↳ {ctl_context.capitalize()}")
        lines.append("  (Chronic Training Load - your long-term fitness level)")
        lines.append("")
        metrics_shown.append("ctl")

    # Intermediate: Add form/freshness
    if disclosure_level >= MetricLevel.INTERMEDIATE:
        # Form (TSB)
        tsb = metrics.ctl_atl.tsb
        tsb_context, _ = contextualize_metric("tsb", tsb)
        lines.append(f"**Form (TSB):** {tsb:+.0f}")
        lines.append(f"↳ {tsb_context.capitalize()}")
        lines.append("  (Training Stress Balance - fitness minus fatigue)")
        lines.append("")
        metrics_shown.append("tsb")

        # Fatigue (ATL)
        atl = metrics.ctl_atl.atl
        lines.append(f"**Fatigue (ATL):** {atl:.0f}")
        lines.append("  (Acute Training Load - recent 7-day fatigue)")
        lines.append("")
        metrics_shown.append("atl")

    # Advanced: Add ACWR and detailed readiness
    if disclosure_level >= MetricLevel.ADVANCED:
        if metrics.acwr and metrics.acwr.acwr is not None:
            acwr = metrics.acwr.acwr
            acwr_context, _ = contextualize_metric("acwr", acwr)
            lines.append(f"**ACWR:** {acwr:.2f}")
            lines.append(f"↳ {acwr_context.capitalize()}")
            lines.append("  (Acute:Chronic Workload Ratio - injury risk indicator)")
            lines.append("")
            metrics_shown.append("acwr")

        # Readiness breakdown
        if metrics.readiness:
            lines.append(f"**Readiness:** {metrics.readiness.score}/100")
            lines.append(f"↳ {metrics.readiness.level.value.capitalize()}")
            lines.append("  Components:")
            lines.append(f"  - TSB contribution: {metrics.readiness.tsb_component:.0f}")
            lines.append(f"  - Trend: {metrics.readiness.trend_component:.0f}")
            lines.append("")
            metrics_shown.append("readiness")

    # Intensity distribution
    if disclosure_level >= MetricLevel.INTERMEDIATE:
        intensity = metrics.intensity_distribution
        lines.append("**7-Day Intensity Distribution:**")
        lines.append(f"- Low (Zone 1-2): {intensity.low_intensity_minutes_7d}min")
        lines.append(f"- Moderate (Zone 3-4): {intensity.moderate_intensity_minutes_7d}min")
        lines.append(f"- High (Zone 5): {intensity.high_intensity_minutes_7d}min")

        if intensity.low_intensity_percent_7d >= 80:
            lines.append("✓ Meeting 80/20 guideline")
        else:
            lines.append(f"  ({intensity.low_intensity_percent_7d:.0f}% low intensity - aim for 80%+)")
        lines.append("")
        metrics_shown.append("intensity_distribution")

    return FormattedResponse(
        response_type=ResponseType.METRICS_EXPLANATION,
        content="\n".join(lines),
        metrics_shown=metrics_shown,
        suggestions_count=0,
        follow_up_questions=[],
    )


def format_plan_overview(
    plan: "MasterPlan",
    current_week: int,
) -> FormattedResponse:
    """
    Format high-level plan overview.

    Process:
        1. Show goal and timeline
        2. Display phase breakdown
        3. Highlight current week
        4. Show volume progression
        5. List key milestones

    Args:
        plan: The master plan to display
        current_week: Current week number in plan

    Returns:
        Formatted plan overview
    """
    lines = []

    # Header with goal
    goal_type = plan.goal.type.value.replace("_", " ").title()
    if plan.goal.race_target_date:
        goal_date = format_date_short(plan.goal.race_target_date)
        lines.append(f"## {goal_type} Training Plan → {goal_date}")
    else:
        lines.append(f"## {goal_type} Training Plan")
    lines.append("")

    # Timeline
    start_str = format_date_short(plan.start_date)
    end_str = format_date_short(plan.end_date)
    lines.append(f"**Timeline:** {start_str} → {end_str} ({plan.total_weeks} weeks)")
    lines.append(f"**Current:** Week {current_week} of {plan.total_weeks}")
    lines.append("")

    # Phase breakdown
    lines.append("**Phases:**")
    for phase_info in plan.phases:
        phase_name = phase_info["phase"].title() if isinstance(phase_info["phase"], str) else phase_info["phase"].value.title()
        start_wk = phase_info["start_week"] + 1  # Convert 0-indexed to 1-indexed
        end_wk = phase_info["end_week"] + 1
        focus = phase_info.get("focus", "")

        marker = " ← Current" if start_wk <= current_week <= end_wk else ""
        lines.append(f"- {phase_name} (weeks {start_wk}-{end_wk}): {focus}{marker}")
    lines.append("")

    # Volume progression
    current_vol = plan.weeks[current_week - 1].target_volume_km if current_week <= len(plan.weeks) else 0
    lines.append("**Volume Progression:**")
    lines.append(f"- Starting: {plan.starting_volume_km:.0f}km/week")
    lines.append(f"- Current: {current_vol:.0f}km/week")
    lines.append(f"- Peak: {plan.peak_volume_km:.0f}km/week")
    lines.append("")

    # Key milestones (find long runs and quality sessions)
    milestones = []
    for week in plan.weeks:
        for workout in week.workouts:
            if workout.key_workout and workout.workout_type in {"long_run", "intervals", "tempo"}:
                if len(milestones) < 3:  # Show first 3 key workouts
                    workout_str = f"{_workout_type_display(workout.workout_type)} - Week {week.week_number}"
                    milestones.append(workout_str)

    if milestones:
        lines.append("**Key Workouts Coming:**")
        for milestone in milestones:
            lines.append(f"- {milestone}")
        lines.append("")

    # Constraints applied
    if plan.constraints_applied:
        lines.append("**Training Constraints:**")
        for constraint in plan.constraints_applied[:3]:
            lines.append(f"- {constraint}")

    return FormattedResponse(
        response_type=ResponseType.PLAN_OVERVIEW,
        content="\n".join(lines),
        metrics_shown=[],
        suggestions_count=0,
        follow_up_questions=["Would you like to see this week's detailed schedule?"],
    )


def format_error(
    error_type: str,
    message: str,
    recovery_hint: Optional[str] = None,
) -> FormattedResponse:
    """
    Format user-friendly error messages.

    Process:
        1. Map error_type to friendly title
        2. Format message clearly
        3. Add recovery hint if available
        4. Return structured error response

    Args:
        error_type: Type of error (e.g., "strava_auth", "file_not_found")
        message: Specific error message
        recovery_hint: Optional suggestion for how to fix

    Returns:
        Formatted error response
    """
    lines = []

    # Map error types to friendly titles
    error_titles = {
        "strava_auth": "Strava Authentication Error",
        "file_not_found": "File Not Found",
        "parse_error": "Configuration Error",
        "validation_error": "Validation Error",
        "network_error": "Network Error",
        "insufficient_data": "Insufficient Data",
        "goal_not_set": "Goal Not Set",
    }

    title = error_titles.get(error_type, "Error")
    lines.append(f"## {title}")
    lines.append("")

    # Error message
    lines.append(f"**Issue:** {message}")
    lines.append("")

    # Recovery hint
    if recovery_hint:
        lines.append(f"**How to fix:** {recovery_hint}")
    else:
        # Provide default hints based on error type
        default_hints = {
            "strava_auth": "Try running 'claude sync strava' again to re-authenticate.",
            "file_not_found": "Make sure you've synced your data first.",
            "goal_not_set": "Set a goal with 'claude set goal' to generate a training plan.",
            "insufficient_data": "This requires at least 14 days of training data. Keep syncing activities!",
        }
        if error_type in default_hints:
            lines.append(f"**How to fix:** {default_hints[error_type]}")

    lines.append("")
    lines.append("If the issue persists, check the logs or report at https://github.com/anthropics/claude-code/issues")

    return FormattedResponse(
        response_type=ResponseType.ERROR_MESSAGE,
        content="\n".join(lines),
        metrics_shown=[],
        suggestions_count=0,
        follow_up_questions=[],
    )


# Utility formatters
def format_date_full(d: date) -> str:
    """Format date as 'Tuesday March 18th'"""
    ...


def format_duration(minutes: int) -> str:
    """Format duration as '45 minutes' or '1h 30m'"""
    ...


def format_pace(min_per_km: float) -> str:
    """Format pace as '5:15/km'"""
    ...


def format_load(load_au: float) -> str:
    """
    Format load with context.

    Provides qualitative description based on typical load ranges:
    - <100 AU: light recovery session
    - 100-300 AU: moderate session
    - 300-500 AU: solid workout
    - 500-700 AU: hard session
    - >700 AU: very demanding session

    Args:
        load_au: Load value in arbitrary units

    Returns:
        Formatted load string with context
    """
    if load_au < 100:
        context = "(light recovery)"
    elif load_au < 300:
        context = "(moderate session)"
    elif load_au < 500:
        context = "(solid workout)"
    elif load_au < 700:
        context = "(hard session)"
    else:
        context = "(very demanding)"

    return f"{load_au:.0f} AU {context}"


def contextualize_metric(
    metric_name: str,
    value: float,
) -> tuple[str, str]:
    """
    Add context to raw metric value.

    Returns (context_phrase, zone_name)
    """
    ...
```

### 4.3 Error Types

```python
class FormattingError(Exception):
    """Base error for formatting failures"""
    pass


class MissingDataError(FormattingError):
    """Required data not available for formatting"""
    def __init__(self, data_type: str):
        super().__init__(f"Missing data for formatting: {data_type}")
        self.data_type = data_type
```

## 5. Core Algorithms

### 5.1 Workout Today Formatter

```python
def format_workout_today(
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    suggestions: list["Suggestion"],
    profile: "AthleteProfile",
) -> FormattedResponse:
    """
    Format today's workout with full context.
    """
    lines = []

    # Header with date
    date_str = format_date_full(workout.date)
    lines.append(f"## {date_str}")
    lines.append("")

    # Check for pending suggestions
    relevant_suggestions = [
        s for s in suggestions
        if s.affected_workout.date == workout.date
        and s.status == "pending"
    ]

    if relevant_suggestions:
        lines.append(_format_suggestion_alert(relevant_suggestions[0]))
        lines.append("")

    # Workout prescription
    lines.append(f"**{_workout_type_display(workout.workout_type)}**")
    lines.append("")

    # Duration and intensity
    lines.append(f"- Duration: {format_duration(workout.duration_minutes)}")
    lines.append(f"- Intensity: {_intensity_display(workout)}")

    # Pace/HR guidance
    if workout.pace_range_min_km:
        lines.append(f"- Target pace: {workout.pace_range_min_km}-{workout.pace_range_max_km}/km")
    if workout.hr_range_low:
        lines.append(f"- Target HR: {workout.hr_range_low}-{workout.hr_range_high} bpm")

    lines.append("")

    # Purpose
    lines.append(f"**Purpose:** {workout.purpose}")
    lines.append("")

    # Rationale based on metrics
    rationale = _generate_workout_rationale(workout, metrics, profile)
    lines.append(f"**Why this today:** {rationale}")
    lines.append("")

    # Current status
    lines.append("**Current status:**")
    lines.append(_format_status_brief(metrics))

    # Notes if any
    if workout.notes:
        lines.append("")
        lines.append(f"💡 {workout.notes}")

    return FormattedResponse(
        response_type=ResponseType.WORKOUT_TODAY,
        content="\n".join(lines),
        metrics_shown=["readiness", "tsb"],
        suggestions_count=len(relevant_suggestions),
        follow_up_questions=[],
    )


def _workout_type_display(workout_type: str) -> str:
    """Convert workout type to display name"""
    return {
        "easy": "Easy Run",
        "long_run": "Long Run",
        "tempo": "Tempo Run",
        "intervals": "Interval Session",
        "fartlek": "Fartlek",
        "rest": "Rest Day",
        "strides": "Easy + Strides",
    }.get(workout_type, workout_type.replace("_", " ").title())


def _intensity_display(workout: "WorkoutPrescription") -> str:
    """Format intensity with RPE and zone"""
    zone_names = {
        "zone_1": "Recovery",
        "zone_2": "Easy aerobic",
        "zone_3": "Moderate aerobic",
        "zone_4": "Threshold",
        "zone_5": "VO2max",
    }
    zone_name = zone_names.get(workout.intensity_zone, workout.intensity_zone)
    return f"RPE {workout.target_rpe}/10 — {zone_name}"


def _generate_workout_rationale(
    workout: "WorkoutPrescription",
    metrics: "DailyMetrics",
    profile: "AthleteProfile",
) -> str:
    """Generate context-aware rationale for the workout"""
    parts = []

    # TSB-based reasoning
    tsb = metrics.ctl_atl.tsb
    if tsb > 5:
        parts.append("You're fresh")
    elif tsb > -10:
        parts.append("Form is good")
    elif tsb > -20:
        parts.append("Training load is building")
    else:
        parts.append("You've been working hard")

    # Workout-specific reasoning
    if workout.workout_type == "easy":
        parts.append("— today is about recovery and maintaining base")
    elif workout.workout_type == "long_run":
        parts.append("— long run builds endurance and fat oxidation")
    elif workout.workout_type == "tempo":
        parts.append("— threshold work improves lactate clearance")
    elif workout.workout_type == "intervals":
        parts.append("— VO2max intervals boost aerobic ceiling")

    # Phase context
    if workout.phase:
        phase_context = {
            "base": "We're building your aerobic foundation.",
            "build": "This phase focuses on increasing intensity.",
            "peak": "Race-specific work to sharpen fitness.",
            "taper": "Reducing volume while staying sharp.",
        }
        if workout.phase in phase_context:
            parts.append(phase_context[workout.phase])

    return " ".join(parts)
```

### 5.2 Weekly Status Formatter

```python
def format_weekly_status(
    week_plan: "WeekPlan",
    activities: list["NormalizedActivity"],
    metrics: "DailyMetrics",
    profile: "AthleteProfile",
) -> FormattedResponse:
    """
    Format weekly status with all activities.
    """
    lines = []

    # Header
    phase_name = week_plan.phase.value.title() if week_plan.phase else ""
    week_range = f"{format_date_short(week_plan.start_date)} - {format_date_short(week_plan.end_date)}"
    lines.append(f"## Week {week_plan.week_number} of {profile.goal.total_weeks or '?'} ({phase_name} Phase) — {week_range}")
    lines.append("")

    # Day-by-day breakdown
    for day_offset in range(7):
        current_date = week_plan.start_date + timedelta(days=day_offset)
        day_str = format_date_weekday(current_date)

        # Find activities on this day
        day_activities = [
            a for a in activities if a.date == current_date
        ]

        # Find planned workout
        planned = next(
            (w for w in week_plan.workouts if w.date == current_date),
            None
        )

        line = f"{day_str}: "

        if day_activities:
            # Show completed activities
            activity_strs = []
            for act in day_activities:
                act_str = _format_activity_brief(act)
                activity_strs.append(act_str)
            line += " + ".join(activity_strs)

            # Show load breakdown
            total_sys = sum(a.calculated.get("systemic_load_au", 0) for a in day_activities)
            total_lb = sum(a.calculated.get("lower_body_load_au", 0) for a in day_activities)
            if total_sys > 0:
                line += f"\n            → Systemic: {total_sys:.0f} AU | Lower-body: {total_lb:.0f} AU"

            if current_date == date.today():
                line += " ← TODAY"

        elif planned:
            # Show planned workout
            status_icon = "→" if current_date >= date.today() else "○"
            line += f"{status_icon} {_workout_type_display(planned.workout_type)} {format_duration(planned.duration_minutes)}"

            if current_date == date.today():
                line += " ← TODAY"
        else:
            line += "Rest"

        lines.append(line)

    lines.append("")

    # Running progress
    run_done = sum(1 for a in activities if a.sport_type in {"run", "trail_run", "treadmill_run"})
    run_planned = sum(1 for w in week_plan.workouts if w.workout_type != "rest")
    lines.append(f"**Running Progress:** {run_done}/{run_planned} complete")

    # Load totals
    total_sys = sum(
        a.calculated.get("systemic_load_au", 0)
        for a in activities
    )
    total_lb = sum(
        a.calculated.get("lower_body_load_au", 0)
        for a in activities
    )
    lines.append(f"**Total Week Load:** {total_sys:.0f} AU systemic | {total_lb:.0f} AU lower-body (so far)")
    lines.append("")

    # Current metrics
    lines.append("**Current Status:**")
    lines.append(_format_metrics_display(metrics, profile))

    return FormattedResponse(
        response_type=ResponseType.WEEKLY_STATUS,
        content="\n".join(lines),
        metrics_shown=["ctl", "tsb", "acwr"],
        suggestions_count=0,
        follow_up_questions=[],
    )


def _format_activity_brief(activity: "NormalizedActivity") -> str:
    """Format activity for weekly display"""
    sport_display = {
        "run": "Running",
        "trail_run": "Trail",
        "treadmill_run": "Treadmill",
        "cycle": "Cycling",
        "swim": "Swimming",
        "climb": "Bouldering",
        "strength": "Strength",
        "yoga": "Yoga",
        "hike": "Hiking",
    }

    sport_name = sport_display.get(activity.sport_type, activity.sport_type.title())

    if activity.duration_minutes >= 60:
        duration = f"{activity.duration_minutes // 60}h {activity.duration_minutes % 60}m"
    else:
        duration = f"{activity.duration_minutes}min"

    # Add distance for running
    if activity.sport_type in {"run", "trail_run"} and activity.distance_km:
        return f"{sport_name} ({activity.distance_km:.1f}km, {duration}) ✓"

    return f"{sport_name} ({duration}) ✓"
```

### 5.3 Metrics Display with Context

```python
# Metric context tables
CTL_CONTEXT = [
    (0, 20, "building base", "beginner"),
    (20, 40, "developing", "developing"),
    (40, 60, "solid recreational level", "recreational"),
    (60, 80, "well-trained", "trained"),
    (80, 100, "competitive amateur", "competitive"),
    (100, 150, "elite amateur", "elite"),
]

TSB_CONTEXT = [
    (-100, -25, "overreached - rest needed", "overreached"),
    (-25, -10, "productive training zone", "productive"),
    (-10, 5, "optimal for quality work", "optimal"),
    (5, 15, "fresh - good for racing", "fresh"),
    (15, 100, "peaked - may be detrained", "peaked"),
]

ACWR_CONTEXT = [
    (0, 0.8, "undertrained - fitness declining", "undertrained"),
    (0.8, 1.0, "safe zone (maintaining)", "safe_low"),
    (1.0, 1.3, "safe zone (building)", "safe"),
    (1.3, 1.5, "caution - monitor closely", "caution"),
    (1.5, 3.0, "high injury risk", "high_risk"),
]


def contextualize_metric(
    metric_name: str,
    value: float,
) -> tuple[str, str]:
    """Add context to raw metric value."""
    context_tables = {
        "ctl": CTL_CONTEXT,
        "tsb": TSB_CONTEXT,
        "acwr": ACWR_CONTEXT,
    }

    table = context_tables.get(metric_name.lower())
    if not table:
        return "", ""

    for low, high, description, zone in table:
        if low <= value < high:
            return description, zone

    return "", ""


def _format_metrics_display(
    metrics: "DailyMetrics",
    profile: "AthleteProfile",
) -> str:
    """Format metrics with progressive disclosure."""
    lines = []

    # Determine disclosure level based on training age
    days_of_data = metrics.acwr.days_of_data
    if days_of_data < 14:
        level = MetricLevel.BASIC
    elif days_of_data < 28:
        level = MetricLevel.INTERMEDIATE
    else:
        level = MetricLevel.ADVANCED

    # CTL (fitness)
    ctl = metrics.ctl_atl.ctl
    ctl_context, _ = contextualize_metric("ctl", ctl)
    lines.append(f"- Fitness (CTL): {ctl:.0f} ({ctl_context})")

    # TSB (form)
    tsb = metrics.ctl_atl.tsb
    tsb_context, _ = contextualize_metric("tsb", tsb)
    lines.append(f"- Form (TSB): {tsb:+.0f} ({tsb_context})")

    # ACWR (only if advanced)
    if level == MetricLevel.ADVANCED and metrics.acwr.acwr is not None:
        acwr = metrics.acwr.acwr
        acwr_context, _ = contextualize_metric("acwr", acwr)
        lines.append(f"- ACWR: {acwr:.2f} ({acwr_context})")

    # Readiness
    readiness = metrics.readiness
    lines.append(f"- Readiness: {readiness.score}/100 ({readiness.level.value})")

    return "\n".join(lines)
```

### 5.4 Sync Summary Formatter

```python
def format_sync_summary(
    sync_result: "SyncResult",
    new_activities: list["NormalizedActivity"],
    metrics_delta: dict,
    suggestions: list["Suggestion"],
) -> FormattedResponse:
    """Format Strava sync results."""
    lines = []

    # Header
    if sync_result.success:
        lines.append("## Sync Complete ✓")
    else:
        lines.append("## Sync Completed with Issues")
    lines.append("")

    # Activity summary
    if sync_result.activities_new > 0:
        lines.append(f"**{sync_result.activities_new} new activities imported:**")
        for activity in new_activities[:5]:  # Show up to 5
            lines.append(f"- {_format_activity_brief(activity)}")
        if len(new_activities) > 5:
            lines.append(f"- ... and {len(new_activities) - 5} more")
        lines.append("")

    # Metrics update
    if metrics_delta:
        lines.append("**Metrics updated:**")
        if "ctl_delta" in metrics_delta:
            delta = metrics_delta["ctl_delta"]
            direction = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            lines.append(f"- Fitness (CTL): {direction} {abs(delta):.1f}")
        lines.append("")

    # Pending suggestions
    if suggestions:
        lines.append(f"**{len(suggestions)} suggestion(s) pending:**")
        for sugg in suggestions[:3]:
            lines.append(f"- {sugg.rationale}")
        lines.append("")
        lines.append("Would you like me to explain these suggestions?")

    # Errors if any
    if sync_result.errors:
        lines.append("")
        lines.append("**Issues:**")
        for error in sync_result.errors[:3]:
            lines.append(f"- {error}")

    return FormattedResponse(
        response_type=ResponseType.SYNC_SUMMARY,
        content="\n".join(lines),
        metrics_shown=["ctl", "atl"],
        suggestions_count=len(suggestions),
        follow_up_questions=["Would you like to see your updated weekly status?"],
    )
```

### 5.5 Suggestion Prompt Formatter

```python
def format_suggestions(
    suggestions: list["Suggestion"],
    profile: "AthleteProfile",
) -> FormattedResponse:
    """Format pending suggestions for user decision."""
    if not suggestions:
        return FormattedResponse(
            response_type=ResponseType.SUGGESTION_PROMPT,
            content="No pending suggestions.",
            metrics_shown=[],
            suggestions_count=0,
            follow_up_questions=[],
        )

    lines = []
    lines.append("## Workout Adjustment Suggestions")
    lines.append("")

    for i, sugg in enumerate(suggestions, 1):
        lines.append(f"### Suggestion {i}")
        lines.append("")

        # What's affected
        workout_date = format_date_full(sugg.affected_workout.date)
        lines.append(f"**Workout:** {sugg.affected_workout.workout_type.title()} on {workout_date}")
        lines.append("")

        # The recommendation
        lines.append(f"**Recommendation:** {_suggestion_type_display(sugg.suggestion_type)}")
        lines.append("")

        # Rationale
        lines.append(f"**Why:** {sugg.rationale}")
        lines.append("")

        # Original vs proposed
        lines.append("**Change:**")
        lines.append(f"- From: {sugg.original['workout_type']} @ RPE {sugg.original['target_rpe']}")
        lines.append(f"- To: {sugg.proposed.workout_type} @ RPE {sugg.proposed.target_rpe}")
        lines.append("")

        # Risk warning if applicable
        if sugg.override_risk in {"high", "severe"}:
            lines.append(f"⚠️ **Override risk:** {sugg.override_risk.upper()}")
            lines.append("")

    # Decision prompt
    lines.append("---")
    lines.append("Would you like to **accept** or **decline** these suggestions?")
    lines.append("(You can say 'accept all', 'decline suggestion 1', etc.)")

    return FormattedResponse(
        response_type=ResponseType.SUGGESTION_PROMPT,
        content="\n".join(lines),
        metrics_shown=[],
        suggestions_count=len(suggestions),
        follow_up_questions=[],
    )


def _suggestion_type_display(suggestion_type: "SuggestionType") -> str:
    """Convert suggestion type to readable text"""
    return {
        "downgrade": "Reduce intensity",
        "skip": "Skip this workout",
        "move": "Move to a different day",
        "substitute": "Replace with different workout",
        "shorten": "Reduce duration",
        "force_rest": "Take a rest day",
    }.get(suggestion_type, suggestion_type)
```

### 5.6 Date and Time Formatters

```python
from datetime import date, timedelta


def format_date_full(d: date) -> str:
    """Format as 'Tuesday March 18th'"""
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]

    day_name = day_names[d.weekday()]
    month_name = month_names[d.month - 1]
    day_ordinal = _ordinal(d.day)

    return f"{day_name} {month_name} {day_ordinal}"


def format_date_short(d: date) -> str:
    """Format as 'Mar 18'"""
    month_abbrev = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{month_abbrev[d.month - 1]} {d.day}"


def format_date_weekday(d: date) -> str:
    """Format as 'Mon Mar 18'"""
    day_abbrev = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return f"{day_abbrev[d.weekday()]} {format_date_short(d)}"


def format_duration(minutes: int) -> str:
    """Format duration human-readably"""
    if minutes < 60:
        return f"{minutes} minutes"
    elif minutes % 60 == 0:
        return f"{minutes // 60}h"
    else:
        return f"{minutes // 60}h {minutes % 60}min"


def format_pace(min_per_km: float) -> str:
    """Format pace as mm:ss/km"""
    minutes = int(min_per_km)
    seconds = int((min_per_km - minutes) * 60)
    return f"{minutes}:{seconds:02d}/km"


def _ordinal(n: int) -> str:
    """Convert number to ordinal (1st, 2nd, 3rd, etc.)"""
    if 11 <= n <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
```

## 6. Display Templates

### 6.1 Workout Today Template

```
## Tuesday March 18th

**Tempo Run**

- Duration: 45 minutes
- Intensity: RPE 7/10 — Threshold
- Target pace: 5:15-5:25/km
- Target HR: 160-170 bpm

**Purpose:** Build lactate threshold

**Why this today:** Form is good — threshold work improves lactate clearance. This phase focuses on increasing intensity.

**Current status:**
- Fitness (CTL): 44 (solid recreational level)
- Form (TSB): -8 (productive training zone)
- Readiness: 62/100 (ready)

💡 Keep effort steady. Should feel comfortably hard.
```

### 6.2 Weekly Status Template

```
## Week 3 of 14 (Build Phase) — Mar 10 - Mar 16

Mon Mar 10: Bouldering (2h) ✓
            → Systemic: 630 AU | Lower-body: 105 AU
Tue Mar 11: Running (8.2km, 48min) ✓
            → Systemic: 336 AU | Lower-body: 336 AU
Wed Mar 12: Running (5.5km, 35min) ✓
            → Systemic: 175 AU | Lower-body: 175 AU
Thu Mar 13: Bouldering (2h) + → Easy Run 30min ← TODAY
Fri Mar 14: Rest
Sat Mar 15: → Long Run 14km
Sun Mar 16: Cycling 90min (planned)

**Running Progress:** 2/4 complete
**Total Week Load:** 1,141 AU systemic | 616 AU lower-body (so far)

**Current Status:**
- Fitness (CTL): 44 (solid recreational level)
- Form (TSB): -8 (productive training zone)
- ACWR: 1.15 (safe zone)
- Readiness: 62/100 (ready)
```

## 7. Integration Points

### 7.1 Called By

| Module | When |
|--------|------|
| M1 | After determining user intent |

### 7.2 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Read data files |
| M9 | Get current metrics |
| M10 | Get plan structure |
| M11 | Get pending suggestions |

### 7.3 Returns To

| Module | Data |
|--------|------|
| M1 | Formatted response for user display |

## 8. Test Scenarios

### 8.1 Formatting Tests

```python
def test_format_date_full():
    """Full date formatting"""
    d = date(2025, 3, 18)
    assert format_date_full(d) == "Tuesday March 18th"


def test_format_duration_hours():
    """Duration with hours"""
    assert format_duration(90) == "1h 30min"
    assert format_duration(60) == "1h"
    assert format_duration(45) == "45 minutes"


def test_metric_contextualization():
    """Metrics get appropriate context"""
    context, zone = contextualize_metric("ctl", 45)
    assert "recreational" in context.lower()

    context, zone = contextualize_metric("tsb", -15)
    assert "productive" in context.lower()


def test_workout_today_includes_rationale():
    """Workout display includes why explanation"""
    response = format_workout_today(
        mock_workout(), mock_metrics(), [], mock_profile()
    )

    assert "Why this today" in response.content
```

### 8.2 Multi-Sport Display Tests

```python
def test_weekly_shows_all_sports():
    """Weekly status includes non-running activities"""
    activities = [
        mock_activity(sport_type="run"),
        mock_activity(sport_type="climb"),
        mock_activity(sport_type="cycle"),
    ]

    response = format_weekly_status(
        mock_week_plan(), activities, mock_metrics(), mock_profile()
    )

    assert "Bouldering" in response.content or "climb" in response.content.lower()
    assert "Cycling" in response.content or "cycle" in response.content.lower()


def test_load_breakdown_shown():
    """Activities show systemic and lower-body load"""
    response = format_weekly_status(
        mock_week_plan(), [mock_activity()], mock_metrics(), mock_profile()
    )

    assert "Systemic:" in response.content
    assert "Lower-body:" in response.content
```

## 9. Configuration

### 9.1 Display Settings

```python
FORMATTER_CONFIG = {
    "max_activities_in_summary": 5,
    "show_load_breakdown": True,
    "use_emojis": False,  # Terminal-friendly
    "progressive_disclosure": True,
    "disclosure_day_thresholds": {
        "basic": 0,
        "intermediate": 14,
        "advanced": 28,
    },
}
```

## 10. Tone Guidelines

The coach responses should be:
- **Conversational** - Natural language, not robotic
- **Data-driven** - Reference actual metrics
- **Explanatory** - Always explain the "why"
- **Encouraging** - Positive but honest
- **Concise** - Respect terminal space
