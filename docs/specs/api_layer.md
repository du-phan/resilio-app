# API Layer Specification

## 1. Overview

### 1.1 Purpose

The API layer provides a clean, well-documented interface between **Claude Code** (the AI coach interface) and the **sports-coach-engine** package (domain logic). Claude Code calls these functions to fulfill user requests.

### 1.2 Design Principles

1. **Zero-configuration entry points**: Functions have sensible defaults, no complex setup required
2. **Rich return types**: All functions return Pydantic models with interpretive context
3. **Self-describing**: Return types include human-readable interpretations (e.g., "CTL 44 = solid recreational level")
4. **Error handling via types**: Functions return `Result | Error` unions, not exceptions
5. **Stateless**: Functions don't maintain global state; all state is in files

### 1.3 Relationship to Other Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Claude Code                              │
│  (Intent understanding, conversation, response formatting)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ imports and calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer (THIS SPEC)                         │
│  sports_coach_engine.api.*                                       │
│  - sync_strava(), get_todays_workout(), get_current_metrics()    │
│  - Returns: WorkoutRecommendation, SyncResult, EnrichedMetrics   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ calls internally
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Internal Modules (core/)                        │
│  workflows, strava, normalization, load, metrics, plan, etc.     │
│  - Pure domain logic, no user-facing concerns                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Package Structure

```
sports_coach_engine/
├── __init__.py              # Re-exports from api/
├── api/                     # PUBLIC: Claude Code uses this
│   ├── __init__.py          # All public exports with __all__
│   ├── coach.py             # get_todays_workout, get_weekly_status, etc.
│   ├── sync.py              # sync_strava, log_activity
│   ├── metrics.py           # get_current_metrics, get_readiness
│   ├── plan.py              # get_current_plan, regenerate_plan, accept/decline
│   ├── profile.py           # get_profile, update_profile, set_goal
│   └── vdot.py              # calculate_vdot_from_race, get_training_paces, etc.
├── core/                    # INTERNAL: Not for direct use
│   ├── workflows.py         # Multi-step operation orchestration
│   ├── config.py            # Configuration and secrets
│   ├── repository.py        # File I/O (also exposed for direct access)
│   ├── profile.py           # Athlete profile operations
│   ├── strava.py            # Strava API integration
│   ├── normalization.py     # Activity normalization
│   ├── notes.py             # Notes and RPE analysis
│   ├── load.py              # Load calculation
│   ├── metrics.py           # CTL/ATL/TSB computation
│   ├── plan.py              # Plan generation
│   ├── adaptation.py        # Workout adaptation
│   ├── enrichment.py        # Data context enrichment
│   ├── memory.py            # Insights extraction
│   ├── logger.py            # Conversation logging
│   └── vdot/                # VDOT calculations (Daniels' Running Formula)
│       ├── calculator.py    # Core VDOT calculations
│       ├── tables.py        # VDOT lookup tables
│       └── adjustments.py   # Environmental pace adjustments
└── schemas/                 # Pydantic models, exported for type hints
```

---

## 3. Public API Functions

### 3.1 Module: api/coach.py

High-level coaching operations that combine multiple internal modules.

```python
from datetime import date
from typing import Optional

from sports_coach_engine.schemas import (
    WorkoutRecommendation,
    WeeklyStatus,
    TrainingStatus,
    WorkoutExplanation,
)


def get_todays_workout(
    target_date: Optional[date] = None,
) -> WorkoutRecommendation:
    """
    Get today's recommended workout with full context.

    Args:
        target_date: Date to get workout for. Defaults to today.

    Returns:
        WorkoutRecommendation containing:
        - workout: The workout prescription (type, duration, intensity)
        - rationale: Why this workout today (based on metrics, plan phase)
        - metrics_context: Current CTL/TSB that informed the decision
        - pending_suggestions: Any adaptations to consider
        - warnings: Injury flags, high ACWR, etc.

    Example:
        >>> workout = get_todays_workout()
        >>> print(workout.workout.workout_type)  # "tempo"
        >>> print(workout.rationale.primary_reason)  # "Form is good"
    """
    ...


def get_weekly_status() -> WeeklyStatus:
    """
    Get current week overview with all activities.

    Returns:
        WeeklyStatus containing:
        - week_number: Current week in plan
        - phase: Training phase (base, build, peak, taper)
        - days: List of day summaries (completed activities, planned workouts)
        - progress: Running workouts completed vs planned
        - load_summary: Total systemic and lower-body load
        - metrics: Current CTL/TSB/ACWR with interpretations

    Example:
        >>> status = get_weekly_status()
        >>> print(f"Week {status.week_number}: {status.progress.completed}/{status.progress.planned}")
    """
    ...


def get_training_status() -> TrainingStatus:
    """
    Get current training metrics with interpretations.

    Returns:
        TrainingStatus containing:
        - fitness (CTL): Current chronic training load with interpretation
        - fatigue (ATL): Current acute training load
        - form (TSB): Training stress balance with zone
        - acwr: Acute:chronic workload ratio with risk level
        - readiness: Overall readiness score (0-100)
        - intensity_distribution: 7-day intensity breakdown (80/20 check)

    Example:
        >>> status = get_training_status()
        >>> print(f"Fitness: {status.fitness.value} ({status.fitness.interpretation})")
        # Output: "Fitness: 44 (solid recreational level)"
    """
    ...


def explain_workout(workout_id: str) -> WorkoutExplanation:
    """
    Get detailed explanation of why a specific workout is prescribed.

    Args:
        workout_id: ID of the workout to explain

    Returns:
        WorkoutExplanation with detailed rationale
    """
    ...
```

