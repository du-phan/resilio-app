"""
Analysis CLI commands - Weekly insights and risk assessment.

Commands:
    sce analysis adherence      - Analyze week adherence
    sce analysis intensity      - Validate 80/20 distribution
    sce analysis gaps           - Detect activity gaps
    sce analysis load           - Analyze multi-sport load
    sce analysis capacity       - Check weekly capacity
    sce risk assess             - Assess current injury risk
    sce risk recovery-window    - Estimate recovery timeline
    sce risk forecast           - Forecast training stress
    sce risk taper-status       - Verify taper progression
"""

import typer
import json
from typing import Optional
from datetime import date

from sports_coach_engine.api import (
    api_analyze_week_adherence,
    api_validate_intensity_distribution,
    api_detect_activity_gaps,
    api_analyze_load_distribution_by_sport,
    api_check_weekly_capacity,
    api_assess_current_risk,
    api_estimate_recovery_window,
    api_forecast_training_stress,
    api_assess_taper_status,
)

from sports_coach_engine.cli.output import output_json
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope

app = typer.Typer(help="Weekly analysis and risk assessment")
risk_app = typer.Typer(help="Risk assessment commands")


# ============================================================
# WEEKLY ANALYSIS COMMANDS
# ============================================================


@app.command(name="adherence")
def adherence_command(
    ctx: typer.Context,
    week_number: int = typer.Option(..., "--week", help="Week number in plan"),
    planned_json: str = typer.Option(..., "--planned", help="JSON file with planned workouts"),
    completed_json: str = typer.Option(..., "--completed", help="JSON file with completed activities"),
) -> None:
    """
    Analyze planned vs actual training adherence.

    Compares planned workouts to completed activities, identifies patterns,
    and provides recommendations for improving adherence.

    Example:
        sce analysis adherence --week 5 \\
            --planned planned_week5.json \\
            --completed completed_week5.json
    """
    try:
        # Load planned workouts
        with open(planned_json, "r") as f:
            planned_workouts = json.load(f)

        # Load completed activities
        with open(completed_json, "r") as f:
            completed_activities = json.load(f)

        result = api_analyze_week_adherence(
            week_number=week_number,
            planned_workouts=planned_workouts,
            completed_activities=completed_activities,
        )

        msg = f"Adherence analysis for Week {week_number} complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


@app.command(name="intensity")
def intensity_command(
    ctx: typer.Context,
    activities_json: str = typer.Option(..., "--activities", help="JSON file with activities"),
    days: int = typer.Option(28, "--days", help="Rolling window in days (default 28)"),
) -> None:
    """
    Validate 80/20 intensity distribution compliance.

    Checks if training follows the 80/20 rule (80% low-intensity, 20% high-intensity)
    and identifies moderate-intensity "gray zone" violations.

    Example:
        sce analysis intensity --activities activities_28d.json --days 28
    """
    try:
        # Load activities
        with open(activities_json, "r") as f:
            activities = json.load(f)

        result = api_validate_intensity_distribution(
            activities=activities,
            date_range_days=days,
        )

        msg = f"80/20 distribution analysis for {days} days complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


@app.command(name="gaps")
def gaps_command(
    ctx: typer.Context,
    activities_json: str = typer.Option(..., "--activities", help="JSON file with activities"),
    min_days: int = typer.Option(7, "--min-days", help="Minimum gap duration to report (default 7)"),
) -> None:
    """
    Detect training breaks/gaps with context.

    Identifies periods without training, analyzes CTL impact, and detects
    potential causes (injury, illness) from activity notes.

    Example:
        sce analysis gaps --activities all_activities.json --min-days 7
    """
    try:
        # Load activities
        with open(activities_json, "r") as f:
            activities = json.load(f)

        result = api_detect_activity_gaps(
            activities=activities,
            min_gap_days=min_days,
        )

        msg = f"Gap analysis complete - {result.total_gaps if not hasattr(result, 'error_type') else 0} gaps found"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


@app.command(name="load")
def load_command(
    ctx: typer.Context,
    activities_json: str = typer.Option(..., "--activities", help="JSON file with activities"),
    days: int = typer.Option(7, "--days", help="Analysis window in days (default 7)"),
    priority: str = typer.Option("equal", "--priority", help="Sport priority: running_primary, equal, other_primary"),
) -> None:
    """
    Analyze multi-sport load distribution.

    Breaks down systemic and lower-body load by sport, checks adherence to
    sport priorities, and identifies fatigue risk from sport conflicts.

    Example:
        sce analysis load --activities week_activities.json \\
            --days 7 --priority equal
    """
    try:
        # Validate priority
        valid_priorities = ["running_primary", "equal", "other_primary"]
        if priority not in valid_priorities:
            envelope = {
                "ok": False,
                "error_type": "invalid_input",
                "message": f"priority must be one of {valid_priorities}",
                "data": None,
            }
            output_json(envelope)
            raise typer.Exit(code=5)

        # Load activities
        with open(activities_json, "r") as f:
            activities = json.load(f)

        result = api_analyze_load_distribution_by_sport(
            activities=activities,
            date_range_days=days,
            sport_priority=priority,
        )

        msg = f"Multi-sport load analysis for {days} days complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


@app.command(name="capacity")
def capacity_command(
    ctx: typer.Context,
    week_number: int = typer.Option(..., "--week", help="Week number in plan"),
    planned_volume: float = typer.Option(..., "--volume", help="Planned weekly volume (km)"),
    planned_load: float = typer.Option(..., "--load", help="Planned systemic load (AU)"),
    historical_json: str = typer.Option(..., "--historical", help="JSON file with historical activities"),
) -> None:
    """
    Validate planned volume against proven capacity.

    Checks if planned volume exceeds historical maximum and assesses risk
    of attempting unproven training volumes.

    Example:
        sce analysis capacity --week 15 --volume 60.0 --load 550.0 \\
            --historical all_activities.json
    """
    try:
        # Load historical activities
        with open(historical_json, "r") as f:
            historical_activities = json.load(f)

        result = api_check_weekly_capacity(
            week_number=week_number,
            planned_volume_km=planned_volume,
            planned_systemic_load_au=planned_load,
            historical_activities=historical_activities,
        )

        msg = f"Capacity check for Week {week_number} complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


