"""
sce goal - Manage race goals.

Set a race goal and automatically validate feasibility.
"""

from datetime import datetime
from typing import Optional, Dict, Any

import typer

from sports_coach_engine.api import set_goal
from sports_coach_engine.api.metrics import get_current_metrics, MetricsError
from sports_coach_engine.api.vdot import estimate_current_vdot, calculate_vdot_from_race, VDOTError
from sports_coach_engine.api.validation import api_assess_goal_feasibility, ValidationError
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, output_json

# Create subcommand app
app = typer.Typer(help="Manage race goals")


@app.command(name="set")
def goal_set_command(
    ctx: typer.Context,
    race_type: str = typer.Option(
        ...,
        "--type",
        help="Race type: 5k, 10k, half_marathon, or marathon",
    ),
    target_date: str = typer.Option(
        ...,
        "--date",
        help="Race date (YYYY-MM-DD)",
    ),
    target_time: Optional[str] = typer.Option(
        None,
        "--time",
        help="Target finish time (HH:MM:SS), optional",
    ),
) -> None:
    """Set a new race goal with automatic feasibility validation.

    Sets a race goal and validates feasibility based on current fitness (VDOT, CTL)
    and time available for training.

    Valid race types:
    - 5k
    - 10k
    - half_marathon
    - marathon

    Examples:
        sce goal set --type 10k --date 2026-06-01
        sce goal set --type half_marathon --date 2026-04-15 --time 01:45:00
        sce goal set --type marathon --date 2026-10-20 --time 03:30:00
    """
    # Parse target_date
    try:
        date_obj = datetime.fromisoformat(target_date).date()
    except ValueError:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid date format: {target_date}. Use YYYY-MM-DD.",
        )
        output_json(envelope)
        raise typer.Exit(code=5)  # Validation error

    # Validate race_type
    valid_race_types = ["5k", "10k", "half_marathon", "marathon"]
    if race_type not in valid_race_types:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid race type: {race_type}. Valid types: {', '.join(valid_race_types)}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)  # Validation error

    # Validate target_time format if provided and convert to seconds
    goal_time_seconds: Optional[int] = None
    if target_time:
        # Expected format: HH:MM:SS
        parts = target_time.split(":")
        if len(parts) != 3:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid time format: {target_time}. Use HH:MM:SS (e.g., 01:45:00)",
            )
            output_json(envelope)
            raise typer.Exit(code=5)  # Validation error

        try:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                raise ValueError
            goal_time_seconds = hours * 3600 + minutes * 60 + seconds
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid time values: {target_time}. Use valid HH:MM:SS.",
            )
            output_json(envelope)
            raise typer.Exit(code=5)  # Validation error

    # 1. Get current metrics (CTL)
    metrics_result = get_current_metrics()
    current_ctl = 0.0
    if not isinstance(metrics_result, MetricsError):
        current_ctl = metrics_result.ctl.value

    # 2. Estimate current VDOT (if available)
    vdot_result = estimate_current_vdot(lookback_days=28)
    current_vdot: Optional[int] = None
    if not isinstance(vdot_result, VDOTError):
        current_vdot = vdot_result.estimated_vdot

    # 3. Calculate required VDOT (if target_time provided)
    vdot_for_goal: Optional[int] = None
    if target_time and goal_time_seconds:
        # Map race_type to race distance for VDOT calculation
        race_distance_map = {
            "5k": "5k",
            "10k": "10k",
            "half_marathon": "half_marathon",
            "marathon": "marathon",
        }
        race_distance = race_distance_map[race_type]

        vdot_calc_result = calculate_vdot_from_race(
            race_distance=race_distance,
            race_time=target_time,
        )

        if not isinstance(vdot_calc_result, VDOTError):
            vdot_for_goal = vdot_calc_result.vdot

    # 4. Assess goal feasibility (if target_time provided)
    validation_data: Optional[Dict[str, Any]] = None
    if target_time and goal_time_seconds and vdot_for_goal:
        feasibility_result = api_assess_goal_feasibility(
            goal_type=race_type,
            goal_time_seconds=goal_time_seconds,
            goal_date=date_obj,
            current_vdot=current_vdot,
            current_ctl=current_ctl,
            vdot_for_goal=vdot_for_goal,
        )

        if not isinstance(feasibility_result, ValidationError):
            # Extract key fields from feasibility assessment
            vdot_gap = feasibility_result.goal_fitness_needed.vdot_gap
            vdot_gap_pct = None
            if vdot_gap and current_vdot and current_vdot > 0:
                vdot_gap_pct = (vdot_gap / current_vdot) * 100

            validation_data = {
                "feasibility_verdict": feasibility_result.feasibility_verdict,
                "confidence_level": feasibility_result.confidence_level,
                "vdot_gap": vdot_gap,
                "vdot_gap_percentage": vdot_gap_pct,
                "weeks_available": feasibility_result.time_available.weeks_until_race,
                "current_vdot": current_vdot,
                "required_vdot": vdot_for_goal,
                "current_ctl": current_ctl,
                "recommendations": feasibility_result.recommendations,
                "warnings": feasibility_result.warnings,
            }

    # 5. Set goal (save to profile)
    result = set_goal(
        race_type=race_type,
        target_date=date_obj,
        target_time=target_time,
    )

    # 6. Build combined response
    if hasattr(result, 'type'):  # Goal object successfully created
        base_msg = f"Goal set: {race_type} on {target_date}"
        if target_time:
            base_msg += f" (target: {target_time})"

        # Add feasibility verdict to message if available
        if validation_data:
            verdict = validation_data['feasibility_verdict']
            base_msg += f" - {verdict}"

        # Create success envelope with combined data
        envelope = {
            "status": "success",
            "message": base_msg,
            "data": {
                "goal": {
                    "race_type": race_type,
                    "target_date": target_date,
                    "target_time": target_time,
                },
                "validation": validation_data,
            },
        }
    else:
        # Goal creation failed
        envelope = api_result_to_envelope(
            result,
            success_message=f"Set goal: {race_type} on {target_date}",
        )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="validate")
