"""
Plan API - Training plan operations and adaptation management.

Provides functions for Claude Code to manage training plans and
handle adaptation suggestions.
"""

from datetime import date, timedelta
from typing import Optional, Union
from dataclasses import dataclass
import uuid

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
class PlanStructureExport:
    """Export of stored macro plan structure for validation."""

    total_weeks: int
    goal_type: str
    race_week: int
    phases: dict
    weekly_volumes_km: list
    recovery_weeks: list


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


# ============================================================
# INTENT-BASED WORKOUT GENERATION HELPERS
# ============================================================


def _calculate_date(start_date_str: str, day_of_week: int) -> str:
    """Calculate workout date from week start and day of week.

    Args:
        start_date_str: Week start date (Monday) as ISO string
        day_of_week: Weekday index (0=Mon, 6=Sun)

    Returns:
        Workout date as ISO string
    """
    start_date = date.fromisoformat(start_date_str)
    # Weekday index: Monday=0, Sunday=6
    # Calculate offset from Monday
    offset = day_of_week
    workout_date = start_date + timedelta(days=offset)
    return workout_date.isoformat()


# Removed _distribute_evenly() - violates CLI-first philosophy
# AI Coach designs exact workout distances; system only validates


# Removed _create_workout_prescription() and _generate_workouts_from_pattern()
# These functions implement rule-based workout generation, violating the
# CLI-first philosophy. AI Coach now designs exact workouts using LLM
# capabilities; Python engine only validates and persists.


@dataclass
class ValidationResult:
    """Result from validation operations."""
    ok: bool
    errors: list[dict]
    warnings: list[dict]


