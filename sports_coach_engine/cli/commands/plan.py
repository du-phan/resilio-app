"""
sce plan - Manage training plans.

View current plan or regenerate based on goal.
"""

import typer

from sports_coach_engine.api import get_current_plan, regenerate_plan
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import output_json

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
