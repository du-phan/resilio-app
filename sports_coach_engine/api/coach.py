"""
Coach API - High-level coaching operations.

Provides functions for Claude Code to get workout recommendations,
weekly status, and training progress with full context.
"""

from datetime import date
from typing import Optional, Any


def get_todays_workout(
    target_date: Optional[date] = None,
) -> Any:
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
    raise NotImplementedError("M1 workflow not implemented yet")


def get_weekly_status() -> Any:
    """
    Get current week overview with all activities.

    Returns:
        WeeklyStatus containing week number, phase, activities, progress.
    """
    raise NotImplementedError("M1 workflow not implemented yet")


def get_training_status() -> Any:
    """
    Get current training metrics with interpretations.

    Returns:
        TrainingStatus with CTL, ATL, TSB, ACWR, readiness, intensity distribution.
    """
    raise NotImplementedError("M9 metrics not implemented yet")
