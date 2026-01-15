"""CLI commands for validation operations.

Commands:
- sce validation validate-intervals: Validate interval workout structure
- sce validation validate-plan: Validate training plan structure
- sce validation assess-goal: Assess goal feasibility
"""

import json
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Optional

import typer

from sports_coach_engine.api.validation import (
    api_validate_interval_structure,
    api_validate_plan_structure,
    api_assess_goal_feasibility,
)
from sports_coach_engine.cli.output import create_error_envelope, output_json
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope

app = typer.Typer(help="Validation operations (interval structure, plan structure, goal feasibility)")


# ============================================================================
# validate-intervals command
# ============================================================================


@app.command(name="validate-intervals")
def validate_intervals_command(
    ctx: typer.Context,
    workout_type: str = typer.Option(..., "--type", help="Workout type (e.g., 'intervals', 'tempo')"),
    intensity: str = typer.Option(..., "--intensity", help="Intensity (e.g., 'I-pace', 'T-pace', 'R-pace')"),
    work_bouts_json: str = typer.Option(..., "--work-bouts", help="JSON file with work bouts"),
    recovery_bouts_json: str = typer.Option(..., "--recovery-bouts", help="JSON file with recovery bouts"),
    weekly_volume_km: Optional[float] = typer.Option(None, "--weekly-volume", help="Weekly volume in km (optional)"),
) -> None:
    """Validate interval workout structure per Daniels methodology.

    Checks work/recovery ratios:
    - I-pace: 3-5min work bouts, equal recovery
    - T-pace: 5-15min work bouts, 1min recovery per 5min work
    - R-pace: 30-90sec work bouts, 2-3x recovery

    Example:
        sce validation validate-intervals \\
            --type intervals \\
            --intensity I-pace \\
            --work-bouts work.json \\
            --recovery-bouts recovery.json \\
            --weekly-volume 50
    """
    # Load work bouts
    try:
        work_bouts_path = Path(work_bouts_json)
        if not work_bouts_path.exists():
            envelope = create_error_envelope(
                error_type="invalid_input",
                message=f"Work bouts file not found: {work_bouts_json}",
            )
            output_json(envelope)
            raise typer.Exit(code=get_exit_code_from_envelope(envelope))

        with open(work_bouts_path, "r") as f:
            work_bouts = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=f"Invalid JSON in work bouts file: {e}",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    # Load recovery bouts
    try:
        recovery_bouts_path = Path(recovery_bouts_json)
        if not recovery_bouts_path.exists():
            envelope = create_error_envelope(
                error_type="invalid_input",
                message=f"Recovery bouts file not found: {recovery_bouts_json}",
            )
            output_json(envelope)
            raise typer.Exit(code=get_exit_code_from_envelope(envelope))

        with open(recovery_bouts_path, "r") as f:
            recovery_bouts = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=f"Invalid JSON in recovery bouts file: {e}",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    # Call API
    result = api_validate_interval_structure(
        workout_type=workout_type,
        intensity=intensity,
        work_bouts=work_bouts,
        recovery_bouts=recovery_bouts,
        weekly_volume_km=weekly_volume_km,
    )

    # Build success message
    msg = f"Interval structure validated: {workout_type} ({intensity})"
    if hasattr(result, "daniels_compliance"):
        if result.daniels_compliance:
            msg += " - Daniels compliant ✓"
        else:
            msg += f" - {len(result.violations)} violation(s) found"

    envelope = api_result_to_envelope(result, success_message=msg)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


# ============================================================================
# validate-plan command
# ============================================================================


