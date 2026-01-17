"""API layer for validation functions.

Provides validation with input sanitization and error handling:
- api_validate_interval_structure()
- api_validate_plan_structure()
- api_assess_goal_feasibility()
"""

from datetime import date, datetime
from typing import List, Dict, Any, Union, Optional
from sports_coach_engine.core.validation import (
    validate_interval_structure,
    validate_plan_structure,
    assess_goal_feasibility,
)
from sports_coach_engine.schemas.validation import (
    IntervalStructureValidation,
    PlanStructureValidation,
    GoalFeasibilityAssessment,
)


class ValidationError(Exception):
    """Validation function error."""

    def __init__(self, message: str, error_type: str = "VALIDATION_ERROR"):
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)


# ============================================================================
# API: Interval Structure Validation
# ============================================================================


def api_validate_interval_structure(
    workout_type: str,
    intensity: str,
    work_bouts: List[Dict[str, Any]],
    recovery_bouts: List[Dict[str, Any]],
    weekly_volume_km: Optional[float] = None,
) -> Union[IntervalStructureValidation, ValidationError]:
    """Validate interval workout structure per Daniels methodology.

    Args:
        workout_type: Workout type (e.g., "intervals", "tempo", "repetitions")
        intensity: Primary intensity (e.g., "I-pace", "T-pace", "R-pace")
        work_bouts: List of work bout dicts with 'duration_minutes', 'pace_per_km_seconds', 'distance_km'
        recovery_bouts: List of recovery bout dicts with 'duration_minutes', 'type'
        weekly_volume_km: Optional weekly volume for total volume validation

    Returns:
        IntervalStructureValidation or ValidationError
    """
    # Validate inputs
    if not workout_type or not isinstance(workout_type, str):
        return ValidationError("workout_type must be a non-empty string", "INVALID_WORKOUT_TYPE")

    if not intensity or not isinstance(intensity, str):
        return ValidationError("intensity must be a non-empty string", "INVALID_INTENSITY")

    if not isinstance(work_bouts, list) or len(work_bouts) == 0:
        return ValidationError("work_bouts must be a non-empty list", "INVALID_WORK_BOUTS")

    if not isinstance(recovery_bouts, list):
        return ValidationError("recovery_bouts must be a list", "INVALID_RECOVERY_BOUTS")

    # Validate bout structures
    for idx, bout in enumerate(work_bouts, 1):
        if not isinstance(bout, dict):
            return ValidationError(f"work_bout {idx} must be a dict", "INVALID_WORK_BOUT_STRUCTURE")
        if "duration_minutes" not in bout:
            return ValidationError(
                f"work_bout {idx} missing 'duration_minutes'", "MISSING_WORK_BOUT_DURATION"
            )
        if not isinstance(bout["duration_minutes"], (int, float)) or bout["duration_minutes"] <= 0:
            return ValidationError(
                f"work_bout {idx} 'duration_minutes' must be positive number",
                "INVALID_WORK_BOUT_DURATION",
            )

    for idx, bout in enumerate(recovery_bouts, 1):
        if not isinstance(bout, dict):
            return ValidationError(
                f"recovery_bout {idx} must be a dict", "INVALID_RECOVERY_BOUT_STRUCTURE"
            )
        if "duration_minutes" not in bout:
            return ValidationError(
                f"recovery_bout {idx} missing 'duration_minutes'", "MISSING_RECOVERY_BOUT_DURATION"
            )
        if not isinstance(bout["duration_minutes"], (int, float)) or bout["duration_minutes"] < 0:
            return ValidationError(
                f"recovery_bout {idx} 'duration_minutes' must be non-negative number",
                "INVALID_RECOVERY_BOUT_DURATION",
            )

    if weekly_volume_km is not None:
        if not isinstance(weekly_volume_km, (int, float)) or weekly_volume_km <= 0:
            return ValidationError(
                "weekly_volume_km must be a positive number", "INVALID_WEEKLY_VOLUME"
            )

    # Call core function
    try:
        result = validate_interval_structure(
            workout_type=workout_type,
            intensity=intensity,
            work_bouts=work_bouts,
            recovery_bouts=recovery_bouts,
            weekly_volume_km=weekly_volume_km,
        )
        return result
    except Exception as e:
        return ValidationError(f"Validation failed: {str(e)}", "VALIDATION_FAILED")


# ============================================================================
# API: Plan Structure Validation
# ============================================================================


