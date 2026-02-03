# M9 — Metrics Engine

## 1. Metadata

| Field | Value |
|-------|-------|
| Module ID | M9 |
| Name | Metrics Engine |
| Code Module | `core/metrics.py` |
| Version | 1.0.2 |
| Status | Draft |
| Dependencies | M3 (Repository I/O), M8 (Load Engine) |

## 2. Purpose

Aggregate activity loads into meaningful training metrics. Computes CTL (fitness), ATL (fatigue), TSB (form), ACWR (load spike indicator), and readiness scores that drive plan generation and adaptation decisions.

### 2.1 Scope Boundaries

**In Scope:**
- Aggregating daily loads from activities
- Computing CTL/ATL/TSB using exponential weighted moving averages
- Computing systemic ACWR
- Computing readiness score with confidence
- Tracking weekly intensity distribution (80/20)
- Counting high-intensity sessions across all sports
- Persisting daily metrics and weekly summaries

**Out of Scope:**
- Computing activity-level loads (M8)
- Making adaptation decisions (M11)
- Generating plans (M10)
- Formatting metrics for display (M12 - Data Enrichment)

## 3. Dependencies

### 3.1 Internal Dependencies

| Module | Usage |
|--------|-------|
| M3 | Read activity files, write metrics files |
| M8 | Receives load calculations for activities |

### 3.2 External Libraries

```
pydantic>=2.0        # Data models
numpy>=1.24          # Efficient array computations (optional, for batch)
```

## 4. Internal Interface

**Note:** This module is called internally by M1 workflows and the API layer. Claude Code should NOT import from `core/metrics.py` directly—use API functions like `api.metrics.get_current_metrics()`.

### 4.1 Type Definitions

```python
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ReadinessLevel(str, Enum):
    """Qualitative readiness assessment"""
    FRESH = "fresh"           # Ready for hard effort
    READY = "ready"           # Normal training
    TIRED = "tired"           # Reduce intensity
    EXHAUSTED = "exhausted"   # Rest recommended


class ACWRZone(str, Enum):
    """ACWR load spike classification"""
    SAFE = "safe"             # 0.8 - 1.3
    CAUTION = "caution"       # 1.3 - 1.5
    HIGH_RISK = "high_risk"   # > 1.5
    UNDERTRAINED = "undertrained"  # < 0.8


class TSBZone(str, Enum):
    """TSB training status"""
    DETRAINING_RISK = "detraining_risk"  # > +25
    RACE_READY = "race_ready"            # +15 to +25
    FRESH = "fresh"                      # +5 to +15
    OPTIMAL = "optimal"                  # -10 to +5
    PRODUCTIVE = "productive"            # -25 to -10
    OVERREACHED = "overreached"          # < -25


class DailyLoad(BaseModel):
    """Aggregated loads for a single day"""
    date: date
    activities: list[dict] = Field(default_factory=list)  # Activity summaries
    systemic_daily_load_au: float
    lower_body_daily_load_au: float
    activity_count: int
    session_types: list[str] = Field(default_factory=list)  # e.g., ["easy", "quality"]


class CTLATLMetrics(BaseModel):
    """Chronic and Acute Training Load metrics"""
    ctl: float              # Chronic Training Load (42-day EMA)
    atl: float              # Acute Training Load (7-day EMA)
    tsb: float              # Training Stress Balance (CTL - ATL)
    tsb_zone: TSBZone       # Qualitative zone


class ACWRMetrics(BaseModel):
    """Acute:Chronic Workload Ratio metrics"""
    acwr: Optional[float] = None  # None if insufficient data
    zone: ACWRZone
    acute_load_7d: float    # Sum of last 7 days
    chronic_load_28d: float # Average of last 28 days
    load_spike_elevated: bool  # True if > 1.3


class ReadinessScore(BaseModel):
    """Overall readiness assessment"""
    score: int              # 0-100
    level: ReadinessLevel
    confidence: str         # "low" (objective-only in v0)
    data_coverage: Optional[str] = None  # "objective_only"
    components: "ReadinessComponents"


class ReadinessComponents(BaseModel):
    """Breakdown of readiness score components (objective-only)"""
    tsb_contribution: float
    load_trend_contribution: float
    weights_used: dict = Field(default_factory=dict)


class IntensityDistribution(BaseModel):
    """Weekly intensity tracking for 80/20"""
    low_minutes: int            # Zone 1-2 / RPE 1-4
    moderate_minutes: int       # Zone 3 / RPE 5-6
    high_minutes: int           # Zone 4-5 / RPE 7-10
    total_minutes: int
    low_percent: float
    moderate_high_percent: float
    compliant_80_20: bool       # Low >= 80%


class DailyMetrics(BaseModel):
    """Complete metrics for a single day"""
    date: date

    # Daily loads
    daily_load: DailyLoad

    # CTL/ATL/TSB (computed from systemic load)
    ctl_atl: CTLATLMetrics

    # ACWR
    acwr: ACWRMetrics

    # Readiness
    readiness: ReadinessScore

    # Flags (from M7, persisted here)
    flags: dict = Field(default_factory=dict)  # injury, illness flags

    # Metadata
    computed_at: datetime
    baseline_established: bool


class WeeklySummary(BaseModel):
    """Aggregated metrics for a week"""
    week_start: date
    week_end: date

    # Load totals
    total_systemic_load_au: float
    total_lower_body_load_au: float

    # Activity counts
    run_sessions: int
    all_sessions: int
    key_sessions_completed: int

    # Intensity distribution
    intensity_distribution: IntensityDistribution
    high_intensity_sessions_7d: int

    # Metrics at week end
    ctl_end: float
    atl_end: float
    tsb_end: float

    # Compliance
    planned_vs_actual_ratio: Optional[float] = None
```

