"""
Metrics API - Metrics queries with interpretations.

Provides functions for Claude Code to get current training metrics
with human-readable context.
"""

from typing import Any


def get_current_metrics() -> Any:
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
    raise NotImplementedError("M9 metrics + M12 enrichment not implemented yet")


def get_readiness() -> Any:
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
    raise NotImplementedError("M9 metrics + M12 enrichment not implemented yet")


def get_intensity_distribution(days: int = 7) -> Any:
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
    raise NotImplementedError("M9 metrics not implemented yet")
