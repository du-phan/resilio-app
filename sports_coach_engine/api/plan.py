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

# Import for populate_plan_workouts validation
from sports_coach_engine.api.profile import get_profile, ProfileError

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


@dataclass
class PlanWeeksResult:
    """Result from getting specific weeks from plan."""

    weeks: list  # List of WeekPlan objects
    goal: dict  # Goal details (type, date, time)
    current_week_number: int  # Current week in plan (1-indexed)
    total_weeks: int  # Total weeks in plan
    week_range: str  # "Week 5 of 12" or "Weeks 5-6 of 12"
    plan_context: dict  # Additional context (volumes, policy)


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


def get_plan_weeks(
    week_number: Optional[int] = None,
    target_date: Optional[date] = None,
    next_week: bool = False,
    count: int = 1
) -> Union[PlanWeeksResult, PlanError]:
    """
    Get specific week(s) from the training plan.

    Args:
        week_number: Explicit week number (1-indexed). Takes priority.
        target_date: Date to find week for. Second priority.
        next_week: If True, return next week. Third priority.
        count: Number of consecutive weeks to return (default: 1)

    Returns:
        PlanWeeksResult with requested weeks and context
        PlanError on failure

    Example:
        >>> # Get current week
        >>> result = get_plan_weeks()
        >>> if isinstance(result, PlanError):
        ...     print(f"Error: {result.message}")
        ... else:
        ...     print(f"{result.week_range}: {len(result.weeks[0].workouts)} workouts")

        >>> # Get next week
        >>> result = get_plan_weeks(next_week=True)

        >>> # Get specific week
        >>> result = get_plan_weeks(week_number=5)

        >>> # Get week by date
        >>> result = get_plan_weeks(target_date=date(2026, 2, 15))

        >>> # Get multiple weeks
        >>> result = get_plan_weeks(week_number=5, count=2)
    """
    # 1. Load current plan
    plan = get_current_plan()
    if isinstance(plan, PlanError):
        return plan

    # 2. Determine current week
    today = date.today()
    current_week_num = None
    before_plan_start = False

    for week in plan.weeks:
        if week.start_date <= today <= week.end_date:
            current_week_num = week.week_number
            break

    # If today is not within any week
    if current_week_num is None:
        if today > plan.end_date:
            # Past plan end - treat last week as current
            current_week_num = plan.total_weeks
        else:
            # Before plan start - week 1 hasn't started yet
            # Treat as "week 0" so next_week returns week 1
            before_plan_start = True
            current_week_num = 0  # Week 0 means "before plan starts"

    # 3. Determine target week number
    if week_number is not None:
        target_week = week_number
    elif target_date is not None:
        target_week = None
        for week in plan.weeks:
            if week.start_date <= target_date <= week.end_date:
                target_week = week.week_number
                break
        if target_week is None:
            return PlanError(
                error_type="not_found",
                message=f"No week found containing date {target_date}"
            )
    elif next_week:
        target_week = current_week_num + 1
        if target_week > plan.total_weeks:
            return PlanError(
                error_type="not_found",
                message="Next week is beyond plan end date"
            )
    else:
        # Default: current week
        # If before plan start, show week 1 (the upcoming week)
        target_week = max(current_week_num, 1)

    # 4. Validate week number
    if target_week < 1 or target_week > plan.total_weeks:
        return PlanError(
            error_type="validation",
            message=f"Week {target_week} out of range (plan has {plan.total_weeks} weeks)"
        )

    # 5. Extract requested weeks
    end_week = min(target_week + count - 1, plan.total_weeks)
    requested_weeks = [w for w in plan.weeks if target_week <= w.week_number <= end_week]

    # 6. Build week range string
    if len(requested_weeks) == 1:
        week_range = f"Week {target_week} of {plan.total_weeks}"
    else:
        week_range = f"Weeks {target_week}-{end_week} of {plan.total_weeks}"

    # 7. Return result
    return PlanWeeksResult(
        weeks=requested_weeks,
        goal={
            "type": plan.goal.get("type") if isinstance(plan.goal, dict) else plan.goal.type,
            "target_date": plan.goal.get("target_date") if isinstance(plan.goal, dict) else plan.goal.target_date,
            "target_time": plan.goal.get("target_time") if isinstance(plan.goal, dict) else plan.goal.target_time
        },
        current_week_number=current_week_num,
        total_weeks=plan.total_weeks,
        week_range=week_range,
        plan_context={
            "starting_volume_km": plan.starting_volume_km,
            "peak_volume_km": plan.peak_volume_km,
            "conflict_policy": plan.conflict_policy,
        }
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

    # 2b. Validate business logic for each week
    from sports_coach_engine.core.plan import validate_week

    all_violations = []
    for week in validated_weeks:
        # Get profile for context-aware validation
        profile_result = get_profile()
        profile_dict = profile_result.model_dump() if not isinstance(profile_result, ProfileError) else {}

        violations = validate_week(week, profile_dict)
        all_violations.extend(violations)

    # Block save only if DANGER violations found (warnings are logged but allowed)
    danger_violations = [v for v in all_violations if v.severity == "danger"]
    if danger_violations:
        violation_messages = "\n".join([
            f"  - Week {v.week}: {v.message} (Suggestion: {v.suggestion})"
            for v in danger_violations
        ])
        return PlanError(
            error_type="validation",
            message=f"Plan validation failed with {len(danger_violations)} critical violation(s):\n{violation_messages}",
        )

    # Log warnings but don't block
    warning_violations = [v for v in all_violations if v.severity == "warning"]
    if warning_violations:
        import logging
        logger = logging.getLogger(__name__)
        for v in warning_violations:
            logger.warning(f"Week {v.week}: {v.message}")

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


# ============================================================
# PROGRESSIVE DISCLOSURE API (Phase 2: Monthly Planning)
# ============================================================


def create_macro_plan(
    goal_type: str,
    race_date: date,
    target_time: Optional[str],
    total_weeks: int,
    start_date: date,
    current_ctl: float,
    starting_volume_km: float,
    peak_volume_km: float,
) -> Union[dict, PlanError]:
    """
    Generate high-level training plan structure (macro plan).

    Creates the structural roadmap for full training period without
    detailed workout prescriptions. Shows phases, volume progression,
    CTL trajectory, recovery weeks, and key milestones.

    Args:
        goal_type: Race distance ("5k", "10k", "half_marathon", "marathon")
        race_date: Goal race date
        target_time: Target finish time (optional, e.g., "1:30:00")
        total_weeks: Total weeks in plan
        start_date: Plan start date (should be Monday)
        current_ctl: CTL at plan creation
        starting_volume_km: Initial weekly volume
        peak_volume_km: Peak weekly volume

    Returns:
        dict: Macro plan structure (MacroPlan schema compatible)
        PlanError: If generation fails

    Example:
        >>> macro = create_macro_plan(
        ...     goal_type="half_marathon",
        ...     race_date=date(2026, 5, 3),
        ...     target_time="1:30:00",
        ...     total_weeks=16,
        ...     start_date=date(2026, 1, 20),
        ...     current_ctl=44.0,
        ...     starting_volume_km=25.0,
        ...     peak_volume_km=55.0
        ... )
    """
    try:
        # Import here to avoid circular dependency
        from sports_coach_engine.core.plan import generate_macro_structure
        from sports_coach_engine.schemas.plan import GoalType

        # Validate goal type
        goal_type_lower = goal_type.lower().replace("-", "_").replace(" ", "_")
        if goal_type_lower not in [g.value for g in GoalType]:
            return PlanError(
                error_type="validation",
                message=f"Invalid goal type: {goal_type}. Valid: 5k, 10k, half_marathon, marathon"
            )

        # Validate dates
        if start_date > race_date:
            return PlanError(
                error_type="validation",
                message=f"Start date ({start_date}) must be before race date ({race_date})"
            )

        # Validate start date is Monday (weekday 0)
        if start_date.weekday() != 0:
            return PlanError(
                error_type="validation",
                message=f"Start date must be Monday, got {start_date.strftime('%A')}"
            )

        # Generate macro structure
        macro = generate_macro_structure(
            goal_type=goal_type_lower,
            race_date=race_date,
            target_time=target_time,
            total_weeks=total_weeks,
            start_date=start_date,
            current_ctl=current_ctl,
            starting_volume_km=starting_volume_km,
            peak_volume_km=peak_volume_km
        )

        return macro

    except ValueError as e:
        return PlanError(
            error_type="validation",
            message=str(e)
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to create macro plan: {str(e)}"
        )


def assess_month_completion(
    month_number: int,
    week_numbers: list[int],
    planned_workouts: list[dict],
    completed_activities: list[dict],
    starting_ctl: float,
    ending_ctl: float,
    target_ctl: float,
    current_vdot: float,
) -> Union[dict, PlanError]:
    """
    Assess completed month for next month planning.

    Analyzes execution and response to inform adaptive planning:
    - Adherence rates
    - CTL progression vs. targets
    - VDOT recalibration needs
    - Injury/illness signals
    - Volume tolerance
    - Patterns detected

    Args:
        month_number: Month assessed (1-indexed)
        week_numbers: Weeks assessed (e.g., [1, 2, 3, 4])
        planned_workouts: Planned workouts from monthly plan
        completed_activities: Actual activities from Strava
        starting_ctl: CTL at month start
        ending_ctl: CTL at month end
        target_ctl: Target CTL for month end
        current_vdot: VDOT used for month's paces

    Returns:
        dict: Monthly assessment (MonthlyAssessment schema compatible)
        PlanError: If assessment fails

    Example:
        >>> assessment = assess_month_completion(
        ...     month_number=1,
        ...     week_numbers=[1, 2, 3, 4],
        ...     planned_workouts=[...],
        ...     completed_activities=[...],
        ...     starting_ctl=44.0,
        ...     ending_ctl=50.5,
        ...     target_ctl=52.0,
        ...     current_vdot=48.0
        ... )
    """
    try:
        # Import here to avoid circular dependency
        from sports_coach_engine.core.plan import assess_monthly_completion

        # Validate inputs
        if not week_numbers:
            return PlanError(
                error_type="validation",
                message="week_numbers cannot be empty"
            )

        if starting_ctl < 0 or ending_ctl < 0 or target_ctl < 0:
            return PlanError(
                error_type="validation",
                message="CTL values must be non-negative"
            )

        # Assess monthly completion
        assessment = assess_monthly_completion(
            month_number=month_number,
            week_numbers=week_numbers,
            planned_workouts=planned_workouts,
            completed_activities=completed_activities,
            starting_ctl=starting_ctl,
            ending_ctl=ending_ctl,
            target_ctl=target_ctl,
            current_vdot=current_vdot
        )

        return assessment

    except ValueError as e:
        return PlanError(
            error_type="validation",
            message=str(e)
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to assess month completion: {str(e)}"
        )


def validate_month_plan(
    monthly_plan_weeks: list[dict],
    macro_volume_targets: list[dict],
) -> Union[dict, PlanError]:
    """
    Validate 4-week monthly plan before saving.

    Checks for:
    - Volume discrepancies vs. macro plan targets
    - Guardrail violations
    - Minimum workout durations
    - Phase consistency

    Args:
        monthly_plan_weeks: 4 weeks from monthly plan
        macro_volume_targets: Volume targets from macro plan

    Returns:
        dict: Validation result with violations and warnings
        PlanError: If validation fails

    Example:
        >>> result = validate_month_plan(
        ...     monthly_plan_weeks=[week1, week2, week3, week4],
        ...     macro_volume_targets=[target1, target2, target3, target4]
        ... )
        >>> result["overall_ok"]
        True
    """
    try:
        # Import here to avoid circular dependency
        from sports_coach_engine.core.plan import validate_monthly_plan

        # Validate inputs
        if len(monthly_plan_weeks) != 4:
            return PlanError(
                error_type="validation",
                message=f"Monthly plan must have exactly 4 weeks, got {len(monthly_plan_weeks)}"
            )

        if len(macro_volume_targets) != 4:
            return PlanError(
                error_type="validation",
                message=f"Macro volume targets must have exactly 4 entries, got {len(macro_volume_targets)}"
            )

        # Validate monthly plan
        result = validate_monthly_plan(
            monthly_plan_weeks=monthly_plan_weeks,
            macro_volume_targets=macro_volume_targets
        )

        return result

    except ValueError as e:
        return PlanError(
            error_type="validation",
            message=str(e)
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to validate monthly plan: {str(e)}"
        )


def generate_month_plan(
    month_number: int,
    week_numbers: list[int],
    macro_plan: dict,
    current_vdot: float,
    profile: dict,
    volume_adjustment: float = 1.0,
) -> Union[dict, PlanError]:
    """
    Generate detailed monthly plan (2-6 weeks) with workout prescriptions.

    API wrapper that validates inputs and calls core.plan.generate_monthly_plan().

    Args:
        month_number: Month number (1-5 typically, may vary)
        week_numbers: List of week numbers for this cycle (e.g., [1,2,3,4] or [9,10,11])
        macro_plan: Macro plan dict with volume_trajectory, structure.phases, etc.
        current_vdot: Current VDOT value (30.0-85.0)
        profile: Athlete profile dict with constraints, sports, preferences
        volume_adjustment: Multiplier for volume targets (0.5-1.5 reasonable range)

    Returns:
        Dict with monthly plan or PlanError

    Example:
        >>> result = generate_month_plan(
        ...     month_number=1,
        ...     week_numbers=[1, 2, 3, 4],
        ...     macro_plan=macro_plan_dict,
        ...     current_vdot=48.0,
        ...     profile=profile_dict
        ... )
        >>> if isinstance(result, dict):
        ...     print(f"Generated {result['num_weeks']} weeks")
    """
    from sports_coach_engine.core.plan import generate_monthly_plan

    # Validation
    if month_number < 1:
        return PlanError(
            error_type="validation",
            message="month_number must be >= 1"
        )

    if not week_numbers:
        return PlanError(
            error_type="validation",
            message="week_numbers cannot be empty"
        )

    if not (2 <= len(week_numbers) <= 6):
        return PlanError(
            error_type="validation",
            message=f"Cycle must be 2-6 weeks, got {len(week_numbers)} weeks"
        )

    if not (30.0 <= current_vdot <= 85.0):
        return PlanError(
            error_type="validation",
            message=f"VDOT must be 30-85, got {current_vdot}"
        )

    if not (0.5 <= volume_adjustment <= 1.5):
        return PlanError(
            error_type="validation",
            message=f"volume_adjustment must be 0.5-1.5, got {volume_adjustment}"
        )

    # Validate macro plan has required fields
    if not isinstance(macro_plan, dict):
        return PlanError(
            error_type="validation",
            message="macro_plan must be a dict"
        )

    if "volume_trajectory" not in macro_plan:
        return PlanError(
            error_type="validation",
            message="macro_plan missing required field: volume_trajectory"
        )

    if "structure" not in macro_plan or "phases" not in macro_plan.get("structure", {}):
        return PlanError(
            error_type="validation",
            message="macro_plan missing required field: structure.phases"
        )

    # Validate profile has required fields
    if not isinstance(profile, dict):
        return PlanError(
            error_type="validation",
            message="profile must be a dict"
        )

    try:
        monthly_plan = generate_monthly_plan(
            month_number=month_number,
            week_numbers=week_numbers,
            macro_plan=macro_plan,
            current_vdot=current_vdot,
            profile=profile,
            volume_adjustment=volume_adjustment
        )
        return monthly_plan

    except ValueError as e:
        return PlanError(
            error_type="validation",
            message=str(e)
        )
    except KeyError as e:
        return PlanError(
            error_type="validation",
            message=f"Missing required field: {str(e)}"
        )
    except Exception as e:
        return PlanError(
            error_type="unknown",
            message=f"Failed to generate monthly plan: {str(e)}"
        )