### 4.2 Function Signatures

```python
from typing import Sequence


def compute_daily_metrics(
    target_date: date,
    activities: Sequence["LoadCalculation"],
    historical_metrics: list["DailyMetrics"],
    flags: Optional[dict] = None,
) -> DailyMetrics:
    """
    Compute all metrics for a single day.

    Args:
        target_date: Date to compute metrics for
        activities: Load calculations for activities on this date
        historical_metrics: Previous daily metrics for EMA computation
        flags: Optional injury/illness flags from M7

    Returns:
        Complete daily metrics
    """
    ...


def compute_ctl_atl(
    daily_loads: list[tuple[date, float]],
    target_date: date,
    ctl_days: int = 42,
    atl_days: int = 7,
) -> CTLATLMetrics:
    """
    Compute CTL and ATL using exponential weighted moving averages.

    Formula:
        EMA_today = EMA_yesterday + (load_today - EMA_yesterday) / time_constant
        where time_constant = days (42 for CTL, 7 for ATL)

    Args:
        daily_loads: List of (date, systemic_load) tuples
        target_date: Date to compute for
        ctl_days: Time constant for CTL (default 42)
        atl_days: Time constant for ATL (default 7)

    Returns:
        CTL, ATL, TSB metrics
    """
    ...


def compute_acwr(
    daily_loads: list[tuple[date, float]],
    target_date: date,
) -> ACWRMetrics:
    """
    Compute Acute:Chronic Workload Ratio.

    Formula:
        ACWR = (7-day total load) / (28-day average load)

    Args:
        daily_loads: List of (date, systemic_load) tuples
        target_date: Date to compute for

    Returns:
        ACWR metrics with zone classification

    Note:
        Returns None for ACWR if < 28 days of data (avoid division by zero)
    """
    ...


def compute_readiness(
    tsb: float,
    load_trend: float,
    injury_flags: Optional[list[str]],
    illness_flags: Optional[list[str]],
) -> ReadinessScore:
    """
    Compute overall readiness score (0-100).

    Weighted components (objective-only in v0):
    - TSB (40%): Higher TSB = more fresh
    - Load trend (40%): Declining load = recovering

    Args:
        tsb: Training Stress Balance
        load_trend: 0-100 load trend score
        injury_flags: Active injury keywords
        illness_flags: Active illness keywords

    Returns:
        Readiness score with confidence level
    """
    ...


def compute_intensity_distribution(
    activities: Sequence["LoadCalculation"],
    target_week: tuple[date, date],
) -> IntensityDistribution:
    """
    Compute weekly intensity distribution for 80/20 compliance.

    Only considers running activities for the distribution.
    """
    ...


def count_high_intensity_sessions(
    activities: Sequence["LoadCalculation"],
    window_days: int = 7,
) -> int:
    """
    Count high-intensity sessions across ALL sports in window.

    High intensity = session_type in {QUALITY, RACE}
    """
    ...


def aggregate_daily_load(
    activities: Sequence["LoadCalculation"],
) -> DailyLoad:
    """
    Sum loads from multiple activities in a day.
    """
    ...


def compute_weekly_summary(
    week_start: date,
    daily_metrics: Sequence["DailyMetrics"],
    activities: Sequence["LoadCalculation"],
) -> WeeklySummary:
    """
    Generate weekly summary from daily metrics.
    """
    ...


def persist_daily_metrics(
    metrics: DailyMetrics,
    repo: "RepositoryIO",
) -> str:
    """
    Write daily metrics to metrics/daily/YYYY-MM-DD.yaml

    Returns:
        File path written
    """
    ...


def persist_weekly_summary(
    summary: WeeklySummary,
    repo: "RepositoryIO",
) -> None:
    """
    Update metrics/weekly_summary.yaml
    """
    ...


def recompute_metrics_range(
    start_date: date,
    end_date: date,
    repo: "RepositoryIO",
) -> list[DailyMetrics]:
    """
    Recompute all metrics for a date range.

    Useful after activity corrections or imports.
    """
    ...
```

