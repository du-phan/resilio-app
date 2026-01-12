"""
Plan API - Training plan operations and adaptation management.

Provides functions for Claude Code to manage training plans and
handle adaptation suggestions.
"""

from datetime import date
from typing import Optional, Any


def get_current_plan() -> Any:
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
    raise NotImplementedError("M10 plan generator not implemented yet")


def regenerate_plan(goal: Optional[Any] = None) -> Any:
    """
    Generate a new training plan.

    If a goal is provided, updates the athlete's goal first.
    Archives the current plan before generating a new one.

    Args:
        goal: New goal (optional). If None, regenerates with current goal.

    Returns:
        New TrainingPlan
    """
    raise NotImplementedError("M10 plan generator not implemented yet")


def get_pending_suggestions() -> list[Any]:
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
    raise NotImplementedError("M11 adaptation engine not implemented yet")


def accept_suggestion(suggestion_id: str) -> Any:
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
    raise NotImplementedError("M11 adaptation engine not implemented yet")


def decline_suggestion(suggestion_id: str) -> Any:
    """
    Decline a pending suggestion and keep the original plan.

    Args:
        suggestion_id: ID of the suggestion to decline

    Returns:
        DeclineResult with:
        - success: Whether the suggestion was declined
        - original_kept: The original workout (unchanged)
    """
    raise NotImplementedError("M11 adaptation engine not implemented yet")
