"""
Plan API - Training plan operations and adaptation management.

Provides functions for Claude Code to manage training plans and
handle adaptation suggestions.
"""

from datetime import date
from typing import Optional, Union
from dataclasses import dataclass

from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.core.workflows import run_plan_generation, WorkflowError
from sports_coach_engine.core.logger import log_message, MessageRole
from sports_coach_engine.schemas.plan import MasterPlan
from sports_coach_engine.schemas.profile import Goal, AthleteProfile
from sports_coach_engine.schemas.adaptation import Suggestion


# ============================================================
# ERROR TYPES
# ============================================================


@dataclass
class PlanError:
    """Error result from plan operations."""

    error_type: str  # "not_found", "no_goal", "validation", "unknown"
    message: str


# ============================================================
# RESULT TYPES
# ============================================================


@dataclass
class AcceptResult:
    """Result from accepting a suggestion."""

    success: bool
    workout_modified: dict
    confirmation_message: str


@dataclass
class DeclineResult:
    """Result from declining a suggestion."""

    success: bool
    original_kept: dict


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================


def get_current_plan() -> Union[MasterPlan, PlanError]:
    """
    Get the full training plan with all weeks.

    Workflow:
    1. Load current_plan.yaml from plans/
    2. Calculate current week based on today's date
    3. Log operation via M14
    4. Return plan

    Returns:
        MasterPlan containing:
        - goal: Target race/goal
        - athlete_name: Athlete name
        - total_weeks: Plan duration
        - plan_start: Plan start date
        - plan_end: Plan end date
        - weeks: All planned weeks with workouts
        - constraints_applied: Training constraints in effect

        PlanError on failure containing error details

    Example:
        >>> plan = get_current_plan()
        >>> if isinstance(plan, PlanError):
        ...     print(f"No plan: {plan.message}")
        ... else:
        ...     # Find current week
        ...     today = date.today()
        ...     for i, week in enumerate(plan.weeks, 1):
        ...         if week.week_start <= today <= week.week_end:
        ...             print(f"Week {i}/{plan.total_weeks} ({week.phase})")
        ...             break
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, "get_current_plan()")

    # Load current plan
    plan_path = "plans/current_plan.yaml"
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(allow_missing=True, validate=True))

    if result is None:
        log_message(
            repo,
            MessageRole.SYSTEM,
            "No current plan found",
        )
        return PlanError(
            error_type="not_found",
            message="No training plan found. Set a goal to generate a plan.",
        )

    if isinstance(result, Exception):
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Failed to load plan: {str(result)}",
        )
        return PlanError(
            error_type="validation",
            message=f"Failed to load plan: {str(result)}",
        )

    plan = result

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Returned plan: {plan.total_weeks} weeks, goal={plan.goal.type.value}",
    )

    return plan


def regenerate_plan(goal: Optional[Goal] = None) -> Union[MasterPlan, PlanError]:
    """
    Generate a new training plan.

    If a goal is provided, updates the athlete's goal first.
    Archives the current plan before generating a new one.

    Workflow:
    1. If goal provided, update athlete profile with new goal
    2. Call M1 run_plan_generation() to:
       - Load profile (M4)
       - Load current metrics (M9)
       - Use M10 toolkit functions to design plan
       - Archive old plan
       - Save new plan
    3. Log operation via M14
    4. Return new plan

    Args:
        goal: New goal (optional). If None, regenerates with current goal.

    Returns:
        New MasterPlan

        PlanError on failure containing error details

    Example:
        >>> # Regenerate with new goal
        >>> new_goal = Goal(
        ...     goal_type=GoalType.HALF_MARATHON,
        ...     target_date=date(2024, 6, 1),
        ...     target_time="1:45:00"
        ... )
        >>> plan = regenerate_plan(goal=new_goal)
        >>> if isinstance(plan, PlanError):
        ...     print(f"Failed: {plan.message}")
        ... else:
        ...     print(f"New {plan.total_weeks}-week plan created")
    """
    repo = RepositoryIO()

    # Log user request
    if goal:
        log_message(
            repo,
            MessageRole.USER,
            f"regenerate_plan(goal={goal.type.value}, target_date={goal.target_date})",
        )
    else:
        log_message(repo, MessageRole.USER, "regenerate_plan()")

    # Update profile with new goal if provided
    if goal:
        profile_path = "athlete/profile.yaml"
        profile_result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(validate=True))

        if isinstance(profile_result, Exception):
            log_message(
                repo,
                MessageRole.SYSTEM,
                f"Failed to load profile: {str(profile_result)}",
            )
            return PlanError(
                error_type="validation",
                message=f"Failed to load profile: {str(profile_result)}",
            )

        profile = profile_result
        profile.goal = goal

        # Save updated profile
        write_result = repo.write_yaml(profile_path, profile)
        if isinstance(write_result, Exception):
            log_message(
                repo,
                MessageRole.SYSTEM,
                f"Failed to save profile: {str(write_result)}",
            )
            return PlanError(
                error_type="validation",
                message=f"Failed to save profile: {str(write_result)}",
            )

    # Call M1 plan generation workflow
    try:
        result = run_plan_generation(repo, goal=goal)
    except WorkflowError as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Plan generation failed: {str(e)}",
        )
        return PlanError(
            error_type="unknown",
            message=f"Failed to generate plan: {str(e)}",
        )
    except Exception as e:
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Plan generation failed: {str(e)}",
        )
        return PlanError(
            error_type="unknown",
            message=f"Unexpected error: {str(e)}",
        )

    # Handle workflow failure
    if not result.success or result.plan is None:
        error_msg = "; ".join(result.warnings) if result.warnings else "Plan generation failed"
        log_message(
            repo,
            MessageRole.SYSTEM,
            f"Plan generation failed: {error_msg}",
        )

        # Check if it's because there's no goal
        if "goal" in error_msg.lower():
            return PlanError(
                error_type="no_goal",
                message="No goal set. Set a goal first to generate a plan.",
            )
        else:
            return PlanError(
                error_type="unknown",
                message=error_msg,
            )

    plan = result.plan

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Generated new plan: {plan.total_weeks} weeks, goal={plan.goal.type.value}",
    )

    return plan


def get_pending_suggestions() -> list[Suggestion]:
    """
    Get pending adaptation suggestions awaiting user decision.

    Note: For v0, this is simplified. Full implementation would query
    a suggestions directory and filter by status.

    Workflow:
    1. Query suggestions directory (simplified for v0)
    2. Filter for status="pending"
    3. Sort by date (most recent first)
    4. Log operation via M14
    5. Return suggestions

    Returns:
        List of Suggestion objects, each containing:
        - suggestion_id: Unique ID
        - trigger_type: What triggered this (e.g., "acwr_elevated")
        - affected_date: Date of workout to be modified
        - suggestion_type: "downgrade", "skip", "move", "substitute"
        - status: "pending", "accepted", "declined", "expired"
        - original_workout: Original workout prescription
        - proposed_change: Proposed modification
        - expires_at: When suggestion expires

    Example:
        >>> suggestions = get_pending_suggestions()
        >>> for s in suggestions:
        ...     print(f"{s.suggestion_type}: {s.proposed_change.rationale}")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, "get_pending_suggestions()")

    # Simplified for v0: return empty list
    # Full implementation would scan suggestions/ directory
    suggestions = []

    # Log response
    log_message(
        repo,
        MessageRole.SYSTEM,
        f"Returned {len(suggestions)} pending suggestions",
    )

    return suggestions