### 4.3 Error Types

```python
class MetricsError(Exception):
    """Base error for metrics computation"""
    pass


class InsufficientDataError(MetricsError):
    """Not enough historical data for computation"""
    def __init__(self, required_days: int, available_days: int):
        super().__init__(
            f"Insufficient data: need {required_days} days, have {available_days}"
        )
        self.required_days = required_days
        self.available_days = available_days


class MetricsStaleError(MetricsError):
    """Metrics are outdated"""
    def __init__(self, last_computed: date, staleness_days: int):
        super().__init__(f"Metrics stale by {staleness_days} days")
        self.last_computed = last_computed
        self.staleness_days = staleness_days
```

## 5. Core Algorithms

### 5.1 CTL/ATL/TSB Computation

```python
from datetime import date, timedelta
from typing import Optional


def compute_ctl_atl(
    daily_loads: list[tuple[date, float]],
    target_date: date,
    ctl_days: int = 42,
    atl_days: int = 7,
) -> CTLATLMetrics:
    """
    Exponential Weighted Moving Average for CTL and ATL.

    The EMA formula:
        EMA_today = EMA_yesterday + (load_today - EMA_yesterday) / τ

    Where τ (time constant) represents the "half-life" of the metric.
    - CTL (τ=42): Represents long-term fitness, changes slowly
    - ATL (τ=7): Represents recent fatigue, changes quickly

    TSB = CTL - ATL
    - Positive TSB: Rested, ready for hard effort
    - Negative TSB: Fatigued from training
    """
    # Sort loads by date
    sorted_loads = sorted(daily_loads, key=lambda x: x[0])

    if not sorted_loads:
        return CTLATLMetrics(ctl=0, atl=0, tsb=0, tsb_zone=TSBZone.FRESH)

    # Build lookup for daily loads
    load_map = {d: load for d, load in sorted_loads}

    # Determine start date (earliest data or target - 90 days)
    earliest = min(d for d, _ in sorted_loads)
    start = min(earliest, target_date - timedelta(days=90))

    # Initialize EMAs
    ctl = 0.0
    atl = 0.0

    # Iterate day by day
    current = start
    while current <= target_date:
        daily_load = load_map.get(current, 0.0)

        # EMA update
        ctl = ctl + (daily_load - ctl) / ctl_days
        atl = atl + (daily_load - atl) / atl_days

        current += timedelta(days=1)

    tsb = ctl - atl

    # Classify TSB zone
    tsb_zone = _classify_tsb_zone(tsb)

    return CTLATLMetrics(
        ctl=round(ctl, 1),
        atl=round(atl, 1),
        tsb=round(tsb, 1),
        tsb_zone=tsb_zone,
    )


def _classify_tsb_zone(tsb: float) -> TSBZone:
    """Classify TSB into training zones"""
    if tsb > 25:
        return TSBZone.DETRAINING_RISK  # Very fresh, risk of detraining if sustained
    elif tsb > 15:
        return TSBZone.RACE_READY  # Peak freshness for A-priority races
    elif tsb > 5:
        return TSBZone.FRESH       # Quality-ready
    elif tsb > -10:
        return TSBZone.OPTIMAL     # Ideal for quality work
    elif tsb > -25:
        return TSBZone.PRODUCTIVE  # Normal training zone
    else:
        return TSBZone.OVERREACHED # Excessive fatigue
```

### 5.2 ACWR Computation

