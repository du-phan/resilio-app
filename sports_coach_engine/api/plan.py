"""
Plan API - Training plan operations and adaptation management.

Provides functions for Claude Code to manage training plans and
handle adaptation suggestions.
"""

from datetime import date
from typing import Optional, Union
from dataclasses import dataclass

from sports_coach_engine.core.paths import current_plan_path, athlete_profile_path
from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
from sports_coach_engine.schemas.repository import RepoError
from sports_coach_engine.core.workflows import run_plan_generation, WorkflowError
from sports_coach_engine.schemas.plan import MasterPlan
from sports_coach_engine.schemas.profile import Goal, AthleteProfile
from sports_coach_engine.schemas.adaptation import Suggestion

# Import toolkit functions from core modules
from sports_coach_engine.core.plan import (
    calculate_periodization,
    calculate_volume_progression,
    suggest_volume_adjustment,
    create_workout,
    validate_guardrails,
    save_plan_review,
    append_plan_adaptation,
    initialize_training_log,
    append_weekly_summary,
)
from sports_coach_engine.core.adaptation import (
    detect_adaptation_triggers,
    assess_override_risk,
)


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
    # Load current plan
    plan_path = current_plan_path()
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(allow_missing=True, should_validate=True))

    if result is None:
        return PlanError(
            error_type="not_found",
            message="No training plan found. Set a goal to generate a plan.",
        )

    if isinstance(result, RepoError):
        return PlanError(
            error_type="validation",
            message=f"Failed to load plan: {str(result)}",
        )

    plan = result
    # Get goal type for logging (plan.goal is a dict, not Goal object)
    goal_type = plan.goal.get('type') if isinstance(plan.goal, dict) else plan.goal.type
    goal_type_str = goal_type.value if hasattr(goal_type, 'value') else str(goal_type)
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

    # Update profile with new goal if provided
    if goal:
        profile_path = athlete_profile_path()
        profile_result = repo.read_yaml(profile_path, AthleteProfile, ReadOptions(should_validate=True))

        if isinstance(profile_result, RepoError):
            return PlanError(
                error_type="validation",
                message=f"Failed to load profile: {str(profile_result)}",
            )

        profile = profile_result
        profile.goal = goal

        # Save updated profile
        write_result = repo.write_yaml(profile_path, profile)
        if isinstance(write_result, RepoError):
            return PlanError(
                error_type="validation",
                message=f"Failed to save profile: {str(write_result)}",
            )

    # Call M1 plan generation workflow
    try:
        result = run_plan_generation(repo, goal=goal)
    except WorkflowError as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to generate plan: {str(e)}",
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Unexpected error: {str(e)}",
        )

    # Handle workflow failure
    if not result.success or result.plan is None:
        error_msg = "; ".join(result.warnings) if result.warnings else "Plan generation failed"        # Check if it's because there's no goal
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

    # Parse plan dict to MasterPlan object
    try:
        plan = MasterPlan.model_validate(result.plan)
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to parse generated plan: {str(e)}",
        )
    # Get goal type for logging (plan.goal is a dict, not Goal object)
    goal_type = plan.goal.get('type') if isinstance(plan.goal, dict) else plan.goal.type
    goal_type_str = goal_type.value if hasattr(goal_type, 'value') else str(goal_type)
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

    # Simplified for v0: return empty list
    # Full implementation would scan suggestions/ directory
    suggestions = []
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
    #  Simplified for v0: not implemented
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
    #  Simplified for v0: not implemented
    return PlanError(
        error_type="not_found",
        message=f"Suggestion {suggestion_id} not found. Suggestion management is simplified in v0.",
    )


