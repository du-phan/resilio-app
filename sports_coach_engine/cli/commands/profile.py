"""
sce profile - Manage athlete profile.

Get or update athlete profile fields like name, max_hr, resting_hr, etc.
"""

from typing import Optional

import typer

from sports_coach_engine.api import create_profile, get_profile, update_profile
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, output_json

# Create subcommand app
app = typer.Typer(help="Manage athlete profile")


@app.command(name="create")
def profile_create_command(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Athlete name"),
    age: Optional[int] = typer.Option(None, "--age", help="Age in years"),
    max_hr: Optional[int] = typer.Option(None, "--max-hr", help="Maximum heart rate"),
    resting_hr: Optional[int] = typer.Option(None, "--resting-hr", help="Resting heart rate"),
    running_priority: str = typer.Option(
        "equal",
        "--running-priority",
        help="Running priority: primary, secondary, or equal"
    ),
    conflict_policy: str = typer.Option(
        "ask_each_time",
        "--conflict-policy",
        help="Conflict resolution: primary_sport_wins, running_goal_wins, or ask_each_time"
    ),
    min_run_days: int = typer.Option(2, "--min-run-days", help="Minimum run days per week"),
    max_run_days: int = typer.Option(4, "--max-run-days", help="Maximum run days per week"),
) -> None:
    """Create a new athlete profile.

    This creates an initial profile with sensible defaults. You can update
    fields later using 'sce profile set'.

    Examples:
        sce profile create --name "Alex" --age 32 --max-hr 190
        sce profile create --name "Sam" --running-priority primary
    """
    # Call API
    result = create_profile(
        name=name,
        age=age,
        max_hr=max_hr,
        resting_hr=resting_hr,
        running_priority=running_priority,
        conflict_policy=conflict_policy,
        min_run_days=min_run_days,
        max_run_days=max_run_days,
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Created athlete profile for {name}",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


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
    min_run_days: Optional[int] = typer.Option(
        None,
        "--min-run-days",
        help="Minimum run days per week (e.g., 3)"
    ),
    max_run_days: Optional[int] = typer.Option(
        None,
        "--max-run-days",
        help="Maximum run days per week (e.g., 4)"
    ),
    max_session_minutes: Optional[int] = typer.Option(
        None,
        "--max-session-minutes",
        help="Maximum session duration in minutes (e.g., 90, 180)"
    ),
) -> None:
    """Update athlete profile fields.

    Only specified fields are updated; others remain unchanged.

    Examples:
        sce profile set --name "Alex" --age 32
        sce profile set --max-hr 190 --resting-hr 55
        sce profile set --run-priority primary
        sce profile set --conflict-policy ask_each_time
        sce profile set --min-run-days 3 --max-run-days 4
        sce profile set --max-session-minutes 180
    """
    # Collect non-None fields
    fields = {}
    constraint_updates = {}

    # Top-level fields
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

    # Constraint fields (nested in profile.constraints)
    if min_run_days is not None:
        constraint_updates["min_run_days_per_week"] = min_run_days
    if max_run_days is not None:
        constraint_updates["max_run_days_per_week"] = max_run_days
    if max_session_minutes is not None:
        constraint_updates["max_time_per_session_minutes"] = max_session_minutes

    # If constraint updates exist, need to load current profile and merge
    if constraint_updates:
        current_profile = get_profile()
        if hasattr(current_profile, 'error_type'):
            # Profile doesn't exist
            envelope = create_error_envelope(
                error_type="not_found",
                message=f"Cannot update constraints: {current_profile.message}",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=2)

        # Merge current constraints with updates
        current_constraints = current_profile.constraints.model_dump()
        current_constraints.update(constraint_updates)
        fields["constraints"] = current_constraints

    # Validate that at least one field was provided
    if not fields and not constraint_updates:
        envelope = create_error_envelope(
            error_type="validation",
            message="No fields specified. Use --name, --age, --max-hr, --min-run-days, --max-session-minutes, etc.",
            data={
                "next_steps": "Run: sce profile set --help to see available fields"
            },
        )
        output_json(envelope)
        raise typer.Exit(code=5)  # Validation error

    # Call API
    result = update_profile(**fields)

    # Convert to envelope
    # Build list of updated field names for user feedback
    updated_fields = []
    if name is not None:
        updated_fields.append("name")
    if age is not None:
        updated_fields.append("age")
    if max_hr is not None:
        updated_fields.append("max_hr")
    if resting_hr is not None:
        updated_fields.append("resting_hr")
    if run_priority is not None:
        updated_fields.append("run_priority")
    if conflict_policy is not None:
        updated_fields.append("conflict_policy")
    if min_run_days is not None:
        updated_fields.append("min_run_days")
    if max_run_days is not None:
        updated_fields.append("max_run_days")
    if max_session_minutes is not None:
        updated_fields.append("max_session_minutes")

    envelope = api_result_to_envelope(
        result,
        success_message=f"Updated profile fields: {', '.join(updated_fields)}",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="analyze")
def profile_analyze_command(ctx: typer.Context) -> None:
    """Analyze activity history to suggest profile values.

    Provides concrete, quantifiable insights for profile setup:
    - Activity date range and gaps (injury breaks, vacations)
    - Max HR observed in workouts
    - Weekly volume averages (run distance)
    - Training day patterns (which days athlete typically trains)
    - Multi-sport frequency and priorities

    Pure computation on local data - no Strava API calls.

    Example:
        sce profile analyze

        Output includes suggestions for:
        - max_hr: 199 (observed peak)
        - weekly_km: 22.5 (4-week average)
        - available_run_days: [tuesday, thursday, saturday, sunday]
        - running_priority: equal (40% running, 60% other sports)
    """
    from sports_coach_engine.api.profile import analyze_profile_from_activities

    # Call API
    result = analyze_profile_from_activities()

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message="Analyzed activity history for profile insights",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)