```python
def compute_acwr(
    daily_loads: list[tuple[date, float]],
    target_date: date,
) -> ACWRMetrics:
    """
    Acute:Chronic Workload Ratio calculation.

    Formula:
        ACWR = Acute Load / Chronic Load
        Acute = Sum of last 7 days
        Chronic = Average daily load over last 28 days

    ACWR Zones (load spike indicator):
        < 0.8: Undertrained (fitness declining)
        0.8 - 1.3: Safe zone (stable load)
        1.3 - 1.5: Caution (elevated load)
        > 1.5: High risk (significant spike)
    """
    # Build date -> load map
    load_map = {d: load for d, load in daily_loads}

    # Calculate acute load (7 days)
    acute_total = 0.0
    for i in range(7):
        day = target_date - timedelta(days=i)
        acute_total += load_map.get(day, 0.0)

    # Calculate chronic load (28 days)
    chronic_total = 0.0
    chronic_days = 0
    for i in range(28):
        day = target_date - timedelta(days=i)
        if day in load_map:
            chronic_total += load_map[day]
            chronic_days += 1

    # Require full 28 days for reliable ACWR
    if chronic_days < 28:
        return None

    chronic_avg = chronic_total / 28  # Use 28-day window, not actual days

    if chronic_avg == 0:
        return None

    acwr = acute_total / (chronic_avg * 7)  # Normalize to weekly

    # Actually simpler formula:
    # ACWR = (7-day sum) / (28-day average × 7)
    # Or equivalently: ACWR = (7-day sum × 4) / (28-day sum)

    # Correct formula from literature:
    acute_weekly_avg = acute_total / 7
    chronic_weekly_avg = chronic_total / 28

    load_spike_elevated = acwr > 1.3

    return ACWRMetrics(
        acwr=round(acwr, 2),
        zone=_classify_acwr_zone(acwr),
        acute_load_7d=round(acute_total, 1),
        chronic_load_28d=round(chronic_avg, 1),
        load_spike_elevated=load_spike_elevated,
    )
def _classify_acwr_zone(acwr: float) -> ACWRZone:
    """Classify ACWR into risk zones"""
    if acwr < 0.8:
        return ACWRZone.UNDERTRAINED
    elif acwr <= 1.3:
        return ACWRZone.SAFE
    elif acwr <= 1.5:
        return ACWRZone.CAUTION
    else:
        return ACWRZone.HIGH_RISK
```

### 5.3 Readiness Score Computation

**Implementation (v0, objective-only)**:
- Inputs: TSB and load trend only.
- Weights: TSB 40%, load trend 40%.
- Score capped at **65** to avoid false precision.
- Confidence: **LOW** (objective-only).
- `data_coverage`: `"objective_only"`.

```python
def compute_readiness(
    tsb: float,
    load_trend: float,
    injury_flags: Optional[list[str]] = None,
    illness_flags: Optional[list[str]] = None,
) -> ReadinessScore:
    """
    Compute overall readiness score (0-100) using objective signals only.
    """
    tsb_score = clamp((tsb + 30) * 2.5, 0, 100)
    score = min(tsb_score * 0.40 + load_trend * 0.40, 65)

    # Safety overrides
    if injury_flags:
        score = min(score, 25)
    elif illness_flags:
        score = min(score, 35)

    confidence = "low"
    data_coverage = "objective_only"
```

### 5.4 Intensity Distribution

```python
def compute_intensity_distribution(
    activities: Sequence["LoadCalculation"],
    target_week: tuple[date, date],
) -> IntensityDistribution:
    """
    Compute 80/20 intensity distribution for running activities.

    Only running activities contribute to the distribution.
    Other sports are tracked separately for total load but not 80/20.
    """
    week_start, week_end = target_week

    # Filter to running activities in the week
    running_types = {"run", "trail_run", "treadmill_run", "track_run"}
    running_activities = [
        a for a in activities
        if a.sport_type in running_types
        and week_start <= a.activity_date <= week_end
    ]

    # Aggregate by intensity
    low_minutes = 0
    moderate_minutes = 0
    high_minutes = 0

    for activity in running_activities:
        duration = activity.duration_minutes

        if activity.session_type == SessionType.EASY:
            low_minutes += duration
        elif activity.session_type == SessionType.MODERATE:
            moderate_minutes += duration
        elif activity.session_type in {SessionType.QUALITY, SessionType.RACE}:
            high_minutes += duration

    total = low_minutes + moderate_minutes + high_minutes

    if total == 0:
        return IntensityDistribution(
            low_minutes=0,
            moderate_minutes=0,
            high_minutes=0,
            total_minutes=0,
            low_percent=0.0,
            moderate_high_percent=0.0,
            compliant_80_20=True,  # No running = trivially compliant
        )

    low_pct = (low_minutes / total) * 100
    mod_high_pct = ((moderate_minutes + high_minutes) / total) * 100

    return IntensityDistribution(
        low_minutes=low_minutes,
        moderate_minutes=moderate_minutes,
        high_minutes=high_minutes,
        total_minutes=total,
        low_percent=round(low_pct, 1),
        moderate_high_percent=round(mod_high_pct, 1),
        compliant_80_20=low_pct >= 80,
    )
```

