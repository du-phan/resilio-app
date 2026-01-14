"""
M9 - Metrics Engine

Compute training metrics from activity loads:
- CTL/ATL/TSB (Chronic/Acute Training Load, Training Stress Balance)
- ACWR (Acute:Chronic Workload Ratio for injury risk assessment)
- Readiness scores with confidence levels
- Weekly intensity distribution for 80/20 tracking

This module aggregates daily activity loads (from M8 Load Engine) and
computes exponentially weighted moving averages to track fitness, fatigue,
and form. These metrics drive adaptive coaching decisions in M11.

The two-channel load model (systemic + lower-body) ensures multi-sport
athletes receive appropriate running recommendations without false constraints
from unrelated activities like climbing or upper-body work.
"""

from typing import Optional
from datetime import date, datetime, timedelta

from sports_coach_engine.core.paths import (
    activities_month_dir,
    daily_metrics_path,
    weekly_metrics_summary_path,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.activity import (
    NormalizedActivity,
    SessionType,
    SportType,
)
from sports_coach_engine.schemas.metrics import (
    DailyMetrics,
    DailyLoad,
    CTLATLMetrics,
    ACWRMetrics,
    ReadinessScore,
    ReadinessComponents,
    IntensityDistribution,
    WeeklySummary,
    TSBZone,
    ACWRZone,
    ReadinessLevel,
    ConfidenceLevel,
    CTLZone,
)


# ============================================================
# ERROR TYPES
# ============================================================


class MetricsCalculationError(Exception):
    """Base exception for metrics calculation errors."""

    pass


class InsufficientDataError(MetricsCalculationError):
    """Not enough historical data to compute metrics."""

    pass


class InvalidMetricsInputError(MetricsCalculationError):
    """Input data is invalid or missing required fields."""

    pass


# ============================================================
# CONSTANTS
# ============================================================

# EWMA decay constants
CTL_DECAY = 0.976  # 42-day time constant: 1 - (1/42) ≈ 0.976
ATL_DECAY = 1 - (1/7)  # 0.8571 - 7-day time constant (standard EWMA)
CTL_ALPHA = 1 - CTL_DECAY  # 0.024
ATL_ALPHA = 1 - ATL_DECAY  # 0.1429 (1/7)

# Data sufficiency thresholds
BASELINE_DAYS_THRESHOLD = 14  # Days before baseline_established = True
ACWR_MINIMUM_DAYS = 28  # Minimum days before ACWR can be calculated

# Readiness component weights (default)
READINESS_WEIGHTS_DEFAULT = {
    "tsb": 0.20,
    "load_trend": 0.25,
    "sleep": 0.25,
    "wellness": 0.30,
}

# Readiness weights when subjective data missing
READINESS_WEIGHTS_OBJECTIVE_ONLY = {
    "tsb": 0.30,
    "load_trend": 0.35,
    "sleep": 0.0,
    "wellness": 0.0,
}

# Running sport types (for intensity distribution)
RUNNING_SPORT_TYPES = {
    SportType.RUN,
    SportType.TRAIL_RUN,
    SportType.TREADMILL_RUN,
    SportType.TRACK_RUN,
}


# ============================================================
# MAIN FUNCTIONS
# ============================================================


def estimate_baseline_ctl_atl(
    target_date: date,
    repo: RepositoryIO,
    lookback_days: int = 14
) -> tuple[float, float]:
    """
    Estimate baseline CTL/ATL from historical data to avoid cold start.

    Uses first `lookback_days` of data to calculate average daily load,
    then assumes athlete was at steady-state fitness before data collection.

    At steady state: CTL = ATL = average daily load (mathematically proven)

    This prevents the cold start problem where CTL starts at 0 and takes
    42+ days to stabilize, causing metrics to depend on sync window start date.

    Args:
        target_date: Date to estimate baseline for (typically first day of data)
        repo: Repository I/O instance
        lookback_days: Days to average (default 14, minimum 7)

    Returns:
        Tuple of (estimated_ctl, estimated_atl)

    Example:
        If athlete averaged 60 TSS/day for first 14 days,
        estimate initial CTL = 60, ATL = 60 (steady state)
    """
    # Read next lookback_days of data (forward from target_date)
    daily_loads = []
    for i in range(lookback_days):
        check_date = target_date + timedelta(days=i)
        day_load = aggregate_daily_load(check_date, repo)
        daily_loads.append(day_load.systemic_load_au)

    # Calculate average
    if not daily_loads:
        return 0.0, 0.0  # No data, use zero baseline

    avg_daily_load = sum(daily_loads) / len(daily_loads)

    # At steady state, CTL = ATL = average daily load
    # This is mathematically exact for EWMA at equilibrium
    estimated_ctl = avg_daily_load
    estimated_atl = avg_daily_load

    return round(estimated_ctl, 1), round(estimated_atl, 1)


def compute_daily_metrics(
    target_date: date,
    repo: RepositoryIO,
) -> DailyMetrics:
    """
    Compute daily metrics for a specific date.

    This is the primary entry point for M9. It:
    1. Aggregates daily load from activity files
    2. Computes CTL/ATL/TSB using EWMA from previous day
    3. Computes ACWR if >= 28 days of data
    4. Computes readiness score with available inputs
    5. Persists result to metrics/daily/YYYY-MM-DD.yaml

    Args:
        target_date: Date to compute metrics for
        repo: Repository I/O instance

    Returns:
        DailyMetrics with all computed values

    Raises:
        InvalidMetricsInputError: If inputs are invalid
        MetricsCalculationError: If computation fails
    """
    # Step 1: Aggregate daily load
    daily_load = aggregate_daily_load(target_date, repo)

    # Step 2: Get previous day's metrics for CTL/ATL baseline
    prev_date = target_date - timedelta(days=1)
    prev_metrics = _read_previous_metrics(prev_date, repo)

    if prev_metrics:
        # Continue EWMA chain from previous day
        previous_ctl = prev_metrics.ctl_atl.ctl
        previous_atl = prev_metrics.ctl_atl.atl
    else:
        # Cold start: estimate baseline from upcoming 14 days
        # This prevents CTL starting at 0 and taking 42 days to stabilize
        previous_ctl, previous_atl = estimate_baseline_ctl_atl(target_date, repo)

    # Step 3: Calculate CTL/ATL/TSB
    ctl_atl = calculate_ctl_atl(
        daily_load.systemic_load_au,
        previous_ctl,
        previous_atl,
        repo,
        target_date,
    )

    # Step 4: Calculate ACWR (if >= 28 days data)
    acwr = calculate_acwr(target_date, repo)
    acwr_available = acwr is not None

    # Step 5: Compute readiness score
    load_trend = compute_load_trend(target_date, repo)
    data_days = _count_historical_days(target_date, repo)

    # Extract flags from activities (if any)
    injury_flags = []
    illness_flags = []
    flags_list = []
    # TODO: Extract actual flags from activities when M7 integration is complete

    readiness = compute_readiness(
        tsb=ctl_atl.tsb,
        load_trend=load_trend,
        sleep_quality=None,  # TODO: Extract from activity notes
        wellness_score=None,  # TODO: Extract from activity notes
        injury_flags=injury_flags,
        illness_flags=illness_flags,
        acwr_available=acwr_available,
        data_days=data_days,
    )

    # Step 6: Build DailyMetrics object
    baseline_established = data_days >= BASELINE_DAYS_THRESHOLD

    # Determine initialization method for transparency
    if prev_metrics:
        ctl_init_method = "chained"
        estimated_days = None
    elif previous_ctl > 0:
        ctl_init_method = "estimated"
        estimated_days = 14
    else:
        ctl_init_method = "zero_start"
        estimated_days = None

    daily_metrics = DailyMetrics(
        date=target_date,
        calculated_at=datetime.now(),
        daily_load=daily_load,
        ctl_atl=ctl_atl,
        acwr=acwr,
        readiness=readiness,
        baseline_established=baseline_established,
        acwr_available=acwr_available,
        data_days_available=data_days,
        ctl_initialization_method=ctl_init_method,
        estimated_baseline_days=estimated_days,
        flags=flags_list,
    )

    # Step 7: Persist to disk
    metrics_path = daily_metrics_path(target_date)
    result = repo.write_yaml(metrics_path, daily_metrics)

    if result is not None:
        raise MetricsCalculationError(
            f"Failed to write daily metrics: {result.message}"
        )

    return daily_metrics


def compute_weekly_summary(
    week_start: date,
    repo: RepositoryIO,
) -> WeeklySummary:
    """
    Compute weekly summary for a 7-day period.

    Aggregates all activities from week_start to week_start+6 days.
    Computes intensity distribution for 80/20 tracking.

    Args:
        week_start: Monday of the week (ISO week start)
        repo: Repository I/O instance

    Returns:
        WeeklySummary with aggregated stats

    Raises:
        InvalidMetricsInputError: If week_start is not a Monday
    """
    # Validate week_start is Monday
    if week_start.weekday() != 0:
        raise InvalidMetricsInputError(
            f"week_start must be a Monday, got {week_start.strftime('%A')}"
        )

    week_end = week_start + timedelta(days=6)
    week_number = week_start.isocalendar()[1]

    # Initialize aggregations
    total_systemic_load = 0.0
    total_lower_body_load = 0.0
    total_activities = 0
    run_sessions = 0
    other_sport_sessions = 0
    easy_sessions = 0
    moderate_sessions = 0
    quality_sessions = 0
    race_sessions = 0
    high_intensity_sessions = 0

    activities = []

    # Iterate through 7 days
    current_date = week_start
    while current_date <= week_end:
        # Read activities for this day
        day_activities = _read_activities_for_date(current_date, repo)
        activities.extend(day_activities)

        # Aggregate loads
        for activity in day_activities:
            total_activities += 1

            if hasattr(activity, "calculated"):
                total_systemic_load += activity.calculated.systemic_load_au
                total_lower_body_load += activity.calculated.lower_body_load_au

                # Count by sport type
                if activity.sport_type in RUNNING_SPORT_TYPES:
                    run_sessions += 1
                else:
                    other_sport_sessions += 1

                # Count by session type
                session_type = activity.calculated.session_type
                if session_type == SessionType.EASY:
                    easy_sessions += 1
                elif session_type == SessionType.MODERATE:
                    moderate_sessions += 1
                elif session_type == SessionType.QUALITY:
                    quality_sessions += 1
                    high_intensity_sessions += 1
                elif session_type == SessionType.RACE:
                    race_sessions += 1
                    high_intensity_sessions += 1

        current_date += timedelta(days=1)

    # Compute intensity distribution
    intensity_distribution = compute_intensity_distribution(activities)

    # Get end-of-week metrics snapshot
    end_metrics = _read_previous_metrics(week_end, repo)
    ctl_end = end_metrics.ctl_atl.ctl if end_metrics else 0.0
    atl_end = end_metrics.ctl_atl.atl if end_metrics else 0.0
    tsb_end = end_metrics.ctl_atl.tsb if end_metrics else 0.0
    acwr_end = end_metrics.acwr.acwr if end_metrics and end_metrics.acwr else None

    # Build WeeklySummary
    weekly_summary = WeeklySummary(
        week_start=week_start,
        week_end=week_end,
        week_number=week_number,
        total_systemic_load_au=total_systemic_load,
        total_lower_body_load_au=total_lower_body_load,
        total_activities=total_activities,
        run_sessions=run_sessions,
        other_sport_sessions=other_sport_sessions,
        easy_sessions=easy_sessions,
        moderate_sessions=moderate_sessions,
        quality_sessions=quality_sessions,
        race_sessions=race_sessions,
        intensity_distribution=intensity_distribution,
        high_intensity_sessions_7d=high_intensity_sessions,
        ctl_end=ctl_end,
        atl_end=atl_end,
        tsb_end=tsb_end,
        acwr_end=acwr_end,
        notes=None,
    )

    # Persist to disk
    summary_path = weekly_metrics_summary_path()
    result = repo.write_yaml(summary_path, weekly_summary)

    if result is not None:
        raise MetricsCalculationError(
            f"Failed to write weekly summary: {result.message}"
        )

    return weekly_summary


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def aggregate_daily_load(
    target_date: date,
    repo: RepositoryIO,
) -> DailyLoad:
    """
    Aggregate all activity loads for a single day.

    Reads all activity files for target_date and sums their loads.

    Args:
        target_date: Date to aggregate
        repo: Repository I/O instance

    Returns:
        DailyLoad with summed systemic and lower-body loads
    """
    # Build path pattern: activities/{YYYY-MM}/{YYYY-MM-DD}_*.yaml
    year_month = f"{target_date.year}-{target_date.month:02d}"
    date_str = target_date.isoformat()
    pattern = f"{activities_month_dir(year_month)}/{date_str}_*.yaml"

    # Find all matching activity files
    activity_files = repo.list_files(pattern)

    systemic_total = 0.0
    lower_body_total = 0.0
    activity_count = 0
    activities_summary = []

    for file_path in activity_files:
        activity = repo.read_yaml(file_path, NormalizedActivity)

        if activity is None:
            continue  # Skip if read failed

        # Extract loads from calculated section
        if hasattr(activity, "calculated"):
            systemic_load = activity.calculated.systemic_load_au
            lower_body_load = activity.calculated.lower_body_load_au

            systemic_total += systemic_load
            lower_body_total += lower_body_load
            activity_count += 1

            # Add summary info
            activities_summary.append({
                "id": activity.id,
                "sport_type": activity.sport_type.value if isinstance(activity.sport_type, SportType) else activity.sport_type,
                "systemic_load_au": systemic_load,
                "lower_body_load_au": lower_body_load,
                "session_type": activity.calculated.session_type.value if hasattr(activity.calculated.session_type, 'value') else activity.calculated.session_type,
            })

    return DailyLoad(
        date=target_date,
        systemic_load_au=systemic_total,
        lower_body_load_au=lower_body_total,
        activity_count=activity_count,
        activities=activities_summary,
    )


def calculate_ctl_atl(
    daily_load: float,
    previous_ctl: float = 0.0,
    previous_atl: float = 0.0,
    repo: Optional[RepositoryIO] = None,
    target_date: Optional[date] = None,
) -> CTLATLMetrics:
    """
    Calculate CTL/ATL/TSB using Exponentially Weighted Moving Average (EWMA).

    Formulas:
        CTL_today = CTL_yesterday × 0.976 + systemic_daily_load × 0.024
        ATL_today = ATL_yesterday × 0.867 + systemic_daily_load × 0.133
        TSB = CTL - ATL

    Constants:
        CTL decay factor: 1 - (1/42) ≈ 0.976  (42-day time constant)
        ATL decay factor: 0.867 (empirically better than 1 - 1/7 ≈ 0.857)

    Args:
        daily_load: Today's systemic load in AU
        previous_ctl: CTL value from previous day (default 0 for cold start)
        previous_atl: ATL value from previous day (default 0 for cold start)
        repo: Optional repository for historical trend calculation
        target_date: Optional target date for trend calculation

    Returns:
        CTLATLMetrics with computed values and zone classifications
    """
    # Apply EWMA formulas
    ctl = previous_ctl * CTL_DECAY + daily_load * CTL_ALPHA
    atl = previous_atl * ATL_DECAY + daily_load * ATL_ALPHA
    tsb = ctl - atl

    # Classify zones
    ctl_zone = _classify_ctl_zone(ctl)
    tsb_zone = _classify_tsb_zone(tsb)

    # Determine trend if history available
    ctl_trend = None
    ctl_change_7d = None

    if repo and target_date:
        # Read metrics from 7 days ago
        seven_days_ago = target_date - timedelta(days=7)
        prev_week_metrics = _read_previous_metrics(seven_days_ago, repo)

        if prev_week_metrics:
            ctl_change_7d = ctl - prev_week_metrics.ctl_atl.ctl

            if ctl_change_7d > 2.0:
                ctl_trend = "building"
            elif ctl_change_7d < -2.0:
                ctl_trend = "declining"
            else:
                ctl_trend = "maintaining"

    return CTLATLMetrics(
        ctl=round(ctl, 1),
        atl=round(atl, 1),
        tsb=round(tsb, 1),
        ctl_zone=ctl_zone,
        tsb_zone=tsb_zone,
        ctl_trend=ctl_trend,
        ctl_change_7d=round(ctl_change_7d, 1) if ctl_change_7d is not None else None,
    )


def calculate_acwr(
    target_date: date,
    repo: RepositoryIO,
) -> Optional[ACWRMetrics]:
    """
    Calculate Acute:Chronic Workload Ratio.

    Formula:
        ACWR = (7-day total systemic load) / (28-day average systemic load)
             = (7-day sum) / ((28-day sum) / 4)

    Returns None if < 28 days of data exists.

    Args:
        target_date: Date to calculate ACWR for
        repo: Repository I/O instance

    Returns:
        ACWRMetrics or None if insufficient data
    """
    # Read last 28 days of metrics (not including today, which is being computed)
    metrics_28d = []
    for i in range(1, 29):  # Days 1-28 ago
        check_date = target_date - timedelta(days=i)
        metrics = _read_previous_metrics(check_date, repo)

        if metrics is None:
            # Not enough data
            return None

        metrics_28d.append(metrics)

    # Sum loads
    acute_7d = sum(m.daily_load.systemic_load_au for m in metrics_28d[:7])
    chronic_28d_total = sum(m.daily_load.systemic_load_au for m in metrics_28d)

    # Calculate average
    chronic_28d_avg = chronic_28d_total / 28.0

    # Handle divide-by-zero
    if chronic_28d_avg == 0:
        return None

    # Calculate ACWR
    acute_7d_avg = acute_7d / 7.0
    acwr = acute_7d_avg / chronic_28d_avg

    # Classify zone
    zone = _classify_acwr_zone(acwr)

    # Set injury risk flag
    injury_risk_elevated = acwr > 1.3

    return ACWRMetrics(
        acwr=round(acwr, 2),
        zone=zone,
        acute_load_7d=round(acute_7d, 1),
        chronic_load_28d=round(chronic_28d_avg, 1),
        injury_risk_elevated=injury_risk_elevated,
    )


def compute_readiness(
    tsb: float,
    load_trend: float,
    sleep_quality: Optional[float] = None,
    wellness_score: Optional[float] = None,
    injury_flags: list[str] = None,
    illness_flags: list[str] = None,
    acwr_available: bool = True,
    data_days: int = 42,
) -> ReadinessScore:
    """
    Compute readiness score from available components.

    Weights (default):
        - TSB: 20%
        - Load trend: 25%
        - Sleep: 25%
        - Wellness: 30%

    If subjective data (sleep/wellness) missing:
        Redistribute weights proportionally to TSB and load_trend
        Set confidence to LOW

    Safety overrides:
        - Injury flags → cap at 25
        - Illness flags (severe) → cap at 15-20

    Args:
        tsb: Training Stress Balance
        load_trend: 0-100 scale (100 = fresh, 0 = accumulating)
        sleep_quality: Optional sleep score 0-100
        wellness_score: Optional subjective wellness 0-100
        injury_flags: List of injury keywords found
        illness_flags: List of illness keywords found
        acwr_available: Whether ACWR is available (affects confidence)
        data_days: Total days of historical data (affects confidence)

    Returns:
        ReadinessScore with final score, level, and components
    """
    if injury_flags is None:
        injury_flags = []
    if illness_flags is None:
        illness_flags = []

    # Convert TSB to 0-100 scale
    # TSB -25 → 0, TSB -10 → 40, TSB 0 → 65, TSB +5 → 80, TSB +15 → 100
    tsb_score = max(0, min(100, (tsb + 30) * 2.5))

    # Determine weights based on available data
    has_subjective_data = sleep_quality is not None or wellness_score is not None

    if has_subjective_data:
        weights = READINESS_WEIGHTS_DEFAULT.copy()
        sleep_score = sleep_quality if sleep_quality is not None else 70.0  # Default
        wellness = wellness_score if wellness_score is not None else 70.0  # Default
    else:
        weights = READINESS_WEIGHTS_OBJECTIVE_ONLY.copy()
        sleep_score = None
        wellness = None

    # Calculate weighted sum
    score = (
        tsb_score * weights["tsb"] +
        load_trend * weights["load_trend"]
    )

    if sleep_score is not None:
        score += sleep_score * weights["sleep"]
    if wellness is not None:
        score += wellness * weights["wellness"]

    # Apply safety overrides
    injury_flag_override = False
    illness_flag_override = False
    override_reason = None

    if injury_flags:
        score = min(score, 25)
        injury_flag_override = True
        override_reason = f"Injury detected: {', '.join(injury_flags[:2])}"
    elif illness_flags:
        # Severity based on keywords
        if any(kw in ' '.join(illness_flags).lower() for kw in ["severe", "fever", "flu"]):
            score = min(score, 15)
            illness_flag_override = True
            override_reason = "Severe illness detected - rest recommended"
        else:
            score = min(score, 35)
            illness_flag_override = True
            override_reason = "Illness detected - easy effort only"

    # Clamp to 0-100
    score = int(max(0, min(100, score)))

    # Classify level
    level = _classify_readiness_level(score)

    # Determine confidence
    if data_days < BASELINE_DAYS_THRESHOLD:
        confidence = ConfidenceLevel.LOW
    elif data_days < 42 or not has_subjective_data:
        confidence = ConfidenceLevel.MEDIUM
    else:
        confidence = ConfidenceLevel.HIGH

    # Generate recommendation
    recommendation = _generate_readiness_recommendation(level, score)

    # Build components
    components = ReadinessComponents(
        tsb_contribution=round(tsb_score, 1),
        load_trend_contribution=round(load_trend, 1),
        sleep_contribution=round(sleep_score, 1) if sleep_score is not None else None,
        wellness_contribution=round(wellness, 1) if wellness is not None else None,
        weights_used=weights,
    )

    return ReadinessScore(
        score=score,
        level=level,
        confidence=confidence,
        components=components,
        recommendation=recommendation,
        injury_flag_override=injury_flag_override,
        illness_flag_override=illness_flag_override,
        override_reason=override_reason,
    )


def compute_intensity_distribution(
    activities: list[NormalizedActivity],
) -> IntensityDistribution:
    """
    Compute weekly intensity distribution for 80/20 tracking.

    Buckets activities by session_type:
        - Easy (RPE 1-4) → low
        - Moderate (RPE 5-6) → moderate
        - Quality/Race (RPE 7-10) → high

    Args:
        activities: List of activities for the week

    Returns:
        IntensityDistribution with minutes and percentages
    """
    low_minutes = 0.0
    moderate_minutes = 0.0
    high_minutes = 0.0

    for activity in activities:
        if not hasattr(activity, "calculated"):
            continue

        duration = activity.duration_minutes
        session_type = activity.calculated.session_type

        if session_type == SessionType.EASY:
            low_minutes += duration
        elif session_type == SessionType.MODERATE:
            moderate_minutes += duration
        elif session_type in [SessionType.QUALITY, SessionType.RACE]:
            high_minutes += duration

    total_minutes = low_minutes + moderate_minutes + high_minutes

    if total_minutes == 0:
        low_percent = 0.0
        moderate_percent = 0.0
        high_percent = 0.0
        is_compliant = None
    else:
        low_percent = (low_minutes / total_minutes) * 100
        moderate_percent = (moderate_minutes / total_minutes) * 100
        high_percent = (high_minutes / total_minutes) * 100

        # Check 80/20 compliance (target low >= 75%)
        is_compliant = low_percent >= 75.0

    return IntensityDistribution(
        low_minutes=round(low_minutes, 1),
        moderate_minutes=round(moderate_minutes, 1),
        high_minutes=round(high_minutes, 1),
        low_percent=round(low_percent, 1),
        moderate_percent=round(moderate_percent, 1),
        high_percent=round(high_percent, 1),
        is_compliant=is_compliant,
        target_low_percent=80.0,
    )


def compute_load_trend(
    target_date: date,
    repo: RepositoryIO,
) -> float:
    """
    Compute recent load trend for readiness calculation.

    Compares 3-day load average to 7-day load average.
    Higher value = fresher (recent load lower than baseline).

    Args:
        target_date: Date to compute trend for
        repo: Repository I/O instance

    Returns:
        Load trend score 0-100 (100 = freshest)
    """
    # Read last 7 days of metrics
    loads_7d = []
    for i in range(7):
        check_date = target_date - timedelta(days=i)
        metrics = _read_previous_metrics(check_date, repo)

        if metrics:
            loads_7d.append(metrics.daily_load.systemic_load_au)
        else:
            loads_7d.append(0.0)

    if len(loads_7d) < 3:
        # Not enough data, return neutral
        return 65.0

    # Calculate averages
    avg_3d = sum(loads_7d[:3]) / 3.0
    avg_7d = sum(loads_7d) / 7.0

    if avg_7d == 0:
        return 65.0  # Neutral if no load

    # Compute ratio: lower recent load = higher trend score
    ratio = 1 - (avg_3d / avg_7d)

    # Scale to 0-100: ratio -1 to +1 → score 0 to 100
    trend_score = 50 + (ratio * 50)

    # Clamp to 0-100
    return max(0.0, min(100.0, trend_score))


# ============================================================
# BATCH OPERATIONS
# ============================================================


def compute_metrics_batch(
    start_date: date,
    end_date: date,
    repo: RepositoryIO,
) -> list[DailyMetrics]:
    """
    Compute daily metrics for a date range.

    Useful for:
    - Initial historical computation after Strava sync
    - Recomputation after activity corrections
    - Backfilling missing metrics

    Args:
        start_date: First date to compute
        end_date: Last date to compute
        repo: Repository I/O instance

    Returns:
        List of computed DailyMetrics
    """
    results = []
    current_date = start_date

    while current_date <= end_date:
        try:
            metrics = compute_daily_metrics(current_date, repo)
            results.append(metrics)
        except Exception as e:
            # Log error but continue
            print(f"Warning: Failed to compute metrics for {current_date}: {e}")

        current_date += timedelta(days=1)

    return results


# ============================================================
# VALIDATION
# ============================================================


def validate_metrics(metrics: DailyMetrics) -> list[str]:
    """
    Validate computed metrics for sanity.

    Checks:
    - CTL/ATL/TSB in reasonable ranges
    - ACWR not extreme (not < 0.2 or > 3.0)
    - Readiness components sum correctly
    - No negative loads

    Args:
        metrics: Computed daily metrics

    Returns:
        List of warning messages (empty if all checks pass)
    """
    warnings = []

    # Check CTL range
    if metrics.ctl_atl.ctl < 0 or metrics.ctl_atl.ctl > 200:
        warnings.append(f"CTL out of range: {metrics.ctl_atl.ctl} (expected 0-200)")

    # Check ATL range
    if metrics.ctl_atl.atl < 0 or metrics.ctl_atl.atl > 300:
        warnings.append(f"ATL out of range: {metrics.ctl_atl.atl} (expected 0-300)")

    # Check TSB range
    if metrics.ctl_atl.tsb < -100 or metrics.ctl_atl.tsb > 50:
        warnings.append(f"TSB out of range: {metrics.ctl_atl.tsb} (expected -100 to +50)")

    # Check ACWR if present
    if metrics.acwr and (metrics.acwr.acwr < 0.2 or metrics.acwr.acwr > 3.0):
        warnings.append(f"ACWR extreme: {metrics.acwr.acwr} (expected 0.2-3.0)")

    # Check readiness
    if metrics.readiness.score < 0 or metrics.readiness.score > 100:
        warnings.append(f"Readiness out of range: {metrics.readiness.score} (expected 0-100)")

    # Check loads non-negative
    if metrics.daily_load.systemic_load_au < 0:
        warnings.append(f"Negative systemic load: {metrics.daily_load.systemic_load_au}")
    if metrics.daily_load.lower_body_load_au < 0:
        warnings.append(f"Negative lower-body load: {metrics.daily_load.lower_body_load_au}")

    # Check component weights sum (with tolerance)
    weights = metrics.readiness.components.weights_used
    weights_sum = sum(weights.values())
    if abs(weights_sum - 1.0) > 0.01:
        warnings.append(f"Readiness weights don't sum to 1.0: {weights_sum}")

    return warnings


# ============================================================
# INTERNAL HELPER FUNCTIONS
# ============================================================


def _read_previous_metrics(target_date: date, repo: RepositoryIO) -> Optional[DailyMetrics]:
    """Read daily metrics for a specific date."""
    metrics_path = daily_metrics_path(target_date)
    result = repo.read_yaml(metrics_path, DailyMetrics)

    # repo.read_yaml returns RepoError if file doesn't exist
    from sports_coach_engine.schemas.repository import RepoError
    if isinstance(result, RepoError):
        return None

    return result


def _read_activities_for_date(target_date: date, repo: RepositoryIO) -> list[NormalizedActivity]:
    """Read all activities for a specific date."""
    year_month = f"{target_date.year}-{target_date.month:02d}"
    date_str = target_date.isoformat()
    pattern = f"{activities_month_dir(year_month)}/{date_str}_*.yaml"

    activity_files = repo.list_files(pattern)
    activities = []

    for file_path in activity_files:
        activity = repo.read_yaml(file_path, NormalizedActivity)
        if activity:
            activities.append(activity)

    return activities


def _count_historical_days(target_date: date, repo: RepositoryIO) -> int:
    """Count days of available metrics data (not including current day being computed)."""
    count = 0
    for i in range(1, 61):  # Check last 60 days (not including today)
        check_date = target_date - timedelta(days=i)
        metrics = _read_previous_metrics(check_date, repo)
        if metrics:
            count += 1

    return count


def _classify_ctl_zone(ctl: float) -> CTLZone:
    """Classify CTL into fitness zones."""
    if ctl < 20:
        return CTLZone.BEGINNER
    elif ctl < 40:
        return CTLZone.DEVELOPING
    elif ctl < 60:
        return CTLZone.RECREATIONAL
    elif ctl < 80:
        return CTLZone.TRAINED
    elif ctl < 100:
        return CTLZone.COMPETITIVE
    else:
        return CTLZone.ELITE


def _classify_tsb_zone(tsb: float) -> TSBZone:
    """Classify TSB into form zones."""
    if tsb < -25:
        return TSBZone.OVERREACHED
    elif tsb < -10:
        return TSBZone.PRODUCTIVE
    elif tsb < 5:
        return TSBZone.OPTIMAL
    elif tsb < 15:
        return TSBZone.FRESH
    else:
        return TSBZone.PEAKED


def _classify_acwr_zone(acwr: float) -> ACWRZone:
    """Classify ACWR into injury risk zones."""
    if acwr < 0.8:
        return ACWRZone.UNDERTRAINED
    elif acwr < 1.3:
        return ACWRZone.SAFE
    elif acwr < 1.5:
        return ACWRZone.CAUTION
    else:
        return ACWRZone.HIGH_RISK


def _classify_readiness_level(score: int) -> ReadinessLevel:
    """Classify readiness score into levels."""
    if score < 35:
        return ReadinessLevel.REST_RECOMMENDED
    elif score < 50:
        return ReadinessLevel.EASY_ONLY
    elif score < 65:
        return ReadinessLevel.REDUCE_INTENSITY
    elif score < 80:
        return ReadinessLevel.READY
    else:
        return ReadinessLevel.PRIMED


def _generate_readiness_recommendation(level: ReadinessLevel, score: int) -> str:
    """Generate recommendation text based on readiness level."""
    if level == ReadinessLevel.REST_RECOMMENDED:
        return "Rest is strongly recommended. Your body needs recovery."
    elif level == ReadinessLevel.EASY_ONLY:
        return "Easy effort only. Avoid high-intensity work today."
    elif level == ReadinessLevel.REDUCE_INTENSITY:
        return "Consider reducing intensity or volume. Listen to your body."
    elif level == ReadinessLevel.READY:
        return "Execute as planned. You're ready for normal training."
    else:  # PRIMED
        return "Great day for high-quality work. You're primed and fresh!"