### 3.2 Module: api/sync.py

Strava synchronization and manual activity logging.

```python
from datetime import date, datetime
from typing import Optional

from sports_coach_engine.schemas import (
    SyncResult,
    SyncError,
    Activity,
)


def sync_strava(
    since: Optional[datetime] = None,
) -> SyncResult | SyncError:
    """
    Import activities from Strava.

    Handles:
    - Token refresh if needed
    - Activity deduplication
    - Normalization, RPE analysis, load calculation
    - Metrics recomputation
    - Memory extraction from notes

    Args:
        since: Fetch activities since this datetime. Defaults to last_sync_at.

    Returns:
        SyncResult on success:
        - activities_imported: List of new activities with enriched data
        - metrics_updated: Current metrics after sync
        - suggestions_generated: Any adaptation suggestions triggered
        - memories_extracted: Insights extracted from activity notes

        SyncError on failure:
        - error_type: "auth", "rate_limit", "network", "partial"
        - message: Human-readable error description
        - retry_after: Seconds to wait (for rate limits)

    Example:
        >>> result = sync_strava()
        >>> if isinstance(result, SyncError):
        ...     print(f"Sync failed: {result.message}")
        ... else:
        ...     print(f"Synced {len(result.activities_imported)} activities")
    """
    ...


def log_activity(
    sport_type: str,
    duration_minutes: int,
    rpe: Optional[int] = None,
    notes: Optional[str] = None,
    date: Optional[date] = None,
    distance_km: Optional[float] = None,
) -> Activity:
    """
    Log a manual activity (not from Strava).

    Args:
        sport_type: Type of activity (e.g., "run", "climb", "cycle")
        duration_minutes: Duration in minutes
        rpe: Rate of perceived exertion (1-10). If None, estimated from notes.
        notes: Optional activity notes
        date: Activity date. Defaults to today.
        distance_km: Distance in kilometers (for running)

    Returns:
        Activity with calculated loads and enriched data

    Example:
        >>> activity = log_activity(
        ...     sport_type="run",
        ...     duration_minutes=45,
        ...     rpe=6,
        ...     notes="Felt good, easy pace"
        ... )
    """
    ...
```

### 3.3 Module: api/metrics.py

Metrics queries with interpretive context.

```python
from sports_coach_engine.schemas import (
    EnrichedMetrics,
    ReadinessScore,
    IntensityDistribution,
)


def get_current_metrics() -> EnrichedMetrics:
    """
    Get current training metrics with human-readable interpretations.

    Returns:
        EnrichedMetrics containing:
        - date: Metrics date
        - ctl: Chronic Training Load with interpretation
          - value: 44
          - interpretation: "solid recreational level"
          - trend: "+2 this week"
        - atl: Acute Training Load
        - tsb: Training Stress Balance with zone
          - value: -8
          - zone: "productive"
          - interpretation: "productive training zone"
        - acwr: Acute:Chronic Workload Ratio with risk level
        - readiness: Overall readiness score

    Example:
        >>> metrics = get_current_metrics()
        >>> print(f"CTL: {metrics.ctl.value} ({metrics.ctl.interpretation})")
        # Output: "CTL: 44 (solid recreational level)"
    """
    ...


def get_readiness() -> ReadinessScore:
    """
    Get current readiness score with detailed breakdown.

    Returns:
        ReadinessScore with:
        - score: 0-100 overall readiness
        - level: "fresh", "ready", "tired", "exhausted"
        - components: Breakdown of contributing factors
        - recommendation: Suggested workout intensity

    Example:
        >>> readiness = get_readiness()
        >>> print(f"Readiness: {readiness.score}/100 ({readiness.level})")
    """
    ...


def get_intensity_distribution(days: int = 7) -> IntensityDistribution:
    """
    Get intensity distribution over a time period.

    Args:
        days: Number of days to analyze (default 7)

    Returns:
        IntensityDistribution with:
        - low_percent: Percentage in Zone 1-2
        - moderate_percent: Percentage in Zone 3
        - high_percent: Percentage in Zone 4-5
        - compliant_80_20: Whether 80/20 rule is being followed
        - recommendation: Suggestions for balance

    Example:
        >>> dist = get_intensity_distribution()
        >>> print(f"Low: {dist.low_percent}% | Meeting 80/20: {dist.compliant_80_20}")
    """
    ...
```