def populate_plan_workouts(weeks_data: list[dict]) -> Union[MasterPlan, PlanError]:
    """
    Populate weekly workouts in the current training plan.

    This replaces the empty weeks array with actual weekly workout prescriptions.
    The plan skeleton must exist (created by regenerate_plan).

    Workflow:
    1. Load current plan skeleton
    2. Validate weeks_data structure against WeekPlan schema
    3. Merge new weeks into plan.weeks array
    4. Validate complete MasterPlan
    5. Save to YAML with atomic write
    6. Log operation via M14

    Args:
        weeks_data: List of week dictionaries matching WeekPlan schema

    Returns:
        Updated MasterPlan with populated weeks
        PlanError on failure

    Example:
        >>> weeks = [
        ...     {
        ...         "week_number": 1,
        ...         "phase": "base",
        ...         "start_date": "2026-01-15",
        ...         "end_date": "2026-01-21",
        ...         "target_volume_km": 22.0,
        ...         "workouts": [...]
        ...     }
        ... ]
        >>> plan = populate_plan_workouts(weeks)
    """
    repo = RepositoryIO()
    # 1. Load current plan
    plan_path = current_plan_path()
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(should_validate=True))

    if result is None:
        return PlanError(
            error_type="not_found",
            message="No plan found. Run 'sce plan regen' first to create skeleton.",
        )

    if isinstance(result, RepoError):
        return PlanError(
            error_type="validation",
            message=f"Failed to load plan: {str(result)}",
        )

    plan = result

    # 2. Validate weeks_data structure
    try:
        from sports_coach_engine.schemas.plan import WeekPlan
        validated_weeks = [WeekPlan.model_validate(w) for w in weeks_data]
    except Exception as e:
        return PlanError(
            error_type="validation",
            message=f"Invalid week data: {str(e)}",
        )

    # 3. Merge into plan (replace weeks array)
    plan.weeks = validated_weeks

    # 4. Validate complete plan
    try:
        complete_plan = MasterPlan.model_validate(plan.model_dump())
    except Exception as e:
        return PlanError(
            error_type="validation",
            message=f"Complete plan validation failed: {str(e)}",
        )

    # 5. Save to YAML
    write_result = repo.write_yaml(plan_path, complete_plan)
    if isinstance(write_result, RepoError):
        return PlanError(
            error_type="unknown",
            message=f"Failed to save plan: {str(write_result)}",
        )

    # 6. Log success
    total_workouts = sum(len(w.workouts) for w in validated_weeks)

    return complete_plan


def update_plan_week(week_number: int, week_data: dict) -> Union[MasterPlan, PlanError]:
    """
    Update a single week in the current training plan.

    This replaces or adds a specific week while preserving other weeks.
    Useful for mid-week adjustments or updating a single week's workouts.

    Workflow:
    1. Load current plan
    2. Validate week_data structure against WeekPlan schema
    3. Find and replace week with matching week_number (or append if new)
    4. Validate complete MasterPlan
    5. Save to YAML with atomic write
    6. Log operation via M14

    Args:
        week_number: Week number to update (1-indexed)
        week_data: Week dictionary matching WeekPlan schema

    Returns:
        Updated MasterPlan with modified week
        PlanError on failure

    Example:
        >>> week5 = {
        ...     "week_number": 5,
        ...     "phase": "build",
        ...     "start_date": "2026-02-12",
        ...     "end_date": "2026-02-18",
        ...     "target_volume_km": 36.0,
        ...     "workouts": [...]
        ... }
        >>> plan = update_plan_week(5, week5)
    """
    repo = RepositoryIO()
    # 1. Load current plan
    plan_path = current_plan_path()
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(should_validate=True))

    if result is None:
        return PlanError(
            error_type="not_found",
            message="No plan found. Run 'sce plan regen' first to create skeleton.",
        )

    if isinstance(result, RepoError):
        return PlanError(
            error_type="validation",
            message=f"Failed to load plan: {str(result)}",
        )

    plan = result

    # 2. Validate week_data structure
    try:
        from sports_coach_engine.schemas.plan import WeekPlan
        validated_week = WeekPlan.model_validate(week_data)
    except Exception as e:
        return PlanError(
            error_type="validation",
            message=f"Invalid week data: {str(e)}",
        )

    # Verify week_number matches
    if validated_week.week_number != week_number:
        return PlanError(
            error_type="validation",
            message=f"Week number mismatch: expected {week_number}, got {validated_week.week_number}",
        )

    # 3. Find and replace week (or append if new)
    week_found = False
    for i, existing_week in enumerate(plan.weeks):
        if existing_week.week_number == week_number:
            plan.weeks[i] = validated_week
            week_found = True
            break

    if not week_found:
        # Append new week and sort
        plan.weeks.append(validated_week)
        plan.weeks.sort(key=lambda w: w.week_number)

    # 4. Validate complete plan
    try:
        complete_plan = MasterPlan.model_validate(plan.model_dump())
    except Exception as e:
        return PlanError(
            error_type="validation",
            message=f"Complete plan validation failed: {str(e)}",
        )

    # 5. Save to YAML
    write_result = repo.write_yaml(plan_path, complete_plan)
    if isinstance(write_result, RepoError):
        return PlanError(
            error_type="unknown",
            message=f"Failed to save plan: {str(write_result)}",
        )

    # 6. Log success
    action = "Updated" if week_found else "Added"
    total_workouts = len(validated_week.workouts)
    return complete_plan