@app.command(name="validate-plan")
def validate_plan_command(
    ctx: typer.Context,
    total_weeks: int = typer.Option(..., "--total-weeks", help="Total number of weeks in plan"),
    goal_type: str = typer.Option(..., "--goal-type", help="Goal race type (e.g., '5k', 'half_marathon')"),
    phases_json: str = typer.Option(..., "--phases", help="JSON file with phases (dict: phase_name -> weeks)"),
    weekly_volumes_json: str = typer.Option(..., "--weekly-volumes", help="JSON file with weekly volumes (list of km)"),
    recovery_weeks_json: str = typer.Option(..., "--recovery-weeks", help="JSON file with recovery weeks (list of week numbers)"),
    race_week: int = typer.Option(..., "--race-week", help="Week number of race"),
) -> None:
    """Validate training plan structure for common errors.

    Checks:
    - Phase duration appropriateness
    - Volume progression (10% rule)
    - Peak placement (2-3 weeks before race)
    - Recovery week frequency (every 3-4 weeks)
    - Taper structure (gradual volume reduction)

    Example:
        sce validation validate-plan \\
            --total-weeks 20 \\
            --goal-type half_marathon \\
            --phases phases.json \\
            --weekly-volumes volumes.json \\
            --recovery-weeks recovery.json \\
            --race-week 20
    """
    # Load phases
    try:
        phases_path = Path(phases_json)
        if not phases_path.exists():
            envelope = create_error_envelope(
                error_type="invalid_input",
                message=f"Phases file not found: {phases_json}",
            )
            output_json(envelope)
            raise typer.Exit(code=get_exit_code_from_envelope(envelope))

        with open(phases_path, "r") as f:
            phases = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=f"Invalid JSON in phases file: {e}",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    # Load weekly volumes
    try:
        weekly_volumes_path = Path(weekly_volumes_json)
        if not weekly_volumes_path.exists():
            envelope = create_error_envelope(
                error_type="invalid_input",
                message=f"Weekly volumes file not found: {weekly_volumes_json}",
            )
            output_json(envelope)
            raise typer.Exit(code=get_exit_code_from_envelope(envelope))

        with open(weekly_volumes_path, "r") as f:
            weekly_volumes = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=f"Invalid JSON in weekly volumes file: {e}",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    # Load recovery weeks
    try:
        recovery_weeks_path = Path(recovery_weeks_json)
        if not recovery_weeks_path.exists():
            envelope = create_error_envelope(
                error_type="invalid_input",
                message=f"Recovery weeks file not found: {recovery_weeks_json}",
            )
            output_json(envelope)
            raise typer.Exit(code=get_exit_code_from_envelope(envelope))

        with open(recovery_weeks_path, "r") as f:
            recovery_weeks = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=f"Invalid JSON in recovery weeks file: {e}",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    # Call API
    result = api_validate_plan_structure(
        total_weeks=total_weeks,
        goal_type=goal_type,
        phases=phases,
        weekly_volumes_km=weekly_volumes,
        recovery_weeks=recovery_weeks,
        race_week=race_week,
    )

    # Build success message
    msg = f"Plan structure validated: {total_weeks} weeks, {goal_type}"
    if hasattr(result, "overall_quality_score"):
        msg += f" - Quality score: {result.overall_quality_score}/100"
        if len(result.violations) > 0:
            msg += f", {len(result.violations)} violation(s) found"

    envelope = api_result_to_envelope(result, success_message=msg)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


# ============================================================================
# assess-goal command
# ============================================================================


@app.command(name="assess-goal")
def assess_goal_command(
    ctx: typer.Context,
    goal_type: str = typer.Option(..., "--goal-type", help="Race type (e.g., '5k', 'half_marathon')"),
    goal_time: str = typer.Option(..., "--goal-time", help="Goal time (HH:MM:SS or MM:SS)"),
    goal_date: str = typer.Option(..., "--goal-date", help="Race date (YYYY-MM-DD)"),
    current_vdot: Optional[int] = typer.Option(None, "--current-vdot", help="Current VDOT (if known)"),
    current_ctl: float = typer.Option(..., "--current-ctl", help="Current CTL"),
    vdot_for_goal: Optional[int] = typer.Option(None, "--vdot-for-goal", help="VDOT required for goal (if known)"),
) -> None:
    """Assess goal feasibility based on VDOT and CTL.

    Determines if a goal is realistic given:
    - Current fitness (VDOT, CTL)
    - Required fitness for goal
    - Time available for training

    Example:
        sce validation assess-goal \\
            --goal-type half_marathon \\
            --goal-time "1:30:00" \\
            --goal-date "2026-06-01" \\
            --current-vdot 48 \\
            --current-ctl 44.0 \\
            --vdot-for-goal 52
    """
    # Parse goal time
    try:
        time_parts = goal_time.split(":")
        if len(time_parts) == 3:
            # HH:MM:SS
            hours, minutes, seconds = map(int, time_parts)
            goal_time_seconds = hours * 3600 + minutes * 60 + seconds
        elif len(time_parts) == 2:
            # MM:SS
            minutes, seconds = map(int, time_parts)
            goal_time_seconds = minutes * 60 + seconds
        else:
            raise ValueError("Invalid time format")
    except ValueError:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message="goal_time must be in format HH:MM:SS or MM:SS",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    # Parse goal date
    try:
        goal_date_obj = datetime.strptime(goal_date, "%Y-%m-%d").date()
    except ValueError:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message="goal_date must be in format YYYY-MM-DD",
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    # Call API
    result = api_assess_goal_feasibility(
        goal_type=goal_type,
        goal_time_seconds=goal_time_seconds,
        goal_date=goal_date_obj,
        current_vdot=current_vdot,
        current_ctl=current_ctl,
        vdot_for_goal=vdot_for_goal,
    )

    # Build success message
    msg = f"Goal feasibility assessed: {goal_type} in {goal_time}"
    if hasattr(result, "feasibility_verdict"):
        msg += f" - {result.feasibility_verdict}"
        if hasattr(result, "confidence_level"):
            msg += f" (confidence: {result.confidence_level})"

    envelope = api_result_to_envelope(result, success_message=msg)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