### 3.4 Module: api/plan.py

Training plan operations and adaptation management.

```python
from typing import Optional

from sports_coach_engine.schemas import (
    TrainingPlan,
    Goal,
    Suggestion,
    AcceptResult,
    DeclineResult,
)


def get_current_plan() -> TrainingPlan:
    """
    Get the full training plan with all weeks.

    Returns:
        TrainingPlan containing:
        - goal: Target race/goal
        - total_weeks: Plan duration
        - current_week: Current week number
        - phase: Current training phase
        - weeks: All planned weeks with workouts
        - constraints_applied: Training constraints in effect

    Example:
        >>> plan = get_current_plan()
        >>> print(f"Week {plan.current_week}/{plan.total_weeks} ({plan.phase})")
    """
    ...


def regenerate_plan(goal: Optional[Goal] = None) -> TrainingPlan:
    """
    Generate a new training plan.

    If a goal is provided, updates the athlete's goal first.
    Archives the current plan before generating a new one.

    Args:
        goal: New goal (optional). If None, regenerates with current goal.

    Returns:
        New TrainingPlan
    """
    ...


def get_pending_suggestions() -> list[Suggestion]:
    """
    Get pending adaptation suggestions awaiting user decision.

    Returns:
        List of Suggestion objects, each containing:
        - id: Unique suggestion ID
        - trigger: What triggered this suggestion (e.g., "acwr_elevated")
        - affected_workout: The workout to be modified
        - suggestion_type: "downgrade", "skip", "move", "substitute"
        - rationale: Why this suggestion was made
        - original: Original workout details
        - proposed: Proposed modification
        - expires_at: When suggestion expires

    Example:
        >>> suggestions = get_pending_suggestions()
        >>> for s in suggestions:
        ...     print(f"{s.suggestion_type}: {s.rationale}")
    """
    ...


def accept_suggestion(suggestion_id: str) -> AcceptResult:
    """
    Accept a pending suggestion and apply the modification.

    Args:
        suggestion_id: ID of the suggestion to accept

    Returns:
        AcceptResult with:
        - success: Whether the suggestion was applied
        - workout_modified: The modified workout
        - confirmation_message: Human-readable confirmation

    Example:
        >>> result = accept_suggestion("sugg_2024-01-15_001")
        >>> print(result.confirmation_message)
    """
    ...


def decline_suggestion(suggestion_id: str) -> DeclineResult:
    """
    Decline a pending suggestion and keep the original plan.

    Args:
        suggestion_id: ID of the suggestion to decline

    Returns:
        DeclineResult with:
        - success: Whether the suggestion was declined
        - original_kept: The original workout (unchanged)
    """
    ...
```

### 3.5 Module: api/profile.py

Athlete profile management.