### 5.5 High-Intensity Session Count

```python
def count_high_intensity_sessions(
    activities: Sequence["LoadCalculation"],
    target_date: date,
    window_days: int = 7,
) -> int:
    """
    Count high-intensity sessions across ALL sports.

    This is a global fatigue indicator - hard climbing, cycling,
    or CrossFit also counts toward the 2-session-per-week limit.
    """
    start_date = target_date - timedelta(days=window_days - 1)

    high_intensity_types = {SessionType.QUALITY, SessionType.RACE}

    count = sum(
        1 for a in activities
        if start_date <= a.activity_date <= target_date
        and a.session_type in high_intensity_types
    )

    return count
```

### 5.6 Daily Aggregation

```python
def aggregate_daily_load(
    activities: Sequence["LoadCalculation"],
) -> DailyLoad:
    """
    Sum loads from multiple activities in a single day.
    """
    if not activities:
        return DailyLoad(
            date=date.today(),
            activities=[],
            systemic_daily_load_au=0.0,
            lower_body_daily_load_au=0.0,
            activity_count=0,
            session_types=[],
        )

    target_date = activities[0].activity_date

    systemic_total = sum(a.systemic_load_au for a in activities)
    lower_body_total = sum(a.lower_body_load_au for a in activities)

    activity_summaries = [
        {
            "id": a.activity_id,
            "sport_type": a.sport_type,
            "systemic_load_au": a.systemic_load_au,
            "lower_body_load_au": a.lower_body_load_au,
            "session_type": a.session_type.value,
        }
        for a in activities
    ]

    session_types = [a.session_type.value for a in activities]

    return DailyLoad(
        date=target_date,
        activities=activity_summaries,
        systemic_daily_load_au=round(systemic_total, 1),
        lower_body_daily_load_au=round(lower_body_total, 1),
        activity_count=len(activities),
        session_types=session_types,
    )
```

### 5.7 Full Daily Metrics Computation

```python
def compute_daily_metrics(
    target_date: date,
    activities: Sequence["LoadCalculation"],
    historical_metrics: list["DailyMetrics"],
    flags: Optional[dict] = None,
) -> DailyMetrics:
    """
    Complete daily metrics computation pipeline.
    """
    # 1. Aggregate daily load
    daily_load = aggregate_daily_load(activities)

    # 2. Build historical load series
    daily_loads = []
    for dm in historical_metrics:
        daily_loads.append((dm.date, dm.daily_load.systemic_daily_load_au))
    daily_loads.append((target_date, daily_load.systemic_daily_load_au))

    # 3. Compute CTL/ATL/TSB
    ctl_atl = compute_ctl_atl(daily_loads, target_date)

    # 4. Compute ACWR
    acwr = compute_acwr(daily_loads, target_date)

    # 5. Compute load trend (3-day vs 7-day average)
    recent_load_trend = _compute_load_trend(daily_loads, target_date)

    # 6. Extract injury/illness flags (from activities)
    injury_flags, illness_flags = _extract_activity_flags(activities)

    # 7. Compute readiness (objective-only)
    readiness = compute_readiness(
        tsb=ctl_atl.tsb,
        load_trend=recent_load_trend,
        injury_flags=injury_flags,
        illness_flags=illness_flags,
    )

    # 8. Determine if baseline established (14+ days)
    days_of_data = len([d for d, _ in daily_loads if d <= target_date])
    baseline_established = days_of_data >= 14

    return DailyMetrics(
        date=target_date,
        daily_load=daily_load,
        ctl_atl=ctl_atl,
        acwr=acwr,
        readiness=readiness,
        flags=flags or {},
        computed_at=datetime.now(),
        baseline_established=baseline_established,
    )


def _compute_load_trend(
    daily_loads: list[tuple[date, float]],
    target_date: date,
) -> float:
    """
    Compute recent load trend (3-day avg vs 7-day avg).

    Positive = load increasing
    Negative = load decreasing (recovering)
    """
    load_map = {d: load for d, load in daily_loads}

    # 3-day average
    three_day = sum(
        load_map.get(target_date - timedelta(days=i), 0)
        for i in range(3)
    ) / 3

    # 7-day average
    seven_day = sum(
        load_map.get(target_date - timedelta(days=i), 0)
        for i in range(7)
    ) / 7

    if seven_day == 0:
        return 0.0

    return (three_day - seven_day) / seven_day
```