def update_plan_from_week(start_week: int, weeks_data: list[dict]) -> Union[MasterPlan, PlanError]:
    """
    Update plan from a specific week onwards, preserving earlier weeks.

    This is useful for "replan the rest of the season" scenarios where
    earlier weeks remain unchanged but later weeks need modification.

    Workflow:
    1. Load current plan
    2. Validate weeks_data structure against WeekPlan schema
    3. Keep weeks < start_week, replace weeks >= start_week
    4. Validate complete MasterPlan
    5. Save to YAML with atomic write
    6. Log operation via M14

    Args:
        start_week: First week number to update (inclusive, 1-indexed)
        weeks_data: List of week dictionaries matching WeekPlan schema

    Returns:
        Updated MasterPlan with modified weeks
        PlanError on failure

    Example:
        >>> # Keep weeks 1-4, replace weeks 5-10
        >>> remaining_weeks = [
        ...     {"week_number": 5, ...},
        ...     {"week_number": 6, ...},
        ...     # ... weeks 7-10
        ... ]
        >>> plan = update_plan_from_week(5, remaining_weeks)
    """
    repo = RepositoryIO()
    # 1. Load current plan
    plan_path = current_plan_path()
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(should_validate=True))

    if result is None:
        return PlanError(
            error_type="not_found",
            message="No plan found. Run 'sce plan regen' first to create skeleton.",
        )

    if isinstance(result, RepoError):
        return PlanError(
            error_type="validation",
            message=f"Failed to load plan: {str(result)}",
        )

    plan = result

    # 2. Validate weeks_data structure
    try:
        from sports_coach_engine.schemas.plan import WeekPlan
        validated_weeks = [WeekPlan.model_validate(w) for w in weeks_data]
    except Exception as e:
        return PlanError(
            error_type="validation",
            message=f"Invalid week data: {str(e)}",
        )

    # Verify all weeks are >= start_week
    for week in validated_weeks:
        if week.week_number < start_week:
            return PlanError(
                error_type="validation",
                message=f"Week {week.week_number} is before start_week {start_week}",
            )

    # 3. Keep earlier weeks, replace from start_week onwards
    earlier_weeks = [w for w in plan.weeks if w.week_number < start_week]
    plan.weeks = earlier_weeks + validated_weeks
    plan.weeks.sort(key=lambda w: w.week_number)

    # 4. Validate complete plan
    try:
        complete_plan = MasterPlan.model_validate(plan.model_dump())
    except Exception as e:
        return PlanError(
            error_type="validation",
            message=f"Complete plan validation failed: {str(e)}",
        )

    # 5. Save to YAML
    write_result = repo.write_yaml(plan_path, complete_plan)
    if isinstance(write_result, RepoError):
        return PlanError(
            error_type="unknown",
            message=f"Failed to save plan: {str(write_result)}",
        )

    # 6. Log success
    total_workouts = sum(len(w.workouts) for w in validated_weeks)

    return complete_plan

# ============================================================
# PLAN REVIEW AND TRAINING LOG API
# ============================================================


def save_training_plan_review(
    review_file_path: str,
    approved: bool = True
) -> Union[dict, PlanError]:
    """Save training plan review markdown to repository.

    High-level API function that:
    1. Loads current plan
    2. Gets athlete profile for name
    3. Validates review file exists
    4. Calls core save_plan_review() function
    5. Handles all error cases gracefully

    Args:
        review_file_path: Path to review markdown file
        approved: True for approved plan, False for draft

    Returns:
        Success: dict with saved_path, approval_timestamp
        Error: PlanError with error details

    Example:
        result = save_training_plan_review("/tmp/training_plan_review_2026_01_20.md")
        if isinstance(result, PlanError):
            print(f"Error: {result.message}")
        else:
            print(f"Review saved to: {result['saved_path']}")
    """
    import os
    repo = RepositoryIO()

    # 1. Load current plan
    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        return plan_result

    plan = plan_result

    # 2. Get athlete profile for name
    athlete_name = None
    profile_result = repo.read_yaml(athlete_profile_path(), AthleteProfile, ReadOptions())
    if not isinstance(profile_result, RepoError):
        athlete_name = profile_result.name

    # 3. Validate review file exists
    if not os.path.exists(review_file_path):
        return PlanError(
            error_type="not_found",
            message=f"Review file not found: {review_file_path}"
        )

    # 4. Call core function
    try:
        result = save_plan_review(
            review_file_path=review_file_path,
            plan=plan,
            athlete_name=athlete_name,
            approved=approved,
            repo=repo
        )
        return result
    except FileNotFoundError as e:
        return PlanError(
            error_type="not_found",
            message=str(e)
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to save review: {str(e)}"
        )


