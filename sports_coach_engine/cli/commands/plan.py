"""
sce plan - Manage training plans.

View current plan or regenerate based on goal.
"""

import json
from pathlib import Path

import typer

from sports_coach_engine.api import get_current_plan, regenerate_plan
from sports_coach_engine.api.plan import populate_plan_workouts, update_plan_week, update_plan_from_week
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, output_json

# Create subcommand app
app = typer.Typer(help="Manage training plans")


@app.command(name="show")
def plan_show_command(ctx: typer.Context) -> None:
    """Get the current training plan with all weeks.

    Returns:
    - Goal details: race type, target date, target time
    - Total weeks and current week
    - All weeks with phases and workouts
    - Weekly volume progression
    - Guardrail validation results

    This gives Claude Code the complete plan structure for analysis.
    """
    # Call API
    result = get_current_plan()

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=_build_plan_message(result),
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="regen")
def plan_regen_command(ctx: typer.Context) -> None:
    """Regenerate training plan based on current goal.

    Workflow:
    1. Archives current plan to plans/archive/
    2. Generates new plan using M10 toolkit functions
    3. Validates against guardrails (80/20, long run caps, etc.)
    4. Saves new plan to plans/current_plan.yaml

    The athlete's current goal (set via `sce goal`) determines:
    - Race type and distance
    - Target date and time
    - Plan duration and periodization
    """
    # Call API (no goal parameter - uses existing goal from profile)
    result = regenerate_plan()

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message="Regenerated training plan based on current goal",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="populate")
def plan_populate_command(
    ctx: typer.Context,
    from_json: str = typer.Option(
        ...,
        "--from-json",
        help="Path to JSON file with weekly workout data"
    ),
) -> None:
    """Populate weekly workouts in the training plan.

    Loads weekly workout prescriptions from a JSON file and adds them
    to the current plan skeleton. The plan must already exist (created
    via 'sce plan regen').

    JSON Format:
        {
          "weeks": [
            {
              "week_number": 1,
              "phase": "base",
              "start_date": "2026-01-15",
              "end_date": "2026-01-21",
              "target_volume_km": 22.0,
              "target_systemic_load_au": 150.0,
              "workouts": [...]
            }
          ]
        }

    Examples:
        sce plan populate --from-json /tmp/marathon_plan.json
        sce plan populate --from-json workouts.json
    """
    # Validate file exists
    json_path = Path(from_json)
    if not json_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"JSON file not found: {from_json}",
            data={"path": str(json_path.absolute())}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Load JSON
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid JSON: {str(e)}",
            data={"file": from_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Extract weeks array
    if "weeks" not in data:
        envelope = create_error_envelope(
            error_type="validation",
            message="JSON must contain 'weeks' array at top level",
            data={"keys_found": list(data.keys())}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    weeks_data = data["weeks"]

    # Call API
    result = populate_plan_workouts(weeks_data)

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Populated {len(weeks_data)} weeks with workouts",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="update-week")
def plan_update_week_command(
    ctx: typer.Context,
    week: int = typer.Option(..., "--week", help="Week number to update (1-indexed)"),
    from_json: str = typer.Option(..., "--from-json", help="Path to JSON file with week data"),
) -> None:
    """Update a single week in the training plan.

    Replaces or adds a specific week while preserving other weeks.
    Useful for mid-week adjustments or updating a single week's workouts.

    JSON Format (single week object):
        {
          "week_number": 5,
          "phase": "build",
          "start_date": "2026-02-12",
          "end_date": "2026-02-18",
          "target_volume_km": 36.0,
          "target_systemic_load_au": 200.0,
          "workouts": [...]
        }

    Examples:
        sce plan update-week --week 5 --from-json week5.json
        sce plan update-week --week 1 --from-json /tmp/updated_week1.json
    """
    # Validate file exists
    json_path = Path(from_json)
    if not json_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"JSON file not found: {from_json}",
            data={"path": str(json_path.absolute())}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Load JSON
    try:
        with open(json_path, 'r') as f:
            week_data = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid JSON: {str(e)}",
            data={"file": from_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Validate week_data is a dict (not array)
    if not isinstance(week_data, dict):
        envelope = create_error_envelope(
            error_type="validation",
            message="JSON must contain a single week object (not an array)",
            data={"type": type(week_data).__name__}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Call API
    result = update_plan_week(week, week_data)

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Updated week {week}",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="update-from")
def plan_update_from_command(
    ctx: typer.Context,
    week: int = typer.Option(..., "--week", help="First week to update (inclusive, 1-indexed)"),
    from_json: str = typer.Option(..., "--from-json", help="Path to JSON file with weeks data"),
) -> None:
    """Update plan from a specific week onwards.

    Preserves earlier weeks, replaces weeks from the specified week onwards.
    Useful for "replan the rest of the season" scenarios.

    JSON Format (array of weeks):
        {
          "weeks": [
            {
              "week_number": 5,
              "phase": "build",
              "start_date": "2026-02-12",
              "end_date": "2026-02-18",
              "target_volume_km": 36.0,
              "workouts": [...]
            },
            {
              "week_number": 6,
              ...
            }
          ]
        }

    Examples:
        sce plan update-from --week 5 --from-json weeks5-10.json
        sce plan update-from --week 1 --from-json /tmp/full_replan.json
    """
    # Validate file exists
    json_path = Path(from_json)
    if not json_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"JSON file not found: {from_json}",
            data={"path": str(json_path.absolute())}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Load JSON
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid JSON: {str(e)}",
            data={"file": from_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Extract weeks array
    if "weeks" not in data:
        envelope = create_error_envelope(
            error_type="validation",
            message="JSON must contain 'weeks' array at top level",
            data={"keys_found": list(data.keys())}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    weeks_data = data["weeks"]

    # Call API
    result = update_plan_from_week(week, weeks_data)

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Updated {len(weeks_data)} weeks from week {week} onwards",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


def _build_plan_message(result: any) -> str:
    """Build human-readable message for plan.

    Args:
        result: MasterPlan from API

    Returns:
        Human-readable message
    """
    if hasattr(result, 'total_weeks') and hasattr(result, 'goal'):
        goal_type = result.goal.type if hasattr(result.goal, 'type') else 'unknown'
        return f"Current plan: {result.total_weeks} weeks for {goal_type}"

    return "Retrieved current training plan"