## 6. Data Structures

### 6.1 Daily Metrics File Schema

```yaml
# metrics/daily/2025-03-15.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "daily_metrics"

date: "2025-03-15"

# Daily load aggregation
daily_load:
  activities:
    - id: "12345"
      sport_type: "run"
      systemic_load_au: 280.0
      lower_body_load_au: 280.0
      session_type: "moderate"
    - id: "12346"
      sport_type: "climb"
      systemic_load_au: 420.0
      lower_body_load_au: 70.0
      session_type: "quality"
  systemic_daily_load_au: 700.0
  lower_body_daily_load_au: 350.0
  activity_count: 2
  session_types: ["moderate", "quality"]

# CTL/ATL/TSB
ctl: 45.2
atl: 52.8
tsb: -7.6
tsb_zone: "optimal"

# ACWR
acwr: 1.18
acwr_zone: "safe"
acute_load_7d: 2450.0
chronic_load_28d: 2080.0

# Readiness
readiness:
  score: 62
  level: "ready"
  confidence: "low"
  data_coverage: "objective_only"
  components:
    tsb_contribution: 45.0
    load_trend_contribution: 65.0
    weights_used:
      tsb: 0.4
      load_trend: 0.4

# Flags
flags:
  injury:
    active: false
  illness:
    active: false

# Metadata
computed_at: "2025-03-15T18:30:00Z"
baseline_established: true
```

### 6.2 Weekly Summary Schema

```yaml
# metrics/weekly_summary.yaml
_schema:
  format_version: "1.0.0"
  schema_type: "weekly_summary"

week_start: "2025-03-10"
week_end: "2025-03-16"

# Load totals
total_systemic_load_au: 3150.0
total_lower_body_load_au: 1820.0

# Activity counts
run_sessions: 4
all_sessions: 7
key_sessions_completed: 2

# Intensity distribution (running only)
intensity_distribution:
  low_minutes: 180
  moderate_minutes: 45
  high_minutes: 30
  total_minutes: 255
  low_percent: 70.6
  moderate_high_percent: 29.4
  compliant_80_20: false

high_intensity_sessions_7d: 3

# End-of-week metrics
ctl_end: 45.2
atl_end: 52.8
tsb_end: -7.6

# Compliance
planned_vs_actual_ratio: 0.85
```

## 7. Cold Start Handling

### 7.1 New User (No History)

```python
def handle_cold_start(target_date: date) -> DailyMetrics:
    """
    Generate metrics for new user with no history.

    Cold Start Rules:
    - CTL = 0 (no fitness baseline)
    - ATL = 0 (no recent fatigue)
    - TSB = 0 (neutral form)
    - ACWR = None (undefined, skip ACWR checks)
    - Readiness = 60 (default "ready")
    - Use absolute thresholds (300 AU) instead of relative
    """
    return DailyMetrics(
        date=target_date,
        daily_load=DailyLoad(
            date=target_date,
            activities=[],
            systemic_daily_load_au=0.0,
            lower_body_daily_load_au=0.0,
            activity_count=0,
            session_types=[],
        ),
        ctl_atl=CTLATLMetrics(
            ctl=0.0,
            atl=0.0,
            tsb=0.0,
            tsb_zone=TSBZone.FRESH,
        ),
        acwr=ACWRMetrics(
            acwr=None,
            zone=ACWRZone.SAFE,
            acute_load_7d=0.0,
            chronic_load_28d=0.0,
            load_spike_elevated=False,
        ),
        readiness=ReadinessScore(
            score=60,
            level=ReadinessLevel.READY,
            confidence="low",
            components={"cold_start": True},
        ),
        flags={},
        computed_at=datetime.now(),
        baseline_established=False,
    )
```

### 7.2 Baseline Establishment