```python
from datetime import date
from typing import Optional, Any

from sports_coach_engine.schemas import (
    AthleteProfile,
    Goal,
)


def get_profile() -> AthleteProfile:
    """
    Get current athlete profile.

    Returns:
        AthleteProfile containing:
        - name: Athlete name
        - goal: Current training goal
        - constraints: Training constraints (runs per week, etc.)
        - conflict_policy: How to handle sport conflicts
        - paces: VDOT-derived training paces
        - memories: Extracted athlete insights

    Example:
        >>> profile = get_profile()
        >>> print(f"Goal: {profile.goal.type} on {profile.goal.target_date}")
    """
    ...


def update_profile(**fields: Any) -> AthleteProfile:
    """
    Update athlete profile fields.

    Args:
        **fields: Fields to update (name, constraints, conflict_policy, etc.)

    Returns:
        Updated AthleteProfile

    Example:
        >>> profile = update_profile(
        ...     runs_per_week=4,
        ...     conflict_policy="running_goal_wins"
        ... )
    """
    ...


def set_goal(
    race_type: str,
    target_date: date,
    target_time: Optional[str] = None,
) -> Goal:
    """
    Set a new race goal and regenerate the training plan.

    Args:
        race_type: Type of race ("5k", "10k", "half_marathon", "marathon")
        target_date: Race date
        target_time: Target finish time (optional, e.g., "1:45:00")

    Returns:
        New Goal object

    Example:
        >>> goal = set_goal(
        ...     race_type="half_marathon",
        ...     target_date=date(2024, 3, 15),
        ...     target_time="1:45:00"
        ... )
    """
    ...
```

---

### 3.6 Module: api/vdot.py

VDOT calculations and training pace generation based on Jack Daniels' Running Formula.

```python
from typing import Union, Optional

from sports_coach_engine.schemas.vdot import (
    VDOTResult,
    TrainingPaces,
    RaceEquivalents,
    SixSecondRulePaces,
    PaceAdjustment,
)


def calculate_vdot_from_race(
    race_distance: str,
    race_time: str,
    race_date: Optional[str] = None,
) -> Union[VDOTResult, VDOTError]:
    """
    Calculate VDOT from race performance.

    Args:
        race_distance: Race distance ("mile", "5k", "10k", "15k", "half_marathon", "marathon")
        race_time: Race time as string ("MM:SS" or "HH:MM:SS")
        race_date: Optional race date (ISO format "YYYY-MM-DD") for confidence adjustment

    Returns:
        VDOTResult on success with:
        - vdot: Calculated VDOT value (30-85)
        - source_race: Input race distance
        - source_time_formatted: Formatted race time
        - confidence: "high" (race <2w old), "medium" (2-6w), "low" (>6w)

        VDOTError on failure with error_type and message

    Example:
        >>> result = calculate_vdot_from_race("10k", "42:30")
        >>> if not is_error(result):
        ...     print(f"VDOT: {result.vdot}")
    """
    ...


def get_training_paces(
    vdot: int,
    unit: str = "min_per_km",
) -> Union[TrainingPaces, VDOTError]:
    """
    Get all training pace zones from VDOT.

    Args:
        vdot: VDOT value (30-85)
        unit: Pace unit ("min_per_km" or "min_per_mile")

    Returns:
        TrainingPaces on success with:
        - easy_pace_range: Tuple[int, int] (seconds per km/mile)
        - marathon_pace_range: Marathon race pace
        - threshold_pace_range: Lactate threshold pace
        - interval_pace_range: VO2max interval pace
        - repetition_pace_range: Speed work pace

        VDOTError on failure (invalid VDOT or unit)

    Example:
        >>> paces = get_training_paces(48)
        >>> if not is_error(paces):
        ...     print(f"Easy: {paces.format_range(paces.easy_pace_range)}")
    """
    ...


def predict_race_times(
    race_distance: str,
    race_time: str,
) -> Union[RaceEquivalents, VDOTError]:
    """
    Predict equivalent race times for all distances.

    Calculates VDOT from input race, then predicts times for all other distances.

    Args:
        race_distance: Source race distance
        race_time: Source race time

    Returns:
        RaceEquivalents on success with:
        - vdot: Calculated VDOT
        - predictions: Dict mapping race distances to predicted times
        - source_race: Input race
        - confidence: Based on VDOT calculation

        VDOTError on failure

    Example:
        >>> result = predict_race_times("10k", "42:30")
        >>> if not is_error(result):
        ...     print(f"Predicted half: {result.predictions['half_marathon']}")
    """
    ...


def apply_six_second_rule_paces(
    mile_time: str
) -> Union[SixSecondRulePaces, VDOTError]:
    """
    Apply six-second rule for novice runners without recent race times.

    Rule: R-pace = mile pace, I-pace = R + 6s/400m, T-pace = I + 6s/400m
    (Uses 7-8 seconds for VDOT 40-50 range)

    Args:
        mile_time: Mile time as string ("M:SS")

    Returns:
        SixSecondRulePaces on success with:
        - r_pace_400m: Repetition pace per 400m
        - i_pace_400m: Interval pace per 400m
        - t_pace_400m: Threshold pace per 400m
        - adjustment_seconds: Adjustment used (6, 7, or 8)
        - estimated_vdot_range: Estimated VDOT range

        VDOTError on failure

    Example:
        >>> result = apply_six_second_rule_paces("6:00")
        >>> if not is_error(result):
        ...     print(f"R-pace: {result.r_pace_400m}s per 400m")
    """
    ...


def adjust_pace_for_environment(
    base_pace: str,
    condition_type: str,
    severity: float,
) -> Union[PaceAdjustment, VDOTError]:
    """
    Adjust pace for environmental conditions.

    Args:
        base_pace: Base pace as string ("M:SS" per km)
        condition_type: "altitude", "heat", "humidity", or "hills"
        severity: Severity value (altitude in ft, temp in °C, humidity %, grade %)

    Returns:
        PaceAdjustment on success with:
        - adjusted_pace_sec_per_km: Adjusted pace
        - adjustment_seconds: Slowdown amount
        - reason: Explanation of adjustment
        - recommendation: Coaching guidance

        VDOTError on failure

    Example:
        >>> result = adjust_pace_for_environment("5:00", "altitude", 7000)
        >>> if not is_error(result):
        ...     print(f"Adjusted pace: {result.adjusted_pace_sec_per_km}s/km")
        ...     print(f"Recommendation: {result.recommendation}")
    """
    ...
```

