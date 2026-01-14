"""
Metrics API - Metrics queries with interpretations.

Provides functions for Claude Code to get current training metrics
with human-readable context.
"""

from datetime import date, timedelta
from typing import Optional, Union
from dataclasses import dataclass

from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.schemas.repository import RepoError
from sports_coach_engine.core.enrichment import enrich_metrics
from sports_coach_engine.core.logger import log_message, MessageRole
from sports_coach_engine.schemas.metrics import DailyMetrics, ReadinessScore, IntensityDistribution
from sports_coach_engine.schemas.enrichment import EnrichedMetrics


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class MetricsError:
    """Error result from metrics operations."""

    error_type: str  # "not_found", "insufficient_data", "validation", "unknown"
    message: str
    minimum_days_needed: Optional[int] = None  # For insufficient_data errors


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def get_current_metrics() -> Union[EnrichedMetrics, MetricsError]:
    """
    Get current training metrics with human-readable interpretations.

    Workflow:
    1. Load most recent DailyMetrics from metrics/daily/
    2. Enrich via M12 to add interpretations and context
    3. Log operation via M14
    4. Return enriched metrics

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
        - acwr: Acute:Chronic Workload Ratio with risk level (if 28+ days data)
        - readiness: Overall readiness score
        - disclosure_level: What metrics are shown based on data history
        - low_intensity_percent: Percent in zone 1-2
        - intensity_on_target: Meeting 80/20 guideline?

        MetricsError on failure containing:
        - error_type: Category of error
        - message: Human-readable error description

    Example:
        >>> metrics = get_current_metrics()
        >>> if isinstance(metrics, MetricsError):
        ...     print(f"No metrics available: {metrics.message}")
        ... else:
        ...     print(f"CTL: {metrics.ctl.value} ({metrics.ctl.interpretation})")
        ...     print(f"TSB: {metrics.tsb.value} ({metrics.tsb.zone})")
        ...     print(f"Readiness: {metrics.readiness.value}/100")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, "get_current_metrics()")

    # Find most recent metrics file
    latest_metrics_date = _find_latest_metrics_date(repo)
    if latest_metrics_date is None:
        log_message(
            repo,
            MessageRole.SYSTEM,
            "No metrics found - no training data available",
        )
        return MetricsError(
            error_type="not_found",
            message="No metrics available yet. Sync activities or log workouts to generate metrics.",
        )

    # Load metrics
    metrics_path = f"metrics/daily/{latest_metrics_date}.yaml"
    result = repo.read_yaml(metrics_path, DailyMetrics, ReadOptions(validate=True))

    if isinstance(result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load metrics: {str(result)}",
        )
        return MetricsError(
            error_type="validation",
            message=f"Failed to load metrics: {str(result)}",
        )

    daily_metrics = result

    # Enrich metrics via M12
    try:
        enriched = enrich_metrics(daily_metrics, repo)
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to enrich metrics: {str(e)}",
        )
        return MetricsError(
            error_type="unknown",
            message=f"Failed to enrich metrics: {str(e)}",
        )

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Returned metrics for {enriched.date}: "
        f"CTL={enriched.ctl.formatted_value}, "
        f"TSB={enriched.tsb.formatted_value}, "
        f"readiness={enriched.readiness.formatted_value}",
    )

    return enriched


def get_readiness() -> Union[ReadinessScore, MetricsError]:
    """
    Get current readiness score with detailed breakdown.

    Workflow:
    1. Load most recent DailyMetrics
    2. Extract readiness score and components
    3. Log operation via M14
    4. Return readiness score

    Returns:
        ReadinessScore with:
        - score: 0-100 overall readiness
        - level: "rest_recommended", "easy_only", "reduce_intensity", "ready", "primed"
        - confidence: "low", "medium", "high" based on data availability
        - components: Breakdown of contributing factors
          - tsb_contribution: Form contribution
          - load_trend_contribution: Recent load trend
          - sleep_contribution: Sleep quality (if available)
          - wellness_contribution: Subjective wellness (if available)
        - recommendation: Suggested workout intensity
        - injury_flag_override: Whether injury flag forced low readiness
        - illness_flag_override: Whether illness flag forced low readiness

        MetricsError on failure containing error details

    Example:
        >>> readiness = get_readiness()
        >>> if isinstance(readiness, MetricsError):
        ...     print(f"No readiness data: {readiness.message}")
        ... else:
        ...     print(f"Readiness: {readiness.score}/100 ({readiness.level})")
        ...     print(f"Recommendation: {readiness.recommendation}")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, "get_readiness()")

    # Find most recent metrics
    latest_metrics_date = _find_latest_metrics_date(repo)
    if latest_metrics_date is None:
        log_message(
            repo,
            MessageRole.SYSTEM,
            "No metrics found - cannot compute readiness",
        )
        return MetricsError(
            error_type="not_found",
            message="No readiness data available yet. Sync activities to generate metrics.",
        )

    # Load metrics
    metrics_path = f"metrics/daily/{latest_metrics_date}.yaml"
    result = repo.read_yaml(metrics_path, DailyMetrics, ReadOptions(validate=True))

    if isinstance(result, RepoError):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load metrics: {str(result)}",
        )
        return MetricsError(
            error_type="validation",
            message=f"Failed to load metrics: {str(result)}",
        )

    daily_metrics = result

    # Extract readiness
    if daily_metrics.readiness is None:
        log_message(
            repo,
            MessageRole.SYSTEM,
            "Readiness not computed - insufficient data",
        )
        return MetricsError(
            error_type="insufficient_data",
            message="Readiness requires at least 7 days of training data",
            minimum_days_needed=7,
        )

    readiness = daily_metrics.readiness

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Readiness: {readiness.score}/100 ({readiness.level.value})",
    )

    return readiness