def accept_suggestion(suggestion_id: str) -> Union[AcceptResult, PlanError]:
    """
    Accept a pending suggestion and apply the modification.

    Note: For v0, this is simplified. Full implementation would:
    1. Load suggestion from file
    2. Validate suggestion is still pending
    3. Apply the modification to the plan
    4. Mark suggestion as accepted
    5. Log decision to M13 (memories)

    Workflow:
    1. Load suggestion by ID
    2. Validate status is "pending"
    3. Apply proposed change to plan
    4. Update suggestion status to "accepted"
    5. Log decision via M14
    6. Return confirmation

    Args:
        suggestion_id: ID of the suggestion to accept

    Returns:
        AcceptResult with:
        - success: Whether the suggestion was applied
        - workout_modified: The modified workout details
        - confirmation_message: Human-readable confirmation

        PlanError on failure containing error details

    Example:
        >>> result = accept_suggestion("sugg_2024-01-15_001")
        >>> if isinstance(result, PlanError):
        ...     print(f"Failed: {result.message}")
        ... else:
        ...     print(result.confirmation_message)
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, f"accept_suggestion(id={suggestion_id})")

    # Simplified for v0: not implemented
    log_message(
        repo,
        MessageRole.SYSTEM,
        "Suggestion management not fully implemented in v0",
    )

    return PlanError(
        error_type="not_found",
        message=f"Suggestion {suggestion_id} not found. Suggestion management is simplified in v0.",
    )


def decline_suggestion(suggestion_id: str) -> Union[DeclineResult, PlanError]:
    """
    Decline a pending suggestion and keep the original plan.

    Note: For v0, this is simplified. Full implementation would:
    1. Load suggestion from file
    2. Validate suggestion is still pending
    3. Mark suggestion as declined
    4. Log decision to M13 (memories)

    Workflow:
    1. Load suggestion by ID
    2. Validate status is "pending"
    3. Update suggestion status to "declined"
    4. Log decision via M14
    5. Return confirmation

    Args:
        suggestion_id: ID of the suggestion to decline

    Returns:
        DeclineResult with:
        - success: Whether the suggestion was declined
        - original_kept: The original workout (unchanged)

        PlanError on failure containing error details

    Example:
        >>> result = decline_suggestion("sugg_2024-01-15_001")
        >>> if isinstance(result, PlanError):
        ...     print(f"Failed: {result.message}")
        ... else:
        ...     print("Suggestion declined, keeping original workout")
    """
    repo = RepositoryIO()

    # Log user request
    log_message(repo, MessageRole.USER, f"decline_suggestion(id={suggestion_id})")

    # Simplified for v0: not implemented
    log_message(
        repo,
        MessageRole.SYSTEM,
        "Suggestion management not fully implemented in v0",
    )

    return PlanError(
        error_type="not_found",
        message=f"Suggestion {suggestion_id} not found. Suggestion management is simplified in v0.",
    )