# ============================================================
# RISK ASSESSMENT COMMANDS
# ============================================================


@risk_app.command(name="assess")
def risk_assess_command(
    ctx: typer.Context,
    metrics_json: str = typer.Option(..., "--metrics", help="JSON file with current metrics"),
    activities_json: str = typer.Option(..., "--recent", help="JSON file with recent activities"),
    workout_json: Optional[str] = typer.Option(None, "--planned", help="JSON file with planned workout (optional)"),
) -> None:
    """
    Assess current injury risk holistically.

    Combines ACWR, readiness, TSB, and recent load to calculate injury
    probability and provide actionable risk mitigation options.

    Example:
        sce risk assess --metrics current_metrics.json \\
            --recent last_7d_activities.json \\
            --planned today_workout.json
    """
    try:
        # Load current metrics
        with open(metrics_json, "r") as f:
            current_metrics = json.load(f)

        # Load recent activities
        with open(activities_json, "r") as f:
            recent_activities = json.load(f)

        # Load planned workout (optional)
        planned_workout = None
        if workout_json:
            with open(workout_json, "r") as f:
                planned_workout = json.load(f)

        result = api_assess_current_risk(
            current_metrics=current_metrics,
            recent_activities=recent_activities,
            planned_workout=planned_workout,
        )

        msg = "Current risk assessment complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


@risk_app.command(name="recovery-window")
def recovery_window_command(
    ctx: typer.Context,
    trigger: str = typer.Option(..., "--trigger", help="Trigger type: ACWR_ELEVATED, TSB_OVERREACHED, READINESS_LOW, LOWER_BODY_SPIKE"),
    current_value: float = typer.Option(..., "--value", help="Current metric value"),
    safe_threshold: float = typer.Option(..., "--threshold", help="Safe threshold value"),
) -> None:
    """
    Estimate recovery timeline to safe zone.

    Calculates minimum, typical, and maximum recovery days with day-by-day
    checkpoints for returning to safe training zones.

    Example:
        sce risk recovery-window --trigger ACWR_ELEVATED \\
            --value 1.35 --threshold 1.3
    """
    try:
        result = api_estimate_recovery_window(
            trigger_type=trigger,
            current_value=current_value,
            safe_threshold=safe_threshold,
        )

        msg = f"Recovery window estimate for {trigger} complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except Exception as e:
        envelope = {
            "ok": False,
            "error_type": "calculation_failed",
            "message": str(e),
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=1)


@risk_app.command(name="forecast")
def forecast_command(
    ctx: typer.Context,
    weeks: int = typer.Option(..., "--weeks", help="Number of weeks to forecast (1-4)"),
    metrics_json: str = typer.Option(..., "--metrics", help="JSON file with current metrics"),
    plan_json: str = typer.Option(..., "--plan", help="JSON file with planned weeks"),
) -> None:
    """
    Forecast future training stress (CTL/ATL/TSB/ACWR).

    Projects metrics 1-4 weeks ahead to identify risk windows and suggest
    proactive plan adjustments.

    Example:
        sce risk forecast --weeks 3 \\
            --metrics current_metrics.json \\
            --plan planned_weeks.json
    """
    try:
        # Load current metrics
        with open(metrics_json, "r") as f:
            current_metrics = json.load(f)

        # Load planned weeks
        with open(plan_json, "r") as f:
            planned_weeks = json.load(f)

        result = api_forecast_training_stress(
            weeks_ahead=weeks,
            current_metrics=current_metrics,
            planned_weeks=planned_weeks,
        )

        msg = f"{weeks}-week training stress forecast complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


@risk_app.command(name="taper-status")
def taper_status_command(
    ctx: typer.Context,
    race_date: str = typer.Option(..., "--race-date", help="Race date (YYYY-MM-DD)"),
    metrics_json: str = typer.Option(..., "--metrics", help="JSON file with current metrics"),
    weeks_json: str = typer.Option(..., "--recent-weeks", help="JSON file with recent weeks"),
) -> None:
    """
    Verify taper progression toward race.

    Checks volume reduction, TSB trajectory, and readiness trend to ensure
    taper is on track for race day freshness.

    Example:
        sce risk taper-status --race-date 2026-03-15 \\
            --metrics current_metrics.json \\
            --recent-weeks last_3_weeks.json
    """
    try:
        # Parse race date
        from datetime import datetime
        race_date_obj = datetime.strptime(race_date, "%Y-%m-%d").date()

        # Load current metrics
        with open(metrics_json, "r") as f:
            current_metrics = json.load(f)

        # Load recent weeks
        with open(weeks_json, "r") as f:
            recent_weeks = json.load(f)

        result = api_assess_taper_status(
            race_date=race_date_obj,
            current_metrics=current_metrics,
            recent_weeks=recent_weeks,
        )

        msg = f"Taper status assessment for race on {race_date} complete"
        envelope = api_result_to_envelope(result, success_message=msg)
        output_json(envelope)

        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    except ValueError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid date format: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except FileNotFoundError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"JSON file not found: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error_type": "invalid_input",
            "message": f"Invalid JSON: {str(e)}",
            "data": None,
        }
        output_json(envelope)
        raise typer.Exit(code=5)


# Register risk subcommand
app.add_typer(risk_app, name="risk")