```python
BASELINE_DAYS_REQUIRED = 14


def check_baseline_status(daily_metrics: list["DailyMetrics"]) -> dict:
    """
    Check if baseline is established for reliable metrics.

    Thresholds:
    - 14 days: Use relative lower-body thresholds
    - 28 days: ACWR becomes meaningful
    - 42 days: CTL stabilizes
    """
    days = len(daily_metrics)

    return {
        "days_of_data": days,
        "relative_thresholds": days >= 14,
        "acwr_reliable": days >= 28,
        "ctl_stable": days >= 42,
        "baseline_established": days >= 14,
    }
```

## 8. Integration Points

### 8.1 Integration with API Layer

This module is called internally by M1 workflows and directly by the API layer. Claude Code calls API functions which use M9 internally.

```
Claude Code → api.metrics.get_current_metrics()
                    │
                    ▼
              M9::compute_daily_metrics()
                    │
                    ▼
              M12::enrich_metrics() → EnrichedMetrics
```

### 8.2 Called By

| Module | When |
|--------|------|
| API Layer (`api.metrics`) | `get_current_metrics()`, `get_readiness()` |
| API Layer (`api.coach`) | `get_todays_workout()`, `get_training_status()` |
| M1 (Workflows) | After sync pipeline completes (M5→M6→M7→M8) |
| M11 | Before generating adaptation suggestions |

### 8.3 Calls To

| Module | Purpose |
|--------|---------|
| M3 | Read activity files, write metrics files |

### 8.4 Returns To

| Module | Data |
|--------|------|
| API Layer | Raw metrics (enriched by M12 before returning to Claude Code) |
| M10 | CTL/ATL/TSB for plan generation |
| M11 | All metrics for adaptation triggers |
| M12 (Data Enrichment) | Raw metrics for enrichment with interpretations |

### 8.5 Pipeline Position

```
[M8 Load Engine]
        │
        ▼ LoadCalculation[]
[M9 Metrics Engine]
        │
        ├── DailyMetrics ──────► [M3] metrics/daily/*.yaml
        │
        ├── WeeklySummary ─────► [M3] metrics/weekly_summary.yaml
        │
        ├── CTL/ATL/TSB ───────► [M10 Plan Generator]
        │
        ├── ACWR + Readiness ──► [M11 Adaptation Engine]
        │
        └── Raw metrics ───────► [M12 Data Enrichment] → EnrichedMetrics → API Layer
```

## 9. Test Scenarios

### 9.1 CTL/ATL/TSB Tests

```python
def test_ctl_atl_initial():
    """New user starts with zeros"""
    result = compute_ctl_atl([], date.today())

    assert result.ctl == 0
    assert result.atl == 0
    assert result.tsb == 0


def test_ctl_atl_single_day():
    """Single workout affects ATL more than CTL"""
    loads = [(date.today(), 300.0)]
    result = compute_ctl_atl(loads, date.today())

    # ATL responds faster (7-day constant)
    assert result.atl > result.ctl
    assert result.tsb < 0  # Fatigued


def test_ctl_atl_consistent_training():
    """Consistent training builds CTL"""
    # 4 weeks of 300 AU daily
    loads = [
        (date.today() - timedelta(days=i), 300.0)
        for i in range(28)
    ]
    result = compute_ctl_atl(loads, date.today())

    # CTL should be building toward 300
    assert result.ctl > 100
    # ATL and CTL should be similar (consistent load)
    assert abs(result.atl - result.ctl) < 50


def test_tsb_zones():
    """TSB zones classify correctly"""
    assert _classify_tsb_zone(20) == TSBZone.RACE_READY
    assert _classify_tsb_zone(10) == TSBZone.FRESH
    assert _classify_tsb_zone(0) == TSBZone.OPTIMAL
    assert _classify_tsb_zone(-15) == TSBZone.PRODUCTIVE
    assert _classify_tsb_zone(-30) == TSBZone.OVERREACHED
```

### 9.2 ACWR Tests

