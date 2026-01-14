"""
sce profile - Manage athlete profile.

Get or update athlete profile fields like name, max_hr, resting_hr, etc.
"""

from typing import Optional

import typer

from sports_coach_engine.api import get_profile, update_profile
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, output_json

# Create subcommand app
app = typer.Typer(help="Manage athlete profile")


@app.command(name="get")
def profile_get_command(ctx: typer.Context) -> None:
    """Get athlete profile with all settings.

    Returns profile including:
    - Basic info: name, age, max_hr, resting_hr
    - Goal: Current race goal (if set)
    - Constraints: Fixed commitments (e.g., climbing on Tuesdays)
    - Preferences: Run priorities, conflict policies
    - History: Injury patterns, PRs

    Secrets (Strava tokens) are redacted for security.
    """
    # Call API
    result = get_profile()

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message="Retrieved athlete profile",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="set")
def profile_set_command(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name", help="Athlete name"),
    age: Optional[int] = typer.Option(None, "--age", help="Age in years"),
    max_hr: Optional[int] = typer.Option(None, "--max-hr", help="Maximum heart rate"),
    resting_hr: Optional[int] = typer.Option(None, "--resting-hr", help="Resting heart rate"),
    run_priority: Optional[str] = typer.Option(
        None, "--run-priority", help="Running priority: primary, secondary, or equal"
    ),
    conflict_policy: Optional[str] = typer.Option(
        None,
        "--conflict-policy",
        help="Conflict resolution: primary_sport_wins, running_goal_wins, or ask_each_time",
    ),
) -> None:
    """Update athlete profile fields.

    Only specified fields are updated; others remain unchanged.

    Examples:
        sce profile set --name "Alex" --age 32
        sce profile set --max-hr 190 --resting-hr 55
        sce profile set --run-priority primary
        sce profile set --conflict-policy ask_each_time
    """
    # Collect non-None fields
    fields = {}
    if name is not None:
        fields["name"] = name
    if age is not None:
        fields["age"] = age
    if max_hr is not None:
        fields["max_hr"] = max_hr
    if resting_hr is not None:
        fields["resting_hr"] = resting_hr
    if run_priority is not None:
        fields["run_priority"] = run_priority
    if conflict_policy is not None:
        fields["conflict_policy"] = conflict_policy

    # Validate that at least one field was provided
    if not fields:
        envelope = create_error_envelope(
            error_type="validation",
            message="No fields specified. Use --name, --age, --max-hr, --resting-hr, etc.",
            data={
                "next_steps": "Run: sce profile set --help to see available fields"
            },
        )
        output_json(envelope)
        raise typer.Exit(code=5)  # Validation error

    # Call API
    result = update_profile(**fields)

    # Convert to envelope
    updated_fields = list(fields.keys())
    envelope = api_result_to_envelope(
        result,
        success_message=f"Updated profile fields: {', '.join(updated_fields)}",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)