def append_training_plan_adaptation(
    adaptation_file_path: str,
    reason: str
) -> Union[dict, PlanError]:
    """Append plan adaptation to existing review markdown.

    High-level API function that:
    1. Loads current plan
    2. Validates existing review exists
    3. Validates adaptation file exists
    4. Calls core append_plan_adaptation() function
    5. Handles all error cases gracefully

    Args:
        adaptation_file_path: Path to adaptation markdown file
        reason: Adaptation reason (illness/injury/schedule_change/etc)

    Returns:
        Success: dict with review_path, adaptation_timestamp, reason
        Error: PlanError with error details

    Example:
        result = append_training_plan_adaptation("/tmp/plan_adaptation_2026_02_15.md", "illness")
        if isinstance(result, PlanError):
            print(f"Error: {result.message}")
        else:
            print(f"Adaptation appended to: {result['review_path']}")
    """
    import os
    repo = RepositoryIO()

    # 1. Load current plan
    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        return plan_result

    plan = plan_result

    # 2. Validate adaptation file exists
    if not os.path.exists(adaptation_file_path):
        return PlanError(
            error_type="not_found",
            message=f"Adaptation file not found: {adaptation_file_path}"
        )

    # 3. Call core function
    try:
        result = append_plan_adaptation(
            adaptation_file_path=adaptation_file_path,
            plan=plan,
            reason=reason,
            repo=repo
        )
        return result
    except FileNotFoundError as e:
        return PlanError(
            error_type="not_found",
            message=str(e)
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to append adaptation: {str(e)}"
        )


def initialize_plan_training_log() -> Union[dict, PlanError]:
    """Initialize training log for current plan.

    High-level API function that:
    1. Loads current plan
    2. Gets athlete profile for name
    3. Calls core initialize_training_log() function
    4. Handles all error cases gracefully

    Returns:
        Success: dict with log_path, created_timestamp
        Error: PlanError with error details

    Example:
        result = initialize_plan_training_log()
        if isinstance(result, PlanError):
            print(f"Error: {result.message}")
        else:
            print(f"Training log initialized: {result['log_path']}")
    """
    repo = RepositoryIO()

    # 1. Load current plan
    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        return plan_result

    plan = plan_result

    # 2. Get athlete profile for name
    athlete_name = None
    profile_result = repo.read_yaml(athlete_profile_path(), AthleteProfile, ReadOptions())
    if not isinstance(profile_result, RepoError):
        athlete_name = profile_result.name

    # 3. Call core function
    try:
        result = initialize_training_log(
            plan=plan,
            athlete_name=athlete_name,
            repo=repo
        )
        return result
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to initialize training log: {str(e)}"
        )


def append_weekly_training_summary(week_data: dict) -> Union[dict, PlanError]:
    """Append weekly summary to training log.

    High-level API function that:
    1. Loads current plan
    2. Validates log exists (initialized with plan)
    3. Validates week_data structure
    4. Calls core append_weekly_summary() function
    5. Handles all error cases gracefully

    Args:
        week_data: Weekly summary dict (see core function for structure)

    Returns:
        Success: dict with log_path, week_number, appended_timestamp
        Error: PlanError with error details

    Example:
        week_data = {
            "week_number": 1,
            "week_dates": "Jan 20-26",
            "planned_volume_km": 22.0,
            "actual_volume_km": 20.0,
            "adherence_pct": 91.0,
            "completed_workouts": [...],
            "key_metrics": {"ctl": 30, "tsb": 1, "acwr": 1.1},
            "coach_observations": "Great first week...",
            "milestones": []
        }
        result = append_weekly_training_summary(week_data)
    """
    repo = RepositoryIO()

    # 1. Load current plan
    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        return plan_result

    plan = plan_result

    # 2. Validate week_data structure
    required_fields = [
        "week_number", "week_dates", "planned_volume_km", "actual_volume_km",
        "adherence_pct", "completed_workouts", "key_metrics", "coach_observations"
    ]
    for field in required_fields:
        if field not in week_data:
            return PlanError(
                error_type="validation",
                message=f"Missing required field in week_data: {field}"
            )

    # 3. Call core function
    try:
        result = append_weekly_summary(
            week_data=week_data,
            plan=plan,
            repo=repo
        )
        return result
    except FileNotFoundError as e:
        return PlanError(
            error_type="not_found",
            message=str(e)
        )
    except ValueError as e:
        return PlanError(
            error_type="validation",
            message=str(e)
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to append weekly summary: {str(e)}"
        )