def api_validate_plan_structure(
    total_weeks: int,
    goal_type: str,
    phases: Dict[str, int],
    weekly_volumes_km: List[float],
    recovery_weeks: List[int],
    race_week: int,
) -> Union[PlanStructureValidation, ValidationError]:
    """Validate training plan structure for common errors.

    Args:
        total_weeks: Total number of weeks in plan
        goal_type: Goal race type (e.g., "5k", "10k", "half_marathon", "marathon")
        phases: Dict mapping phase name to number of weeks
        weekly_volumes_km: List of weekly volumes (index 0 = week 1)
        recovery_weeks: List of week numbers designated as recovery
        race_week: Week number of race

    Returns:
        PlanStructureValidation or ValidationError
    """
    # Validate inputs
    if not isinstance(total_weeks, int) or total_weeks <= 0:
        return ValidationError("total_weeks must be a positive integer", "INVALID_TOTAL_WEEKS")

    if not goal_type or not isinstance(goal_type, str):
        return ValidationError("goal_type must be a non-empty string", "INVALID_GOAL_TYPE")

    if not isinstance(phases, dict) or len(phases) == 0:
        return ValidationError("phases must be a non-empty dict", "INVALID_PHASES")

    for phase_name, weeks in phases.items():
        if not isinstance(phase_name, str):
            return ValidationError("phase names must be strings", "INVALID_PHASE_NAME")
        if not isinstance(weeks, int) or weeks <= 0:
            return ValidationError(
                f"phase '{phase_name}' weeks must be a positive integer", "INVALID_PHASE_WEEKS"
            )

    if not isinstance(weekly_volumes_km, list) or len(weekly_volumes_km) == 0:
        return ValidationError(
            "weekly_volumes_km must be a non-empty list", "INVALID_WEEKLY_VOLUMES"
        )

    for idx, vol in enumerate(weekly_volumes_km, 1):
        if not isinstance(vol, (int, float)) or vol < 0:
            return ValidationError(
                f"weekly_volumes_km[{idx-1}] must be a non-negative number", "INVALID_WEEKLY_VOLUME"
            )

    if not isinstance(recovery_weeks, list):
        return ValidationError("recovery_weeks must be a list", "INVALID_RECOVERY_WEEKS")

    for week_num in recovery_weeks:
        if not isinstance(week_num, int) or week_num <= 0:
            return ValidationError(
                "recovery_weeks must contain positive integers", "INVALID_RECOVERY_WEEK"
            )

    if not isinstance(race_week, int) or race_week <= 0:
        return ValidationError("race_week must be a positive integer", "INVALID_RACE_WEEK")

    if race_week > total_weeks:
        return ValidationError(
            f"race_week ({race_week}) exceeds total_weeks ({total_weeks})", "RACE_WEEK_OUT_OF_RANGE"
        )

    # Call core function
    try:
        result = validate_plan_structure(
            total_weeks=total_weeks,
            goal_type=goal_type,
            phases=phases,
            weekly_volumes_km=weekly_volumes_km,
            recovery_weeks=recovery_weeks,
            race_week=race_week,
        )
        return result
    except Exception as e:
        return ValidationError(f"Validation failed: {str(e)}", "VALIDATION_FAILED")


# ============================================================================
# API: Goal Feasibility Assessment
# ============================================================================


def api_assess_goal_feasibility(
    goal_type: str,
    goal_time_seconds: int,
    goal_date: Union[date, str],  # Accept date or ISO string
    current_vdot: Optional[int],
    current_ctl: float,
    vdot_for_goal: Optional[int] = None,
) -> Union[GoalFeasibilityAssessment, ValidationError]:
    """Assess goal feasibility based on VDOT and CTL.

    Args:
        goal_type: Race type (e.g., "5k", "10k", "half_marathon", "marathon")
        goal_time_seconds: Goal time in seconds
        goal_date: Race date (date object or ISO string "YYYY-MM-DD")
        current_vdot: Current VDOT (None if no recent race)
        current_ctl: Current CTL
        vdot_for_goal: VDOT required to achieve goal time (optional)

    Returns:
        GoalFeasibilityAssessment or ValidationError
    """
    # Validate inputs
    if not goal_type or not isinstance(goal_type, str):
        return ValidationError("goal_type must be a non-empty string", "INVALID_GOAL_TYPE")

    if not isinstance(goal_time_seconds, int) or goal_time_seconds <= 0:
        return ValidationError("goal_time_seconds must be a positive integer", "INVALID_GOAL_TIME")

    # Parse goal_date
    if isinstance(goal_date, str):
        try:
            goal_date = datetime.strptime(goal_date, "%Y-%m-%d").date()
        except ValueError:
            return ValidationError(
                "goal_date must be a valid date or ISO string (YYYY-MM-DD)", "INVALID_GOAL_DATE"
            )
    elif not isinstance(goal_date, date):
        return ValidationError("goal_date must be a date object or ISO string", "INVALID_GOAL_DATE")

    # Validate goal_date is in the future
    if goal_date <= date.today():
        return ValidationError("goal_date must be in the future", "GOAL_DATE_IN_PAST")

    if current_vdot is not None:
        if not isinstance(current_vdot, int) or current_vdot <= 0:
            return ValidationError(
                "current_vdot must be a positive integer or None", "INVALID_CURRENT_VDOT"
            )

    if not isinstance(current_ctl, (int, float)) or current_ctl < 0:
        return ValidationError("current_ctl must be a non-negative number", "INVALID_CURRENT_CTL")

    if vdot_for_goal is not None:
        if not isinstance(vdot_for_goal, int) or vdot_for_goal <= 0:
            return ValidationError(
                "vdot_for_goal must be a positive integer or None", "INVALID_VDOT_FOR_GOAL"
            )

    # Call core function
    try:
        result = assess_goal_feasibility(
            goal_type=goal_type,
            goal_time_seconds=goal_time_seconds,
            goal_date=goal_date,
            current_vdot=current_vdot,
            current_ctl=current_ctl,
            vdot_for_goal=vdot_for_goal,
        )
        return result
    except Exception as e:
        return ValidationError(f"Assessment failed: {str(e)}", "ASSESSMENT_FAILED")