def _validate_explicit_workouts(
    week_data: dict,
    tolerance_km: float = 0.5
) -> ValidationResult:
    """
    Validate explicit workout format.

    Detection-only: Returns violations, never auto-fixes.

    Checks:
    - Required fields on each workout
    - Date alignment (within week boundaries)
    - Sum-to-target (workouts sum to target_volume_km ± tolerance)
    - No duplicate days

    Args:
        week_data: Week dictionary with explicit workouts
        tolerance_km: Tolerance for sum-to-target check (default 0.5km)

    Returns:
        ValidationResult with ok, errors, warnings
    """
    from datetime import datetime

    errors = []
    warnings = []

    # Required field check
    required_fields = ["date", "day_of_week", "workout_type", "distance_km", "target_rpe"]
    for i, workout in enumerate(week_data.get("workouts", [])):
        missing = [f for f in required_fields if f not in workout]
        if missing:
            errors.append({
                "type": "missing_fields",
                "workout_index": i,
                "fields": missing,
                "message": f"Workout {i}: Missing required fields {missing}"
            })

    # Date alignment check
    try:
        start = datetime.fromisoformat(week_data["start_date"]).date()
        end = datetime.fromisoformat(week_data["end_date"]).date()
        for i, workout in enumerate(week_data.get("workouts", [])):
            if "date" in workout:
                workout_date = datetime.fromisoformat(workout["date"]).date()
                if not (start <= workout_date <= end):
                    errors.append({
                        "type": "date_out_of_range",
                        "workout_index": i,
                        "date": str(workout_date),
                        "message": f"Workout {i}: date {workout_date} not in week {start} to {end}"
                    })
    except (ValueError, KeyError) as e:
        errors.append({
            "type": "date_parse_error",
            "message": f"Failed to parse dates: {str(e)}"
        })

    # Sum-to-target check (CRITICAL)
    actual = sum(w.get("distance_km", 0) for w in week_data.get("workouts", []))
    target = week_data.get("target_volume_km", 0)
    diff = abs(actual - target)

    if diff > tolerance_km:
        errors.append({
            "type": "sum_mismatch",
            "severity": "danger",
            "actual_km": actual,
            "target_km": target,
            "diff_km": diff,
            "message": f"Workouts sum to {actual:.1f}km but target is {target:.1f}km (diff: {diff:.1f}km exceeds tolerance {tolerance_km}km)",
            "suggestion": "Adjust workout distances or update target_volume_km to match"
        })
    elif diff > 0.2:
        # Warning for noticeable differences (>200m) that are within tolerance
        warnings.append({
            "type": "sum_mismatch_minor",
            "actual_km": actual,
            "target_km": target,
            "diff_km": diff,
            "message": f"Workouts sum to {actual:.1f}km, target is {target:.1f}km (diff: {diff:.1f}km, within tolerance but noticeable)"
        })

    # Duplicate day check
    days_used = [w.get("day_of_week") for w in week_data.get("workouts", []) if "day_of_week" in w]
    duplicates = [d for d in set(days_used) if days_used.count(d) > 1]
    if duplicates:
        errors.append({
            "type": "duplicate_days",
            "days": duplicates,
            "message": f"Multiple workouts scheduled on same day(s): {duplicates}"
        })

    return ValidationResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_plan_json_structure(
    json_path: str,
    verbose: bool = False
) -> tuple[bool, list[str], list[str]]:
    """Validate plan JSON structure without saving.

    Checks for:
    - JSON syntax
    - Required fields (including workout_pattern)
    - Date alignment (Monday-Sunday)
    - Valid enum values
    - Intent-based pattern structure

    Args:
        json_path: Path to JSON file to validate
        verbose: Show detailed validation output

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    import json
    from datetime import datetime

    errors = []
    warnings = []

    # 1. Load and parse JSON
    try:
        with open(json_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return False, [f"File not found: {json_path}"], []
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON syntax: {e}"], []

    # 2. Check top-level structure
    if "weeks" not in data:
        errors.append("Missing 'weeks' key at top level")
        return False, errors, warnings

    # 3. Validate each week
    for week in data["weeks"]:
        week_num = week.get("week_number", "?")

        # Required week fields
        required = [
            "week_number",
            "phase",
            "start_date",
            "end_date",
            "target_volume_km",
            "target_systemic_load_au",
        ]
        for field in required:
            if field not in week:
                errors.append(f"Week {week_num}: Missing required field '{field}'")

        # Date alignment
        if "start_date" in week:
            try:
                start = datetime.fromisoformat(week["start_date"]).date()
                if start.weekday() != 0:
                    errors.append(
                        f"Week {week_num}: start_date must be Monday, "
                        f"got {start.strftime('%A')}"
                    )
            except ValueError as e:
                errors.append(f"Week {week_num}: Invalid start_date: {e}")

        if "end_date" in week:
            try:
                end = datetime.fromisoformat(week["end_date"]).date()
                if end.weekday() != 6:
                    errors.append(
                        f"Week {week_num}: end_date must be Sunday, "
                        f"got {end.strftime('%A')}"
                    )
            except ValueError as e:
                errors.append(f"Week {week_num}: Invalid end_date: {e}")

        # Check for explicit workouts (required)
        if "workouts" not in week:
            errors.append(
                f"Week {week_num}: Missing required field 'workouts'. "
                f"Provide explicit workout array (AI Coach designs all workouts)."
            )
        else:
            # Validate explicit format using helper
            validation_result = _validate_explicit_workouts(week)
            for error in validation_result.errors:
                errors.append(f"Week {week_num}: {error['message']}")
            for warning in validation_result.warnings:
                warnings.append(f"Week {week_num}: {warning['message']}")

        # Validate phase is valid enum value
        if "phase" in week:
            valid_phases = ["base", "build", "peak", "taper", "recovery"]
            if week["phase"] not in valid_phases:
                errors.append(
                    f"Week {week_num}: Invalid phase '{week['phase']}', "
                    f"must be one of: {', '.join(valid_phases)}"
                )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def populate_plan_workouts(weeks_data: list[dict]) -> Union[MasterPlan, PlanError]:
    """
    Add or update weekly workouts in the current training plan.

    Merges weeks into the plan: updates existing weeks (same week_number) or
    adds new weeks. Safe to call multiple times - existing weeks are preserved.

    Workflow:
    1. Load current plan
    2. Validate weeks_data structure against WeekPlan schema
    3. Merge weeks: update existing, append new
    4. Validate complete MasterPlan
    5. Save to YAML with atomic write

    Args:
        weeks_data: List of week dictionaries matching WeekPlan schema

    Returns:
        Updated MasterPlan with merged weeks
        PlanError on failure

    Example (progressive addition):
        >>> # Week 1
        >>> populate_plan_workouts([{"week_number": 1, ...}])
        >>> # Week 2 (week 1 preserved)
        >>> populate_plan_workouts([{"week_number": 2, ...}])
        >>> # Weeks 3-5 (bulk add)
        >>> populate_plan_workouts([{"week_number": 3, ...}, {"week_number": 4, ...}, {"week_number": 5, ...}])
    """
    repo = RepositoryIO()
    # 1. Load current plan (auto-create from goal if missing)
    plan_path = current_plan_path()
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(should_validate=True))

    if result is None:
        return PlanError(
            error_type="no_plan",
            message="No training plan found. Create a macro plan first with:\n"
                    "sce plan create-macro --goal-type <type> --race-date <date> "
                    "--total-weeks <N> --start-date <YYYY-MM-DD> "
                    "--current-ctl <X> --baseline-vdot <VDOT> "
                    "--macro-template-json /tmp/macro_template.json"
        )

    if isinstance(result, RepoError):
        return PlanError(
            error_type="validation",
            message=f"Failed to load plan: {str(result)}",
        )

    plan = result

    # 2. Get athlete profile for HR zone calculation
    profile_result = get_profile()
    max_hr = 189  # default fallback
    if not isinstance(profile_result, ProfileError):
        max_hr = profile_result.vital_signs.max_hr

    # 3. Validate explicit workout format and enrich
    processed_weeks_data = []
    week_hint_map = {w.week_number: w.workout_structure_hints for w in plan.weeks}
    for week_data in weeks_data:
        # Expect explicit workouts only
        if "workouts" not in week_data:
            return PlanError(
                error_type="validation",
                message=f"Week {week_data.get('week_number', '?')}: Missing 'workouts' field. "
                        f"Provide explicit workout array (AI Coach designs all workouts)."
            )

        # Validate explicit format
        validation_result = _validate_explicit_workouts(week_data)
        if not validation_result.ok:
            error_messages = "\n".join([f"  - {e['message']}" for e in validation_result.errors])
            return PlanError(
                error_type="validation",
                message=f"Week {week_data.get('week_number', '?')} validation failed:\n{error_messages}"
            )

        # Enrich workouts with HR zones and parent context
        week_data_copy = week_data.copy()
        for workout in week_data_copy["workouts"]:
            # Copy parent phase (used by enrichment.py for phase-specific guidance)
            if "phase" not in workout and "phase" in week_data_copy:
                workout["phase"] = week_data_copy["phase"]

            # Calculate HR zones if not provided
            if "hr_range_low" not in workout and "workout_type" in workout:
                workout_type = workout["workout_type"]
                hr_zones = {
                    "easy": (0.65, 0.75),
                    "long_run": (0.70, 0.78),
                    "tempo": (0.85, 0.90),
                    "intervals": (0.90, 0.95),
                    "fartlek": (0.75, 0.85),
                    "strides": (0.90, 0.95),
                    "race": (0.90, 0.98),
                    "rest": (0.50, 0.65),
                }
                low_pct, high_pct = hr_zones.get(workout_type, (0.65, 0.75))
                workout["hr_range_low"] = int(max_hr * low_pct)
                workout["hr_range_high"] = int(max_hr * high_pct)

        # Add hints if missing
        if "workout_structure_hints" not in week_data_copy:
            hints = week_hint_map.get(week_data_copy["week_number"])
            if hints is None:
                return PlanError(
                    error_type="validation",
                    message=f"Week {week_data_copy.get('week_number', '?')}: Missing workout_structure_hints and no macro hints found"
                )
            week_data_copy["workout_structure_hints"] = hints.model_dump()
        processed_weeks_data.append(week_data_copy)

    # 3. Validate weeks_data structure
    try:
        from sports_coach_engine.schemas.plan import WeekPlan
        validated_weeks = [WeekPlan.model_validate(w) for w in processed_weeks_data]
    except Exception as e:
        return PlanError(
            error_type="validation",
            message=f"Invalid week data: {str(e)}",
        )

    # 3b. Validate business logic for each week
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

    # 3. Merge weeks (upsert: update existing, add new)
    for new_week in validated_weeks:
        existing_idx = next((i for i, w in enumerate(plan.weeks) if w.week_number == new_week.week_number), None)
        if existing_idx is not None:
            plan.weeks[existing_idx] = new_week
        else:
            plan.weeks.append(new_week)

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
    # 1. Load current plan (auto-create from goal if missing)
    plan_path = current_plan_path()
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(should_validate=True))

    if result is None:
        return PlanError(
            error_type="no_plan",
            message="No training plan found. Create a macro plan first with:\n"
                    "sce plan create-macro --goal-type <type> --race-date <date> "
                    "--total-weeks <N> --start-date <YYYY-MM-DD> "
                    "--current-ctl <X> --baseline-vdot <VDOT> "
                    "--macro-template-json /tmp/macro_template.json"
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

    # 6. Auto-log plan change (v0 simple version - only for update-from)
    week_nums = [w.week_number for w in validated_weeks]
    if len(week_nums) == 1:
        change_desc = f"Replanned week {week_nums[0]}"
    else:
        change_desc = f"Replanned weeks {min(week_nums)}-{max(week_nums)}"
    _auto_log_plan_change(change_desc)

    # 7. Log success
    total_workouts = sum(len(w.workouts) for w in validated_weeks)

    return complete_plan

# ============================================================
# AUTO-LOGGING HELPER (V0 - Simple)
# ============================================================


def _auto_log_plan_change(change_description: str) -> None:
    """
    Auto-log plan changes to review markdown (v0 simple version).

    Appends a timestamped entry to the Adaptations section of the plan review.
    Fails silently if review doesn't exist (no error thrown).

    Args:
        change_description: Brief description of what changed (e.g., "Replanned weeks 5-10")

    Example:
        _auto_log_plan_change("Replanned weeks 5-10 due to illness")
    """
    from sports_coach_engine.core.paths import current_plan_review_path
    from datetime import datetime
    import logging

    logger = logging.getLogger(__name__)

    try:
        repo = RepositoryIO()
        review_path = current_plan_review_path()
        review_abs_path = repo.resolve_path(review_path)

        if not review_abs_path.exists():
            # No review yet - skip logging (not an error)
            logger.debug("Plan review not found, skipping auto-log")
            return

        # Read existing content
        with open(review_abs_path, 'r') as f:
            content = f.read()

        # Check if Adaptations section exists
        if "## Adaptations" not in content:
            # Add new section at end
            content += "\n\n## Adaptations\n\n"

        # Append new entry with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"### {timestamp}\n{change_description}\n\n"
        content += entry

        # Write back
        with open(review_abs_path, 'w') as f:
            f.write(content)

        logger.info(f"Auto-logged plan change: {change_description}")

    except Exception as e:
        # Fail silently - logging shouldn't break the operation
        logger.warning(f"Failed to auto-log plan change: {str(e)}")


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
        return PlanError(error_type="not_found", message=str(e))
    except Exception as e:
        return PlanError(error_type="unknown", message=f"Failed to save review: {str(e)}")


def export_plan_structure() -> Union[PlanStructureExport, PlanError]:
    """Export stored macro plan structure for CLI validation.

    Returns:
        PlanStructureExport with phases, volumes, recovery weeks, and race week.
        PlanError if plan is missing or data is invalid.
    """
    plan = get_current_plan()
    if isinstance(plan, PlanError):
        return plan

    # Goal details (dict in MasterPlan)
    goal = getattr(plan, "goal", None)
    if goal is None:
        return PlanError(error_type="validation", message="Plan missing goal data")

    goal_type = goal.get("type") if isinstance(goal, dict) else getattr(goal, "type", None)
    goal_date = goal.get("target_date") if isinstance(goal, dict) else getattr(goal, "target_date", None)
    if goal_type is None or goal_date is None:
        return PlanError(error_type="validation", message="Goal type/date missing in plan")

    if isinstance(goal_date, str):
        try:
            goal_date = date.fromisoformat(goal_date)
        except ValueError:
            return PlanError(error_type="validation", message="Invalid goal target_date in plan")

    total_weeks = getattr(plan, "total_weeks", None)
    if not isinstance(total_weeks, int) or total_weeks <= 0:
        return PlanError(error_type="validation", message="Invalid total_weeks in plan")

    # Phase counts (phase -> weeks)
    phases_list = getattr(plan, "phases", None) or []
    phases: dict = {}
    for phase in phases_list:
        if not isinstance(phase, dict):
            continue
        phase_name = phase.get("phase")
        start_week = phase.get("start_week")
        end_week = phase.get("end_week")
        if phase_name is None or start_week is None or end_week is None:
            continue
        phases[phase_name] = int(end_week) - int(start_week) + 1

    # Weeks (sorted by week_number)
    weeks_list = getattr(plan, "weeks", None) or []
    weeks_sorted = sorted(weeks_list, key=lambda w: getattr(w, "week_number", 0))
    week_numbers = [getattr(w, "week_number", None) for w in weeks_sorted]
    if len(weeks_sorted) != total_weeks or set(week_numbers) != set(range(1, total_weeks + 1)):
        return PlanError(
            error_type="validation",
            message="Plan weeks mismatch total_weeks (expected contiguous weeks 1..N)",
        )

    weekly_volumes_km = [getattr(w, "target_volume_km", 0.0) for w in weeks_sorted]
    recovery_weeks = [
        getattr(w, "week_number", 0)
        for w in weeks_sorted
        if getattr(w, "is_recovery_week", False)
    ]

    # Race week: find week containing goal date
    race_week = total_weeks
    for week in weeks_sorted:
        week_start = getattr(week, "start_date", None)
        week_end = getattr(week, "end_date", None)
        if isinstance(week_start, str):
            week_start = date.fromisoformat(week_start)
        if isinstance(week_end, str):
            week_end = date.fromisoformat(week_end)
        if week_start and week_end and week_start <= goal_date <= week_end:
            race_week = getattr(week, "week_number", total_weeks)
            break

    return PlanStructureExport(
        total_weeks=total_weeks,
        goal_type=str(goal_type),
        race_week=race_week,
        phases=phases,
        weekly_volumes_km=weekly_volumes_km,
        recovery_weeks=recovery_weeks,
    )


def build_macro_template(total_weeks: int) -> Union[dict, PlanError]:
    """Build a blank macro plan template with required fields.

    The template uses null placeholders that must be filled by the AI coach
    before calling create-macro.
    """
    if not isinstance(total_weeks, int) or total_weeks <= 0:
        return PlanError(error_type="validation", message="total_weeks must be a positive integer")

    return {
        "template_version": "macro_template_v1",
        "total_weeks": total_weeks,
        "weekly_volumes_km": [None] * total_weeks,
        "target_systemic_load_au": [None] * total_weeks,
        "workout_structure_hints": [
            {
                "quality": {"max_sessions": None, "types": None},
                "long_run": {"emphasis": None, "pct_range": [None, None]},
                "intensity_balance": {"low_intensity_pct": None},
            }
            for _ in range(total_weeks)
        ],
    }


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
    baseline_vdot: Optional[float] = None,
    weekly_volumes_km: Optional[list[float]] = None,
    weekly_systemic_load_au: Optional[list[float]] = None,
    weekly_structure_hints: Optional[list[dict]] = None,
) -> Union["MasterPlan", PlanError]:
    """
    Create training plan skeleton with stub weeks.

    Stub weeks contain structural data:
    - Week number, phase, start/end dates
    - Target volume (AI-supplied progression)
    - Macro workout_structure_hints (AI-supplied)
    - Recovery week flag (every 4th week in base/build)
    - Empty workouts list (filled progressively via populate)

    IMPORTANT: This function does NOT generate workout structure hints.
    The AI Coach must supply weekly_structure_hints (macro-level guidance)
    via CLI input. Detailed weekly structure is created progressively by the
    AI Coach via weekly-plan generation.

    Args:
        goal_type: Race distance ("5k", "10k", "half_marathon", "marathon")
        race_date: Goal race date
        target_time: Target finish time (optional, e.g., "1:30:00")
        total_weeks: Total weeks in plan
        start_date: Plan start date (should be Monday)
        current_ctl: CTL at plan creation
        baseline_vdot: Approved baseline VDOT (optional but recommended)
        weekly_volumes_km: Explicit weekly volume targets (AI coach computed)
        weekly_systemic_load_au: Total systemic load targets (optional; for multi-sport athletes)
        weekly_structure_hints: Macro-level workout structure hints (AI coach computed)

    Returns:
        MasterPlan: Plan skeleton with stub weeks (0 weeks populated)
        PlanError: If generation fails

    Example:
        >>> plan = create_macro_plan(
        ...     goal_type="half_marathon",
        ...     race_date=date(2026, 5, 3),
        ...     target_time="1:30:00",
        ...     total_weeks=16,
        ...     start_date=date(2026, 1, 20),
        ...     current_ctl=44.0,
        ...     baseline_vdot=48.0,
        ...     weekly_volumes_km=[25.0] * 16,
        ...     weekly_structure_hints=[{
        ...         "quality": {"max_sessions": 1, "types": ["strides_only"]},
        ...         "long_run": {"emphasis": "steady", "pct_range": [24, 30]},
        ...         "intensity_balance": {"low_intensity_pct": 0.90}
        ...     }] * 16,
        ... )
        >>> len(plan.weeks)
        16  # All stub weeks with volume targets
        >>> len(plan.weeks[0].workouts)
        0  # No workouts yet - filled via populate
    """
    try:
        # Import here to avoid circular dependency
        from sports_coach_engine.core.repository import RepositoryIO
        from sports_coach_engine.core.plan import persist_plan
        from sports_coach_engine.schemas.plan import GoalType, MasterPlan, WeekPlan, WorkoutStructureHints
        from datetime import timedelta
        import uuid

        # Validate goal type and convert to enum
        goal_type_lower = goal_type.lower().replace("-", "_").replace(" ", "_")
        if goal_type_lower not in [g.value for g in GoalType]:
            return PlanError(
                error_type="validation",
                message=f"Invalid goal type: {goal_type}. Valid: 5k, 10k, half_marathon, marathon"
            )

        # Convert string to GoalType enum
        goal_type_enum = GoalType(goal_type_lower)

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

        # Create phase structure
        phases = _create_phase_structure(total_weeks)

        # Strict CLI-only: AI coach must supply weekly volume targets
        if not weekly_volumes_km:
            return PlanError(
                error_type="validation",
                message="weekly_volumes_km is required (AI coach must supply weekly targets)"
            )
        if len(weekly_volumes_km) != total_weeks:
            return PlanError(
                error_type="validation",
                message=f"weekly_volumes_km length {len(weekly_volumes_km)} != total_weeks {total_weeks}"
            )
        for idx, value in enumerate(weekly_volumes_km, start=1):
            if not isinstance(value, (int, float)) or value <= 0:
                return PlanError(
                    error_type="validation",
                    message=f"weekly_volumes_km[{idx}] must be a positive number"
                )

        # Derive starting/peak from template (single source of truth)
        starting_volume_km = weekly_volumes_km[0]
        peak_volume_km = max(weekly_volumes_km)

        # Validate weekly_systemic_load_au if provided (for multi-sport athletes)
        if weekly_systemic_load_au is not None:
            if len(weekly_systemic_load_au) != total_weeks:
                return PlanError(
                    error_type="validation",
                    message=f"weekly_systemic_load_au length {len(weekly_systemic_load_au)} != total_weeks {total_weeks}"
                )
            for idx, value in enumerate(weekly_systemic_load_au, start=1):
                if not isinstance(value, (int, float)) or value < 0:
                    return PlanError(
                        error_type="validation",
                        message=f"weekly_systemic_load_au[{idx}] must be a non-negative number"
                    )

        # Strict CLI-only: AI coach must supply workout structure hints
        if not weekly_structure_hints:
            return PlanError(
                error_type="validation",
                message="weekly_structure_hints is required (AI coach must supply workout structure hints)"
            )
        if len(weekly_structure_hints) != total_weeks:
            return PlanError(
                error_type="validation",
                message=f"weekly_structure_hints length {len(weekly_structure_hints)} != total_weeks {total_weeks}"
            )

        validated_hints: list[WorkoutStructureHints] = []
        for idx, hint in enumerate(weekly_structure_hints, start=1):
            try:
                validated_hints.append(WorkoutStructureHints.model_validate(hint))
            except Exception as e:
                return PlanError(
                    error_type="validation",
                    message=f"weekly_structure_hints[{idx}] invalid: {str(e)}"
                )

        # Create week-to-phase mapping
        week_to_phase = {}
        for phase_dict in phases:
            for week_num in range(phase_dict["start_week"], phase_dict["end_week"] + 1):
                week_to_phase[week_num] = phase_dict["phase"]

        # Create stub weeks WITHOUT automatic volume calculation
        # AI Coach will determine volumes using guardrails during macro planning:
        # - sce guardrails safe-volume (CTL-based capacity)
        # - sce guardrails analyze-progression (phase-aware progression rates)
        # - Training methodology (Pfitzinger phase rates, minimum volume constraints)
        stub_weeks = []
        for week_num in range(1, total_weeks + 1):
            week_start = start_date + timedelta(weeks=week_num - 1)
            week_end = week_start + timedelta(days=6)

            # Weekly target volume from AI-provided list
            target_volume = weekly_volumes_km[week_num - 1]
            structure_hints = validated_hints[week_num - 1]

            # Weekly target systemic load (from template for multi-sport, 0.0 for single-sport)
            target_systemic = weekly_systemic_load_au[week_num - 1] if weekly_systemic_load_au else 0.0

            # Determine phase
            phase = week_to_phase.get(week_num, "base")

            # Recovery week flag for metadata only (AI Coach uses this context)
            is_recovery = (week_num % 4 == 0) and phase in ["base", "build"]

            # Create stub week with structural data + macro-level workout structure hints
            stub_week = WeekPlan(
                week_number=week_num,
                phase=phase,
                start_date=week_start,
                end_date=week_end,
                target_volume_km=target_volume,
                target_systemic_load_au=target_systemic,  # From template (multi-sport) or 0.0 (single-sport)
                workout_structure_hints=structure_hints,
                workouts=[],  # Empty - filled via populate
                is_recovery_week=is_recovery,
                notes=f"{phase.capitalize()} phase"  # Simple phase label
            )
            stub_weeks.append(stub_week)

        # Create MasterPlan with stub weeks
        plan = MasterPlan(
            id=f"plan_{uuid.uuid4().hex[:12]}",
            created_at=date.today(),
            goal={
                "type": goal_type_enum.value,
                "target_date": str(race_date),
                "target_time": target_time
            },
            start_date=start_date,
            end_date=race_date,
            total_weeks=total_weeks,
            phases=phases,
            weeks=stub_weeks,  # Stub weeks with volume targets
            starting_volume_km=starting_volume_km,
            peak_volume_km=peak_volume_km,
            baseline_vdot=baseline_vdot,
            current_vdot=baseline_vdot,
            vdot_history=[],
            plan_state=None,
            constraints_applied=[],
            conflict_policy="running_goal_wins"
        )

        # Persist to disk
        repo = RepositoryIO()
        persist_plan(plan, repo)

        return plan

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


def _create_phase_structure(total_weeks: int) -> list[dict]:
    """Create phase boundaries based on total weeks."""
    if total_weeks <= 4:
        return [
            {"phase": "base", "start_week": 1, "end_week": total_weeks - 1},
            {"phase": "taper", "start_week": total_weeks, "end_week": total_weeks}
        ]
    elif total_weeks <= 8:
        mid = total_weeks // 2
        return [
            {"phase": "base", "start_week": 1, "end_week": mid},
            {"phase": "build", "start_week": mid + 1, "end_week": total_weeks - 1},
            {"phase": "taper", "start_week": total_weeks, "end_week": total_weeks}
        ]
    else:
        base_end = total_weeks // 3
        build_end = 2 * total_weeks // 3
        return [
            {"phase": "base", "start_week": 1, "end_week": base_end},
            {"phase": "build", "start_week": base_end + 1, "end_week": build_end},
            {"phase": "peak", "start_week": build_end + 1, "end_week": total_weeks - 2},
            {"phase": "taper", "start_week": total_weeks - 1, "end_week": total_weeks}
        ]


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
    target_volumes_km: list[float],
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
        target_volumes_km: List of weekly volume targets (AI-designed, one per week)
        macro_plan: Macro plan dict with phases and recovery weeks
        current_vdot: Current VDOT value (30.0-85.0)
        profile: Athlete profile dict with constraints, sports, preferences
        volume_adjustment: Multiplier for volume targets (0.5-1.5 reasonable range)

    Returns:
        Dict with monthly plan or PlanError

    Example:
        >>> result = generate_month_plan(
        ...     month_number=1,
        ...     week_numbers=[1, 2, 3, 4],
        ...     target_volumes_km=[25.0, 27.5, 30.0, 21.0],
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

    # Validate target_volumes_km
    if not isinstance(target_volumes_km, list):
        return PlanError(
            error_type="validation",
            message="target_volumes_km must be a list"
        )

    if len(target_volumes_km) != len(week_numbers):
        return PlanError(
            error_type="validation",
            message=f"target_volumes_km length ({len(target_volumes_km)}) must match week_numbers length ({len(week_numbers)})"
        )

    for i, vol in enumerate(target_volumes_km):
        if not (5.0 <= vol <= 200.0):
            return PlanError(
                error_type="validation",
                message=f"target_volumes_km[{i}] = {vol}km is outside reasonable range (5-200km)"
            )

    # Validate macro plan has required fields
    if not isinstance(macro_plan, dict):
        return PlanError(
            error_type="validation",
            message="macro_plan must be a dict"
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
            target_volumes_km=target_volumes_km,
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


# ============================================================
# RUN COUNT SUGGESTION (Intelligent session determination)
# ============================================================


def _score_run_distribution(
    avg_easy: float,
    long_km: float,
    total_km: float,
    easy_min: float,
    long_min: float
) -> float:
    """Score a run distribution (higher is better).

    Factors:
    - Easy runs comfortably above minimum (not at boundary)
    - Long run is substantial but not excessive (40-50% of weekly)
    - Even distribution (not too lumpy)

    Args:
        avg_easy: Average easy run distance
        long_km: Long run distance
        total_km: Total weekly volume
        easy_min: Minimum easy run distance
        long_min: Minimum long run distance

    Returns:
        Score (higher is better)
    """
    score = 100.0

    # Penalize if easy runs below minimum
    if avg_easy < easy_min:
        score -= (easy_min - avg_easy) * 10

    # Penalize if easy runs WAY above minimum (inefficient)
    if avg_easy > easy_min + 3:
        score -= (avg_easy - easy_min - 3) * 2

    # Reward if easy runs in sweet spot (min + 1km to min + 2km)
    if easy_min + 1 <= avg_easy <= easy_min + 2:
        score += 20

    # Long run percentage
    long_pct = long_km / total_km if total_km > 0 else 0

    # Penalize if long run too small (<35%)
    if long_pct < 0.35:
        score -= (0.35 - long_pct) * 100

    # Penalize if long run too large (>55%)
    if long_pct > 0.55:
        score -= (long_pct - 0.55) * 100

    # Reward if long run in sweet spot (40-50%)
    if 0.40 <= long_pct <= 0.50:
        score += 15

    return score


def suggest_optimal_run_count(
    target_volume_km: float,
    max_runs: int,
    phase: str = "base",
    profile: Optional[dict] = None
) -> dict:
    """Suggest optimal number of running sessions for weekly volume.

    Args:
        target_volume_km: Weekly volume target
        max_runs: Maximum runs from athlete profile
        phase: Training phase (affects long run %)
        profile: Athlete profile (for historical minimums)

    Returns:
        Dict with recommendation and rationale containing:
        - target_volume_km: Input volume
        - max_runs: Input max runs
        - phase: Input phase
        - recommended_runs: Optimal number of runs
        - rationale: Human-readable explanation
        - distribution_preview: Preview of each option
        - minimum_volume_for_max_runs: Min km needed for max runs
        - comfortable_volume_for_max_runs: Comfortable km for max runs
        - easy_min_km: Minimum easy run distance used
        - long_min_km: Minimum long run distance used
    """
    # Get minimums (from profile if available, else defaults)
    easy_min = 5.0
    long_min = 8.0

    if profile:
        # Use 80% of athlete's typical distances as minimum
        # IMPORTANT: If these are missing, the calling code (skills) should:
        # 1. Try `sce profile analyze` to detect from Strava activities
        # 2. If still missing, ask athlete directly using AskUserQuestion
        # 3. Never proceed with hardcoded defaults - that's poor coaching
        typical_easy = profile.get("typical_easy_distance_km")
        typical_long = profile.get("typical_long_run_distance_km")

        if typical_easy is None or typical_long is None:
            # WARNING: Missing athlete-specific workout patterns
            # Skills should handle this proactively, but we'll use conservative defaults
            # to prevent blocking plan generation during testing/development
            easy_min = 5.0 * 0.8  # Conservative default, should be personalized
            long_min = 8.0 * 0.8  # Conservative default, should be personalized
        else:
            easy_min = typical_easy * 0.8
            long_min = typical_long * 0.8

    # Long run percentage varies by phase
    long_run_pct = {
        "base": 0.45,
        "build": 0.48,
        "peak": 0.50,
        "taper": 0.40,
        "recovery": 0.50
    }.get(phase, 0.45)

    # Calculate for each possible run count
    options = []
    for num_runs in range(2, max_runs + 1):
        # Calculate long run
        long_km = round(target_volume_km * long_run_pct * 2) / 2
        long_km = max(long_km, long_min)  # Enforce minimum

        # Calculate easy runs
        num_easy = num_runs - 1
        remaining_km = target_volume_km - long_km

        if remaining_km < 0:
            # Volume too low for even one long run
            continue

        avg_easy = remaining_km / num_easy if num_easy > 0 else 0

        # Check concerns
        concerns = []
        if avg_easy < easy_min and num_easy > 0:
            concerns.append(f"Easy runs below {easy_min:.1f}km minimum")
        if long_km > target_volume_km * 0.55:
            concerns.append(f"Long run >55% of weekly volume")

        # Calculate distribution preview
        easy_distances = []
        if num_easy > 0:
            for i in range(num_easy - 1):
                easy_distances.append(round(avg_easy * 2) / 2)
            # Last easy adjusts for exact sum
            last_easy = remaining_km - sum(easy_distances)
            easy_distances.append(round(last_easy * 2) / 2)

        options.append({
            "num_runs": num_runs,
            "easy": easy_distances,
            "long": long_km,
            "avg_easy": round(avg_easy, 1),
            "concerns": concerns,
            "score": _score_run_distribution(avg_easy, long_km, target_volume_km, easy_min, long_min)
        })

    # Choose best option (highest score without major concerns)
    viable_options = [opt for opt in options if not opt["concerns"]]
    if not viable_options:
        # No perfect option, choose least bad
        viable_options = sorted(options, key=lambda x: len(x["concerns"]))

    # Sort by score
    recommended = max(viable_options, key=lambda x: x["score"])

    # Build distribution preview for comparison
    distribution_preview = {}
    for opt in options:
        key = f"with_{opt['num_runs']}_runs"
        distribution_preview[key] = {
            "easy": opt["easy"],
            "long": opt["long"],
            "avg_easy": opt["avg_easy"],
            "concerns": opt["concerns"]
        }

    # Build rationale
    rationale_parts = []
    rationale_parts.append(
        f"{target_volume_km}km spread across {max_runs} runs averages "
        f"{target_volume_km / max_runs:.1f}km per run."
    )

    max_runs_opt = next((o for o in options if o["num_runs"] == max_runs), None)
    if max_runs_opt and max_runs_opt["concerns"]:
        rationale_parts.append(
            f"With {max_runs} runs: {', '.join(max_runs_opt['concerns'])}."
        )

    rationale_parts.append(
        f"Recommend {recommended['num_runs']} runs: "
        f"{len(recommended['easy'])}×{recommended['avg_easy']:.1f}km easy + "
        f"{recommended['long']}km long for more substantial sessions."
    )

    rationale = " ".join(rationale_parts)

    # Calculate minimum/comfortable volumes for max_runs
    minimum_volume = (max_runs - 1) * easy_min + long_min
    comfortable_volume = minimum_volume + (max_runs * 1.0)  # Add 1km buffer per run

    return {
        "target_volume_km": target_volume_km,
        "max_runs": max_runs,
        "phase": phase,
        "recommended_runs": recommended["num_runs"],
        "rationale": rationale,
        "distribution_preview": distribution_preview,
        "minimum_volume_for_max_runs": round(minimum_volume, 1),
        "comfortable_volume_for_max_runs": round(comfortable_volume, 1),
        "easy_min_km": round(easy_min, 1),
        "long_min_km": round(long_min, 1)
    }


def validate_week_plan(
    weekly_plan_path: str,
    verbose: bool = False
) -> Union[dict, PlanError]:
    """
    Validate a single week's workout plan before saving.

    Checks for:
    - JSON structure and required fields
    - Volume discrepancy (<5% acceptable, >10% regenerate)
    - Minimum duration violations (easy ≥5km, long ≥8km)
    - Quality volume limits (T≤10%, I≤8%, R≤5%)
    - Date alignment (start=Monday, end=Sunday)
    - workout_pattern field presence (intent-based format required)

    Args:
        weekly_plan_path: Path to weekly plan JSON file
        verbose: Show detailed validation output

    Returns:
        dict: Validation result
        {
            "is_valid": bool,
            "errors": list[str],
            "warnings": list[str],
            "summary": str
        }

        PlanError on failure

    Example:
        >>> result = validate_week_plan("/tmp/weekly_plan_w1.json")
        >>> result["is_valid"]
        True
    """
    from pathlib import Path
    import json
    from datetime import datetime

    # Load weekly plan
    plan_path = Path(weekly_plan_path)
    if not plan_path.exists():
        return PlanError(
            error_type="not_found",
            message=f"Weekly plan file not found: {weekly_plan_path}"
        )

    try:
        with open(plan_path, 'r') as f:
            plan_data = json.load(f)
    except json.JSONDecodeError as e:
        return PlanError(
            error_type="validation",
            message=f"Invalid JSON: {str(e)}"
        )

    # Extract weeks array
    if "weeks" not in plan_data:
        return PlanError(
            error_type="validation",
            message="JSON must contain 'weeks' array"
        )

    weeks = plan_data["weeks"]
    if len(weeks) != 1:
        return PlanError(
            error_type="validation",
            message=f"Weekly plan must contain exactly 1 week, found {len(weeks)}"
        )

    week = weeks[0]
    errors = []
    warnings = []

    # Check required fields
    required_fields = [
        "week_number",
        "phase",
        "start_date",
        "end_date",
        "target_volume_km",
        "target_systemic_load_au",
    ]
    for field in required_fields:
        if field not in week:
            errors.append(f"Missing required field: '{field}'")

    # Check for explicit workouts (required)
    if "workouts" not in week:
        errors.append(
            "Missing 'workouts' field. Provide explicit workout array (AI Coach designs all workouts)."
        )
    else:
        # Validate explicit format using helper
        validation_result = _validate_explicit_workouts(week)
        errors.extend([e["message"] for e in validation_result.errors])
        warnings.extend([w["message"] for w in validation_result.warnings])

    # Check date alignment
    if "start_date" in week and "end_date" in week:
        try:
            start = datetime.fromisoformat(week["start_date"]).date()
            end = datetime.fromisoformat(week["end_date"]).date()

            if start.weekday() != 0:
                errors.append(
                    f"start_date must be Monday, got {start.strftime('%A')}"
                )

            if end.weekday() != 6:
                errors.append(
                    f"end_date must be Sunday, got {end.strftime('%A')}"
                )
        except ValueError as e:
            errors.append(f"Invalid date format: {e}")

    # Check phase is valid
    if "phase" in week:
        valid_phases = ["base", "build", "peak", "taper", "recovery"]
        if week["phase"] not in valid_phases:
            errors.append(
                f"Invalid phase '{week['phase']}', must be one of: {', '.join(valid_phases)}"
            )

    is_valid = len(errors) == 0
    summary = "Weekly plan validation passed" if is_valid else f"Found {len(errors)} error(s)"

    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "summary": summary
    }


def revert_week_plan(week_number: int) -> Union[dict, PlanError]:
    """
    Revert a week's plan to macro plan targets (remove detailed workouts).

    Removes workout_pattern field from specified week, leaving only target_volume_km.
    Useful for rolling back a week to allow regeneration with different parameters.

    Workflow:
    1. Load current plan
    2. Find specified week
    3. Remove workout_pattern and workouts fields
    4. Keep only target_volume_km, phase, dates, notes
    5. Save updated plan

    Args:
        week_number: Week number to revert (1-indexed)

    Returns:
        dict: Confirmation with week details
        {
            "week_number": 3,
            "reverted_to_target": 30.0,
            "message": "Week 3 reverted to macro plan targets"
        }

        PlanError on failure

    Example:
        >>> result = revert_week_plan(week_number=3)
        >>> result["message"]
        "Week 3 reverted to macro plan targets"
    """
    repo = RepositoryIO()

    # Load current plan
    plan_path = current_plan_path()
    result = repo.read_yaml(plan_path, MasterPlan, ReadOptions(should_validate=True))

    if result is None:
        return PlanError(
            error_type="not_found",
            message="No plan found. Run 'sce plan regen' first."
        )

    if isinstance(result, RepoError):
        return PlanError(
            error_type="validation",
            message=f"Failed to load plan: {str(result)}"
        )

    plan = result

    # Find specified week
    week_to_revert = None
    for week in plan.weeks:
        if week.week_number == week_number:
            week_to_revert = week
            break

    if not week_to_revert:
        return PlanError(
            error_type="not_found",
            message=f"Week {week_number} not found in plan"
        )

    # Store target volume before modification
    target_volume = week_to_revert.target_volume_km

    # Revert week by clearing workouts
    week_to_revert.workouts = []

    # Save updated plan
    write_result = repo.write_yaml(plan_path, plan)
    if isinstance(write_result, RepoError):
        return PlanError(
            error_type="unknown",
            message=f"Failed to save plan: {str(write_result)}"
        )

    return {
        "week_number": week_number,
        "reverted_to_target": target_volume,
        "message": f"Week {week_number} reverted to macro plan targets (workouts removed). Can regenerate with different parameters."
    }