---


### 3.7 Module: api/guardrails.py

Volume validation and recovery planning based on Daniels Running Formula and Pfitzinger guidelines.

```python
from typing import Union, Optional

from sports_coach_engine.schemas.guardrails import (
    QualityVolumeValidation,
    WeeklyProgressionValidation,
    LongRunValidation,
    SafeVolumeRange,
    BreakReturnPlan,
    MastersRecoveryAdjustment,
    RaceRecoveryPlan,
    IllnessRecoveryPlan,
)


# Volume Validation Functions

def validate_quality_volume(
    t_pace_km: float,
    i_pace_km: float,
    r_pace_km: float,
    weekly_mileage_km: float,
) -> Union[QualityVolumeValidation, GuardrailsError]:
    """Validate T/I/R pace volumes against Daniels hard constraints."""
    ...

def validate_weekly_progression(
    previous_volume_km: float,
    current_volume_km: float,
) -> Union[WeeklyProgressionValidation, GuardrailsError]:
    """Validate weekly volume progression (10% rule)."""
    ...

def validate_long_run_limits(
    long_run_km: float,
    long_run_duration_minutes: int,
    weekly_volume_km: float,
    pct_limit: float = 30.0,
    duration_limit_minutes: int = 150,
) -> Union[LongRunValidation, GuardrailsError]:
    """Validate long run against weekly volume and duration limits."""
    ...

def calculate_safe_volume_range(
    current_ctl: float,
    goal_type: str = "fitness",
    athlete_age: Optional[int] = None,
) -> Union[SafeVolumeRange, GuardrailsError]:
    """Calculate safe weekly volume range based on CTL and goals."""
    ...


# Recovery Planning Functions

def calculate_break_return_plan(
    break_days: int,
    pre_break_ctl: float,
    cross_training_level: str = "none",
) -> Union[BreakReturnPlan, GuardrailsError]:
    """Generate return-to-training protocol per Daniels Table 9.2."""
    ...

def calculate_masters_recovery(
    age: int,
    workout_type: str,
) -> Union[MastersRecoveryAdjustment, GuardrailsError]:
    """Calculate age-specific recovery adjustments (Pfitzinger)."""
    ...

def calculate_race_recovery(
    race_distance: str,
    athlete_age: int,
    finishing_effort: str = "hard",
) -> Union[RaceRecoveryPlan, GuardrailsError]:
    """Determine post-race recovery protocol by distance and age."""
    ...

def generate_illness_recovery_plan(
    illness_start_date: str,
    illness_end_date: str,
    severity: str = "moderate",
) -> Union[IllnessRecoveryPlan, GuardrailsError]:
    """Generate structured return-to-training plan after illness."""
    ...
```

---

### 3.8 Module: api/analysis.py

Weekly insights, multi-sport load distribution, and holistic risk assessment.

