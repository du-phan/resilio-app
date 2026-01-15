"""
Core analysis module - Weekly insights and risk assessment.

Provides computational analysis functions for adherence tracking,
intensity distribution validation, activity gap detection, load
distribution analysis, capacity checking, risk assessment, recovery
window estimation, training stress forecasting, and taper status tracking.
"""

from sports_coach_engine.core.analysis.weekly import (
    analyze_week_adherence,
    validate_intensity_distribution,
    detect_activity_gaps,
    analyze_load_distribution_by_sport,
    check_weekly_capacity,
)

from sports_coach_engine.core.analysis.risk import (
    assess_current_risk,
    estimate_recovery_window,
    forecast_training_stress,
    assess_taper_status,
)

__all__ = [
    # Weekly analysis
    "analyze_week_adherence",
    "validate_intensity_distribution",
    "detect_activity_gaps",
    "analyze_load_distribution_by_sport",
    "check_weekly_capacity",
    # Risk assessment
    "assess_current_risk",
    "estimate_recovery_window",
    "forecast_training_stress",
    "assess_taper_status",
]