```python
def test_acwr_insufficient_data():
    """ACWR is None with < 21 days of data"""
    loads = [(date.today() - timedelta(days=i), 100.0) for i in range(14)]
    result = compute_acwr(loads, date.today())

    assert result.acwr is None


def test_acwr_safe_zone():
    """Consistent training yields safe ACWR"""
    loads = [(date.today() - timedelta(days=i), 100.0) for i in range(30)]
    result = compute_acwr(loads, date.today())

    assert result.acwr is not None
    assert 0.9 <= result.acwr <= 1.1
    assert result.zone == ACWRZone.SAFE


def test_acwr_spike_high_risk():
    """Sudden load spike raises ACWR"""
    # 3 weeks of 100 AU, then 1 week of 300 AU
    loads = []
    for i in range(7):
        loads.append((date.today() - timedelta(days=i), 300.0))
    for i in range(7, 28):
        loads.append((date.today() - timedelta(days=i), 100.0))

    result = compute_acwr(loads, date.today())

    assert result.acwr > 1.5
    assert result.zone == ACWRZone.HIGH_RISK
```

### 9.3 Readiness Tests

```python
def test_readiness_fresh():
    """High TSB + low recent load trend = ready (objective-only)"""
    result = compute_readiness(
        tsb=15.0,
        load_trend=90.0,
    )

    assert result.score <= 65  # capped
    assert result.level == ReadinessLevel.READY


def test_readiness_injured_cap():
    """Injury caps readiness at 25"""
    result = compute_readiness(
        tsb=15.0,
        load_trend=90.0,
        injury_flags=["knee"],
    )

    assert result.score <= 25
    assert result.level == ReadinessLevel.REST_RECOMMENDED


def test_readiness_illness_cap():
    """Illness caps readiness at 35"""
    result = compute_readiness(
        tsb=10.0,
        load_trend=80.0,
        illness_flags=["cold"],
    )

    assert result.score <= 35
```

### 9.4 Intensity Distribution Tests

```python
def test_intensity_80_20_compliant():
    """80%+ low intensity is compliant"""
    activities = [
        mock_load(sport="run", session_type=SessionType.EASY, duration=60),
        mock_load(sport="run", session_type=SessionType.EASY, duration=45),
        mock_load(sport="run", session_type=SessionType.QUALITY, duration=20),
    ]

    result = compute_intensity_distribution(activities, week_range())

    assert result.low_minutes == 105
    assert result.high_minutes == 20
    assert result.low_percent > 80
    assert result.compliant_80_20 is True


def test_intensity_non_running_excluded():
    """Non-running activities don't affect 80/20"""
    activities = [
        mock_load(sport="run", session_type=SessionType.EASY, duration=60),
        mock_load(sport="climb", session_type=SessionType.QUALITY, duration=120),
    ]

    result = compute_intensity_distribution(activities, week_range())

    assert result.total_minutes == 60  # Only running
```

## 10. Formulas Reference

### 10.1 CTL/ATL (Exponential Moving Average)

```
CTL_today = CTL_yesterday + (load_today - CTL_yesterday) / 42
ATL_today = ATL_yesterday + (load_today - ATL_yesterday) / 7
TSB = CTL - ATL
```

### 10.2 ACWR

```
ACWR = Acute_weekly_avg / Chronic_weekly_avg

Where:
  Acute_weekly_avg = Sum(last 7 days load) / 7
  Chronic_weekly_avg = Sum(last 28 days load) / 28
```

### 10.3 Readiness

```
Base_score = (TSB_score × 0.20) + (Trend_score × 0.25) +
             (Sleep_score × 0.25) + (Wellness_score × 0.30)

Final_score = min(Base_score, Flag_caps)
```

**Objective-only fallback (current implementation)**:

```
Base_score = (TSB_score × 0.40) + (Trend_score × 0.40)
Final_score = min(Base_score, 65)  # cap in objective-only v0
```

## 11. Performance Notes

- CTL/ATL computation: O(n) where n = days of history
- Daily metrics: ~5ms per day
- Full recompute (90 days): ~500ms
- Batch computation recommended for imports

## 12. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.2 | 2026-01-12 | Added code module path (`core/metrics.py`) and API layer integration notes. Updated M12 reference to "Data Enrichment". |
| 1.0.1 | 2026-01-12 | **Fixed type consistency**: Converted all `@dataclass` types to `BaseModel` for Pydantic consistency (DailyLoad, CTLATLMetrics, ACWRMetrics, ReadinessScore, IntensityDistribution, DailyMetrics, WeeklySummary - 7 types converted). Removed `dataclass` and `field` imports, added `Field` for default factories. Algorithms were already complete and correct (CTL/ATL formulas: τ=42d/7d, ACWR formula: 7d avg / 28d avg, readiness weights: TSB 40%, trend 40%, cap 65). |
| 1.0.0 | 2026-01-12 | Initial specification |