def goal_validate_command(
    ctx: typer.Context,
) -> None:
    """Validate existing goal feasibility without setting a new goal.

    Re-validates the current goal from profile against current fitness.
    Useful for periodic checks during training:
    - Weekly planning: "Are we still on track?"
    - Race prep: "Is the goal still realistic given taper?"
    - After illness/injury: "Is goal still achievable?"

    Examples:
        sce goal validate
    """
    from sports_coach_engine.api.profile import get_profile, ProfileError

    # 1. Get goal from profile
    profile_result = get_profile()

    if isinstance(profile_result, ProfileError):
        envelope = create_error_envelope(
            error_type="not_found",
            message="Profile not found. Create a profile first using 'sce profile create'.",
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    if not profile_result.goal or not profile_result.goal.target_date:
        envelope = create_error_envelope(
            error_type="validation",
            message="No goal set in profile. Use 'sce goal set' to set a goal first.",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    goal = profile_result.goal
    race_type = goal.type.value
    target_date_str = goal.target_date
    target_time = goal.target_time

    # Parse target_date
    try:
        date_obj = datetime.fromisoformat(target_date_str).date()
    except ValueError:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid goal date in profile: {target_date_str}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # If no target_time, can't validate pace goal
    if not target_time:
        envelope = {
            "status": "success",
            "message": f"Goal: {race_type} on {target_date_str} (no target time set - cannot validate pace goal)",
            "data": {
                "goal": {
                    "race_type": race_type,
                    "target_date": target_date_str,
                    "target_time": None,
                },
                "validation": None,
            },
        }
        output_json(envelope)
        raise typer.Exit(code=0)

    # Parse target_time to seconds
    try:
        parts = target_time.split(":")
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        goal_time_seconds = hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid goal time in profile: {target_time}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # 2. Get current metrics (CTL)
    metrics_result = get_current_metrics()
    current_ctl = 0.0
    if not isinstance(metrics_result, MetricsError):
        current_ctl = metrics_result.ctl.value

    # 3. Estimate current VDOT
    vdot_result = estimate_current_vdot(lookback_days=28)
    current_vdot: Optional[int] = None
    if not isinstance(vdot_result, VDOTError):
        current_vdot = vdot_result.estimated_vdot

    # 4. Calculate required VDOT
    race_distance_map = {
        "5k": "5k",
        "10k": "10k",
        "half_marathon": "half_marathon",
        "marathon": "marathon",
    }
    race_distance = race_distance_map.get(race_type, race_type)

    vdot_calc_result = calculate_vdot_from_race(
        race_distance=race_distance,
        race_time=target_time,
    )

    vdot_for_goal: Optional[int] = None
    if not isinstance(vdot_calc_result, VDOTError):
        vdot_for_goal = vdot_calc_result.vdot

    if not vdot_for_goal:
        envelope = create_error_envelope(
            error_type="calculation_failed",
            message=f"Unable to calculate required VDOT for goal: {target_time}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # 5. Assess goal feasibility
    feasibility_result = api_assess_goal_feasibility(
        goal_type=race_type,
        goal_time_seconds=goal_time_seconds,
        goal_date=date_obj,
        current_vdot=current_vdot,
        current_ctl=current_ctl,
        vdot_for_goal=vdot_for_goal,
    )

    if isinstance(feasibility_result, ValidationError):
        envelope = create_error_envelope(
            error_type="calculation_failed",
            message=f"Feasibility assessment failed: {feasibility_result.message}",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # 6. Build response
    vdot_gap = feasibility_result.goal_fitness_needed.vdot_gap
    vdot_gap_pct = None
    if vdot_gap and current_vdot and current_vdot > 0:
        vdot_gap_pct = (vdot_gap / current_vdot) * 100

    validation_data = {
        "feasibility_verdict": feasibility_result.feasibility_verdict,
        "confidence_level": feasibility_result.confidence_level,
        "vdot_gap": vdot_gap,
        "vdot_gap_percentage": vdot_gap_pct,
        "weeks_available": feasibility_result.time_available.weeks_until_race,
        "current_vdot": current_vdot,
        "required_vdot": vdot_for_goal,
        "current_ctl": current_ctl,
        "recommendations": feasibility_result.recommendations,
        "warnings": feasibility_result.warnings,
    }

    verdict = validation_data['feasibility_verdict']
    base_msg = f"Goal validation: {race_type} {target_time} on {target_date_str} - {verdict}"

    envelope = {
        "status": "success",
        "message": base_msg,
        "data": {
            "goal": {
                "race_type": race_type,
                "target_date": target_date_str,
                "target_time": target_time,
            },
            "validation": validation_data,
        },
    }

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    raise typer.Exit(code=0)