```python
from typing import Union, List, Dict, Any, Optional
from datetime import date

from sports_coach_engine.schemas.analysis import (
    IntensityDistributionAnalysis,
    ActivityGapAnalysis,
    LoadDistributionAnalysis,
    WeeklyCapacityCheck,
    CurrentRiskAssessment,
    RecoveryWindowEstimate,
    TrainingStressForecast,
    TaperStatusAssessment,
)


# Weekly Analysis Functions

def api_validate_intensity_distribution(
    activities: List[Dict[str, Any]],
    date_range_days: int = 28,
) -> Union[IntensityDistributionAnalysis, AnalysisError]:
    """Validate 80/20 rule compliance (80% low, 20% high)."""
    ...

def api_detect_activity_gaps(
    activities: List[Dict[str, Any]],
    min_gap_days: int = 7,
) -> Union[ActivityGapAnalysis, AnalysisError]:
    """Detect training breaks with CTL impact and cause detection."""
    ...

def api_analyze_load_distribution_by_sport(
    activities: List[Dict[str, Any]],
    date_range_days: int = 7,
    sport_priority: str = "equal",
) -> Union[LoadDistributionAnalysis, AnalysisError]:
    """Analyze systemic and lower-body load across all sports."""
    ...

def api_check_weekly_capacity(
    week_number: int,
    planned_volume_km: float,
    planned_systemic_load_au: float,
    historical_activities: List[Dict[str, Any]],
) -> Union[WeeklyCapacityCheck, AnalysisError]:
    """Validate planned volume against proven capacity."""
    ...


# Risk Assessment Functions

def api_assess_current_risk(
    current_metrics: Dict[str, Any],
    recent_activities: List[Dict[str, Any]],
    planned_workout: Optional[Dict[str, Any]] = None,
) -> Union[CurrentRiskAssessment, AnalysisError]:
    """Multi-factor training risk combining ACWR, readiness, TSB, recent load."""
    ...

def api_estimate_recovery_window(
    trigger_type: str,
    current_value: float,
    safe_threshold: float,
) -> Union[RecoveryWindowEstimate, AnalysisError]:
    """Estimate recovery timeline to safe zone."""
    ...

def api_forecast_training_stress(
    weeks_ahead: int,
    current_metrics: Dict[str, Any],
    planned_weeks: List[Dict[str, Any]],
) -> Union[TrainingStressForecast, AnalysisError]:
    """Project CTL/ATL/TSB/ACWR 1-4 weeks ahead."""
    ...

def api_assess_taper_status(
    race_date: date,
    current_metrics: Dict[str, Any],
    recent_weeks: List[Dict[str, Any]],
) -> Union[TaperStatusAssessment, AnalysisError]:
    """Verify taper progression toward race day freshness."""
    ...
```

**Key Features:**
- **80/20 Validation:** Polarization scoring, compliance levels, moderate-intensity rut detection
- **Gap Detection:** CTL impact analysis, cause inference from notes (injury/illness keywords)
- **Multi-Sport Load:** Systemic + lower-body breakdown by sport, priority adherence, fatigue flags
- **Capacity Checks:** Validates planned volume against historical max, prevents untested loads
- **Risk Assessment:** Multi-factor scoring (ACWR, readiness, TSB, recent load), heuristic risk index
- **Recovery Windows:** Day-by-day checklist for returning to safe zones
- **Stress Forecasting:** Projects metrics 1-4 weeks ahead, identifies risk windows
- **Taper Verification:** Volume reduction, TSB trajectory, readiness trend tracking

---

### 3.9 Module: api/validation.py

Interval structure, plan structure, and goal feasibility validation.

```python
def api_validate_interval_structure(
    workout_type: str,
    intensity: str,
    work_bouts: List[Dict[str, Any]],
    recovery_bouts: List[Dict[str, Any]],
    weekly_volume_km: Optional[float] = None,
) -> Union[IntervalStructureValidation, ValidationError]:
    """Validate interval workout structure per Daniels methodology.

    Checks:
    - I-pace: 3-5min work bouts, equal recovery, total ≤10km or 8% weekly
    - T-pace: 5-15min work bouts, 1min recovery per 5min work, total ≤10% weekly
    - R-pace: 30-90sec work bouts, 2-3x recovery, total ≤8km or 5% weekly

    Returns:
        IntervalStructureValidation with work/recovery bout analysis, violations,
        daniels_compliance (true/false), and recommendations.
    """


def api_validate_plan_structure(
    total_weeks: int,
    goal_type: str,
    phases: Dict[str, int],
    weekly_volumes_km: List[float],
    recovery_weeks: List[int],
    race_week: Optional[int],
) -> Union[PlanStructureValidation, ValidationError]:
    """Validate training plan structure for common errors.

    Checks:
    - Phase duration appropriateness (base, build, peak, taper)
    - Volume progression (10% rule)
    - Peak placement (2-3 weeks before race; skipped for general_fitness)
    - Recovery week frequency (every 3-4 weeks)
    - Taper structure (gradual volume reduction; skipped for general_fitness)

    Returns:
        PlanStructureValidation with overall_quality_score (0-100),
        phase checks, volume checks, violations, and recommendations.
    """


def api_assess_goal_feasibility(
    goal_type: str,
    goal_time_seconds: int,
    goal_date: Union[date, str],
    current_vdot: Optional[int],
    current_ctl: float,
    vdot_for_goal: Optional[int] = None,
) -> Union[GoalFeasibilityAssessment, ValidationError]:
    """Assess goal feasibility based on VDOT and CTL.

    Analyzes:
    - Current fitness (VDOT, CTL) vs goal requirements
    - Time available vs typical training duration
    - VDOT improvement needed and realistic timeline
    - CTL buildup needed for goal distance

    Returns:
        GoalFeasibilityAssessment with feasibility_verdict
        (VERY_REALISTIC/REALISTIC/AMBITIOUS_BUT_REALISTIC/AMBITIOUS/UNREALISTIC),
        confidence_level, feasibility_analysis, recommendations, warnings.
    """
```