def get_intensity_distribution(days: int = 7) -> Union[IntensityDistribution, MetricsError]:
    """
    Get intensity distribution over a time period.

    Workflow:
    1. Load DailyMetrics for the specified number of days
    2. Aggregate intensity minutes across all days
    3. Calculate percentages
    4. Check 80/20 compliance (if >= 3 run days/week)
    5. Log operation via M14
    6. Return intensity distribution

    Args:
        days: Number of days to analyze (default 7)

    Returns:
        IntensityDistribution with:
        - low_minutes: Time in RPE 1-4 (Zone 1-2)
        - moderate_minutes: Time in RPE 5-6 (Zone 3)
        - high_minutes: Time in RPE 7-10 (Zone 4-5)
        - low_percent: Percentage in low intensity
        - moderate_percent: Percentage in moderate intensity
        - high_percent: Percentage in high intensity
        - is_compliant: Whether meeting 80/20 rule (>= 3 run days)
        - target_low_percent: Target percentage for low intensity (80%)

        MetricsError on failure containing error details

    Example:
        >>> dist = get_intensity_distribution(days=7)
        >>> if isinstance(dist, MetricsError):
        ...     print(f"No intensity data: {dist.message}")
        ... else:
        ...     print(f"Low: {dist.low_percent:.0f}% | "
        ...           f"Moderate: {dist.moderate_percent:.0f}% | "
        ...           f"High: {dist.high_percent:.0f}%")
        ...     if dist.is_compliant is not None:
        ...         status = "✓" if dist.is_compliant else "✗"
        ...         print(f"80/20 compliance: {status}")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, f"get_intensity_distribution(days={days})")

    # Load metrics for the period
    intensity_data = []
    today = date.today()
    for i in range(days):
        target_date = today - timedelta(days=i)
        metrics_path = f"metrics/daily/{target_date}.yaml"
        result = repo.read_yaml(metrics_path, DailyMetrics, ReadOptions(allow_missing=True, validate=True))

        if result is None:
            # Missing metrics for this day, skip
            continue
        elif isinstance(result, RepoError):
            # Error reading metrics, skip with warning
            continue

        # Extract intensity distribution if available
        if result.intensity_distribution:
            intensity_data.append(result.intensity_distribution)

    # Check if we have any data
    if not intensity_data:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"No intensity data found for last {days} days",
        )
        return MetricsError(
            error_type="not_found",
            message=f"No training data available for the last {days} days",
        )

    # Aggregate intensity minutes
    total_low = sum(d.low_minutes for d in intensity_data)
    total_moderate = sum(d.moderate_minutes for d in intensity_data)
    total_high = sum(d.high_minutes for d in intensity_data)
    total_minutes = total_low + total_moderate + total_high

    # Calculate percentages
    if total_minutes == 0:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"No training minutes found in last {days} days",
        )
        return MetricsError(
            error_type="insufficient_data",
            message=f"No training time recorded in the last {days} days",
        )

    low_percent = (total_low / total_minutes) * 100
    moderate_percent = (total_moderate / total_minutes) * 100
    high_percent = (total_high / total_minutes) * 100

    # Check 80/20 compliance (requires 3+ run days)
    # For v0, use simplified check: is low >= 75%?
    # Full implementation would count actual run days
    is_compliant = None
    target_low_percent = None
    if len(intensity_data) >= 3:  # At least 3 days of data
        target_low_percent = 80.0
        is_compliant = low_percent >= 75.0  # Allow 5% tolerance

    distribution = IntensityDistribution(
        low_minutes=total_low,
        moderate_minutes=total_moderate,
        high_minutes=total_high,
        low_percent=low_percent,
        moderate_percent=moderate_percent,
        high_percent=high_percent,
        is_compliant=is_compliant,
        target_low_percent=target_low_percent,
    )

    # Log response
    compliance_str = ""
    if is_compliant is not None:
        compliance_str = f", 80/20: {'✓' if is_compliant else '✗'}"

    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Intensity distribution ({days} days): "
        f"Low={low_percent:.0f}%, Moderate={moderate_percent:.0f}%, High={high_percent:.0f}%{compliance_str}",
    )

    return distribution


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _find_latest_metrics_date(repo: RepositoryIO) -> Optional[date]:
    """
    Find the most recent date with metrics available.

    Returns:
        Date of most recent metrics, or None if no metrics exist.
    """
    # Check last 30 days for metrics files
    today = date.today()
    for i in range(30):
        check_date = today - timedelta(days=i)
        metrics_path = f"metrics/daily/{check_date}.yaml"
        resolved_path = repo.resolve_path(metrics_path)
        if resolved_path.exists():
            return check_date

    return None