**Key Features:**
- **Interval Validation:** Daniels methodology compliance (I/T/R-pace work/recovery ratios, total volume limits)
- **Plan Validation:** Quality scoring (0-100), phase duration checks, volume progression safety (10% rule)
- **Goal Feasibility:** VDOT gap analysis, time sufficiency, CTL buildup needs, alternative scenarios
- **Violation Reporting:** Type, severity (LOW/MODERATE/HIGH), message, specific recommendations
- **Input Validation:** Comprehensive type checking, date parsing, boundary validation

---

## 4. Return Type Schemas

### 4.1 Enriched Data Types

All API functions return rich, self-describing types:

```python
from datetime import date
from typing import Optional
from pydantic import BaseModel


class MetricInterpretation(BaseModel):
    """A metric value with human-readable context."""
    value: float                      # Raw numeric value
    formatted: str                    # Display string ("44", "+8", "1.15")
    zone: str                         # Qualitative zone ("safe", "productive", "high_risk")
    interpretation: str               # Human-readable explanation
    trend: Optional[str] = None       # Change over time ("+2 this week")


class EnrichedMetrics(BaseModel):
    """Training metrics with interpretations."""
    date: date
    ctl: MetricInterpretation         # Chronic Training Load (fitness)
    atl: MetricInterpretation         # Acute Training Load (fatigue)
    tsb: MetricInterpretation         # Training Stress Balance (form)
    acwr: Optional[MetricInterpretation]  # Acute:Chronic Workload Ratio
    readiness: MetricInterpretation   # Overall readiness score


class WorkoutRationale(BaseModel):
    """Why a specific workout is prescribed."""
    primary_reason: str               # "Form is good"
    training_purpose: str             # "threshold work improves lactate clearance"
    phase_context: Optional[str]      # "Building aerobic foundation"
    safety_notes: list[str]           # Any warnings


class WorkoutRecommendation(BaseModel):
    """Today's workout with full context."""
    workout: "WorkoutPrescription"    # The prescription itself
    rationale: WorkoutRationale       # Why this workout today
    metrics_context: EnrichedMetrics  # Current metrics that informed decision
    pending_suggestions: list["Suggestion"]  # Any adaptations to consider
    warnings: list[str]               # Injury flags, high ACWR, etc.


class SyncResult(BaseModel):
    """Result of a successful Strava sync."""
    activities_imported: list["Activity"]
    metrics_updated: EnrichedMetrics
    suggestions_generated: list["Suggestion"]
    memories_extracted: list["Memory"]
    errors: list[str]                 # Non-fatal errors


class SyncError(BaseModel):
    """Sync operation error."""
    error_type: str                   # "auth", "rate_limit", "network", "partial"
    message: str                      # Human-readable description
    retry_after: Optional[int] = None # Seconds to wait (for rate limits)
    activities_imported: int = 0      # For partial failures
```

---

## 5. Data Access Patterns

### 5.1 Primary: API Functions

For all normal operations, Claude Code should use API functions:

```python
from sports_coach_engine.api import (
    sync_strava,
    get_todays_workout,
    get_current_metrics,
    get_weekly_status,
    accept_suggestion,
)

# Sync Strava
result = sync_strava()

# Get today's workout
workout = get_todays_workout()

# Get current metrics
metrics = get_current_metrics()
```

### 5.2 Secondary: Direct File Access

For exploration, debugging, or custom queries, direct file access is available:

```python
from sports_coach_engine.core.repository import RepositoryIO

repo = RepositoryIO()

# Read specific file
profile = repo.read_yaml("athlete/profile.yaml")

# List files
activities = repo.list_files("activities/**/*.yaml")

# Read activity
activity = repo.read_yaml("activities/2024-01/2024-01-15_run_123.yaml")
```

**When to use direct access:**

- Debugging data issues
- Custom analysis not covered by API
- Exploring historical data
- One-off queries

**When NOT to use direct access:**

- Normal coaching operations (use API)
- Modifying data (use API functions that handle validation)

---

## 6. Error Handling

### 6.1 Error Types

Functions return union types with explicit errors:

```python
def sync_strava() -> SyncResult | SyncError:
    ...

# Usage
result = sync_strava()
if isinstance(result, SyncError):
    if result.error_type == "auth":
        # Handle authentication error
        pass
    elif result.error_type == "rate_limit":
        # Wait and retry
        time.sleep(result.retry_after)
else:
    # Success
    print(f"Synced {len(result.activities_imported)} activities")
```

### 6.2 Common Errors

| Error Type   | Cause                        | Recovery                     |
| ------------ | ---------------------------- | ---------------------------- |
| `auth`       | Strava token invalid/expired | Re-authenticate              |
| `rate_limit` | API rate limit exceeded      | Wait `retry_after` seconds   |
| `network`    | Network connectivity issue   | Retry later                  |
| `partial`    | Some activities failed       | Review `activities_imported` |
| `not_found`  | Resource doesn't exist       | Check ID/path                |
| `validation` | Invalid input data           | Fix input                    |

---

## 7. Usage Examples

### 7.1 Typical Coaching Flow

```python
from sports_coach_engine.api import (
    sync_strava,
    get_todays_workout,
    get_weekly_status,
    accept_suggestion,
)

# User: "Sync my Strava"
result = sync_strava()
if isinstance(result, SyncError):
    print(f"Sync failed: {result.message}")
else:
    print(f"Synced {len(result.activities_imported)} activities")
    for activity in result.activities_imported:
        print(f"  - {activity.name}: {activity.duration_minutes}min")

# User: "What should I do today?"
workout = get_todays_workout()
print(f"Today: {workout.workout.workout_type}")
print(f"Duration: {workout.workout.duration_minutes}min")
print(f"Why: {workout.rationale.primary_reason}")

if workout.pending_suggestions:
    suggestion = workout.pending_suggestions[0]
    print(f"Suggestion: {suggestion.rationale}")
    # User: "Yes, accept"
    accept_suggestion(suggestion.id)

# User: "Show my week"
status = get_weekly_status()
print(f"Week {status.week_number} ({status.phase})")
for day in status.days:
    print(f"  {day.date}: {day.summary}")
```

### 7.2 Goal Setting Flow

```python
from datetime import date
from sports_coach_engine.api import set_goal, get_current_plan

# User: "I want to run a half marathon in March"
goal = set_goal(
    race_type="half_marathon",
    target_date=date(2024, 3, 15)
)

# Plan is automatically regenerated
plan = get_current_plan()
print(f"New {plan.total_weeks}-week plan to {goal.target_date}")
print(f"Phase 1: {plan.weeks[0].phase}")
```

---

## 8. Integration Notes

### 8.1 Internal Module Calls

API functions orchestrate internal modules:

```
api/sync.py::sync_strava()
  → core/strava.py::fetch_activities()
  → core/normalization.py::normalize_activity()
  → core/notes.py::analyze_notes()
  → core/load.py::calculate_loads()
  → core/metrics.py::compute_daily_metrics()
  → core/adaptation.py::evaluate_adaptations()
  → core/memory.py::extract_memories()
  → core/enrichment.py::enrich_sync_result()
  → return SyncResult
```

### 8.2 Claude Code Should NOT

- Import from `core/` directly for normal operations
- Call internal functions that bypass validation
- Modify files directly (use API functions)
- Assume file paths (use API functions)

### 8.3 CLAUDE.md Documentation

The CLAUDE.md file should contain a quick reference of all API functions with "When to Use" guidance. See CLAUDE.md for the definitive reference.

---

## 9. Versioning

| Version | Date       | Changes                         |
| ------- | ---------- | ------------------------------- |
| 1.0.0   | 2026-01-12 | Initial API layer specification |
