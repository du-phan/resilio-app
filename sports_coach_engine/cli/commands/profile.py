"""
sce profile - Manage athlete profile.

Get or update athlete profile fields like name, max_hr, resting_hr, etc.
"""

from typing import Optional
import os
import subprocess

import typer

from sports_coach_engine.api import create_profile, get_profile, update_profile
from sports_coach_engine.api.profile import ProfileError
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, output_json, OutputEnvelope
from sports_coach_engine.schemas.profile import Weekday, DetailLevel, CoachingStyle, IntensityMetric

# Create subcommand app
app = typer.Typer(help="Manage athlete profile")


@app.command(name="create")
def profile_create_command(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Athlete name"),
    age: Optional[int] = typer.Option(None, "--age", help="Age in years"),
    max_hr: Optional[int] = typer.Option(None, "--max-hr", help="Maximum heart rate"),
    resting_hr: Optional[int] = typer.Option(None, "--resting-hr", help="Resting heart rate"),
    run_priority: str = typer.Option(
        "equal",
        "--run-priority",
        help="Running priority: primary, secondary, or equal"
    ),
    conflict_policy: str = typer.Option(
        "ask_each_time",
        "--conflict-policy",
        help="Conflict resolution: primary_sport_wins, running_goal_wins, or ask_each_time"
    ),
    min_run_days: int = typer.Option(2, "--min-run-days", help="Minimum run days per week"),
    max_run_days: int = typer.Option(4, "--max-run-days", help="Maximum run days per week"),
    available_days: Optional[str] = typer.Option(
        None,
        "--available-days",
        help="Available run days (comma-separated, e.g., 'monday,wednesday,friday')"
    ),
    detail_level: Optional[str] = typer.Option(
        None,
        "--detail-level",
        help="Coaching detail level: brief, moderate, or detailed"
    ),
    coaching_style: Optional[str] = typer.Option(
        None,
        "--coaching-style",
        help="Coaching style: supportive, direct, or analytical"
    ),
    intensity_metric: Optional[str] = typer.Option(
        None,
        "--intensity-metric",
        help="Intensity metric: pace, hr, or rpe"
    ),
) -> None:
    """Create a new athlete profile.

    This creates an initial profile with sensible defaults. You can update
    fields later using 'sce profile set'.

    Examples:
        sce profile create --name "Alex" --age 32 --max-hr 190
        sce profile create --name "Sam" --run-priority primary
        sce profile create --name "Alex" --available-days "monday,wednesday,friday"
    """
    # Parse constraint fields (comma-separated days to List[Weekday])
    available_days_list = None
    if available_days:
        try:
            available_days_list = [Weekday(d.strip().lower()) for d in available_days.split(',')]
        except ValueError as e:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid day in --available-days: {str(e)}. Use: monday, tuesday, wednesday, thursday, friday, saturday, sunday",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    # Parse preference enums
    detail_level_enum = None
    if detail_level:
        try:
            detail_level_enum = DetailLevel(detail_level.lower())
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid --detail-level: {detail_level}. Use: brief, moderate, or detailed",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    coaching_style_enum = None
    if coaching_style:
        try:
            coaching_style_enum = CoachingStyle(coaching_style.lower())
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid --coaching-style: {coaching_style}. Use: supportive, direct, or analytical",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    intensity_metric_enum = None
    if intensity_metric:
        try:
            intensity_metric_enum = IntensityMetric(intensity_metric.lower())
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid --intensity-metric: {intensity_metric}. Use: pace, hr, or rpe",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    # Call API
    result = create_profile(
        name=name,
        age=age,
        max_hr=max_hr,
        resting_hr=resting_hr,
        running_priority=run_priority,
        conflict_policy=conflict_policy,
        min_run_days=min_run_days,
        max_run_days=max_run_days,
        available_run_days=available_days_list,
        detail_level=detail_level_enum,
        coaching_style=coaching_style_enum,
        intensity_metric=intensity_metric_enum,
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
    vdot: Optional[int] = typer.Option(None, "--vdot", help="VDOT (running fitness level)"),
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
    available_days: Optional[str] = typer.Option(
        None,
        "--available-days",
        help="Available run days (comma-separated, e.g., 'monday,wednesday,friday')"
    ),
    detail_level: Optional[str] = typer.Option(
        None,
        "--detail-level",
        help="Coaching detail level: brief, moderate, or detailed"
    ),
    coaching_style: Optional[str] = typer.Option(
        None,
        "--coaching-style",
        help="Coaching style: supportive, direct, or analytical"
    ),
    intensity_metric: Optional[str] = typer.Option(
        None,
        "--intensity-metric",
        help="Intensity metric: pace, hr, or rpe"
    ),
) -> None:
    """Update athlete profile fields.

    Only specified fields are updated; others remain unchanged.

    Examples:
        sce profile set --name "Alex" --age 32
        sce profile set --max-hr 190 --resting-hr 55
        sce profile set --vdot 42
        sce profile set --run-priority primary
        sce profile set --conflict-policy ask_each_time
        sce profile set --min-run-days 3 --max-run-days 4
        sce profile set --max-session-minutes 180
        sce profile set --available-days "tuesday,thursday,saturday,sunday"
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
    if vdot is not None:
        fields["vdot"] = vdot
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

    # Parse new constraint fields
    if available_days is not None:
        try:
            available_days_list = [Weekday(d.strip().lower()) for d in available_days.split(',')]
            constraint_updates["available_run_days"] = available_days_list
        except ValueError as e:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid day in --available-days: {str(e)}. Use: monday, tuesday, wednesday, thursday, friday, saturday, sunday",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    # Parse preference fields (nested in profile.preferences)
    preference_updates = {}

    if detail_level is not None:
        try:
            detail_level_enum = DetailLevel(detail_level.lower())
            preference_updates["detail_level"] = detail_level_enum
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid --detail-level: {detail_level}. Use: brief, moderate, or detailed",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    if coaching_style is not None:
        try:
            coaching_style_enum = CoachingStyle(coaching_style.lower())
            preference_updates["coaching_style"] = coaching_style_enum
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid --coaching-style: {coaching_style}. Use: supportive, direct, or analytical",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    if intensity_metric is not None:
        try:
            intensity_metric_enum = IntensityMetric(intensity_metric.lower())
            preference_updates["intensity_metric"] = intensity_metric_enum
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid --intensity-metric: {intensity_metric}. Use: pace, hr, or rpe",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

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

    # If preference updates exist, need to load current profile and merge
    if preference_updates:
        if not constraint_updates:
            # Profile not loaded yet (constraints weren't updated)
            current_profile = get_profile()
            if hasattr(current_profile, 'error_type'):
                # Profile doesn't exist
                envelope = create_error_envelope(
                    error_type="not_found",
                    message=f"Cannot update preferences: {current_profile.message}",
                    data={}
                )
                output_json(envelope)
                raise typer.Exit(code=2)

        # Merge current preferences with updates
        current_preferences = current_profile.preferences.model_dump()
        current_preferences.update(preference_updates)
        fields["preferences"] = current_preferences

    # Validate that at least one field was provided
    if not fields and not constraint_updates and not preference_updates:
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
    if vdot is not None:
        updated_fields.append("vdot")
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


@app.command(name="add-sport")
def profile_add_sport_command(
    ctx: typer.Context,
    sport: str = typer.Option(..., "--sport", help="Sport name (e.g., climbing, yoga, cycling)"),
    days: Optional[str] = typer.Option(None, "--days", help="Days (comma-separated, e.g., 'tuesday,thursday'). Optional for flexible scheduling."),
    duration: int = typer.Option(60, "--duration", help="Typical session duration in minutes (default: 60)"),
    intensity: str = typer.Option("moderate", "--intensity", help="Intensity: easy, moderate, hard, moderate_to_hard (default: moderate)"),
    flexible: bool = typer.Option(False, "--flexible/--fixed", help="Flexible scheduling (True) or fixed commitment (False)"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Optional notes about the commitment"),
) -> None:
    """Add a sport commitment to your profile.

    This tracks your regular sport commitments (climbing, yoga, cycling, etc.)
    so the coach can account for multi-sport training load.

    Examples:
        sce profile add-sport --sport climbing --days tuesday,thursday --duration 120 --intensity moderate_to_hard --fixed
        sce profile add-sport --sport yoga --days monday --duration 60 --intensity easy --notes "Morning yoga 7am" --flexible
        sce profile add-sport --sport swimming --intensity moderate --flexible  # Flexible scheduling, no fixed days
    """
    from sports_coach_engine.api.profile import add_sport_to_profile

    # Parse days if provided
    day_list = None
    if days:
        try:
            day_list = [Weekday(d.strip().lower()) for d in days.split(',')]
        except ValueError as e:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid day in --days: {str(e)}. Use: monday, tuesday, wednesday, thursday, friday, saturday, sunday",
                data={}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    # Call API
    result = add_sport_to_profile(
        sport=sport,
        days=day_list,
        duration=duration,
        intensity=intensity,
        flexible=flexible,
        notes=notes
    )

    # Build success message
    if days:
        success_msg = f"Added sport commitment: {sport} on {days}"
    else:
        success_msg = f"Added sport commitment: {sport} (flexible scheduling)"

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=success_msg,
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="remove-sport")
def profile_remove_sport_command(
    ctx: typer.Context,
    sport: str = typer.Option(..., "--sport", help="Sport name to remove (case-insensitive)"),
) -> None:
    """Remove a sport commitment from your profile.

    Example:
        sce profile remove-sport --sport climbing
    """
    from sports_coach_engine.api.profile import remove_sport_from_profile

    # Call API
    result = remove_sport_from_profile(sport=sport)

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Removed sport commitment: {sport}",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="list-sports")
def profile_list_sports_command(ctx: typer.Context) -> None:
    """List all sport commitments in your profile.

    Shows all configured sport commitments with days, duration, and intensity.

    Example:
        sce profile list-sports
    """
    # Call get_profile API
    profile = get_profile()

    # Check for errors
    if hasattr(profile, 'error_type'):
        envelope = api_result_to_envelope(
            profile,
            success_message="",
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Format sports data
    if not profile.other_sports:
        envelope = api_result_to_envelope(
            profile,
            success_message="No sport commitments configured",
        )
        output_json(envelope)
        raise typer.Exit(code=0)

    # Build sports list
    sports_data = []
    for sport_commitment in profile.other_sports:
        sports_data.append({
            "sport": sport_commitment.sport,
            "days": [d.value for d in sport_commitment.days] if sport_commitment.days else [],
            "duration_minutes": sport_commitment.typical_duration_minutes,
            "intensity": sport_commitment.typical_intensity,
            "flexible": sport_commitment.is_flexible,
            "notes": sport_commitment.notes
        })

    # Create envelope with sports data directly
    envelope = OutputEnvelope(
        ok=True,
        message=f"Found {len(sports_data)} sport commitment(s)",
        data={"sports": sports_data},
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="validate")
def profile_validate_command(ctx: typer.Context) -> None:
    """Validate profile completeness against actual Strava data.

    Checks if other_sports is populated for all significant activities
    (>15% of total) in your Strava data.
    """
    from sports_coach_engine.api.profile import validate_profile_completeness

    result = validate_profile_completeness()

    if isinstance(result, ProfileError):
        envelope = create_error_envelope(
            error_type=result.error_type,
            message=result.message,
            data={}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Check validation result
    issues = result.get("issues", [])

    if not issues:
        envelope = OutputEnvelope(
            ok=True,
            message="✅ Profile validation passed - other_sports matches activity data",
            data={"valid": True, "issues": []}
        )
        output_json(envelope)
        raise typer.Exit(code=0)

    # Has warnings
    envelope = OutputEnvelope(
        ok=True,
        message=f"⚠️  Profile has {len(issues)} data alignment issue(s)",
        data={"valid": False, "issues": issues}
    )
    output_json(envelope)
    raise typer.Exit(code=0)  # Warning, not error


@app.command(name="edit")
def profile_edit_command(ctx: typer.Context) -> None:
    """Open profile YAML in $EDITOR for direct editing.

    This is a power-user feature for editing the profile YAML directly.
    The profile will be validated after editing to ensure data integrity.

    Environment Variables:
        EDITOR: Your preferred editor (default: nano)
                Supports: nano, vim, emacs, code, etc.

    Examples:
        sce profile edit                    # Uses $EDITOR (default: nano)
        EDITOR=vim sce profile edit         # Use vim
        EDITOR=code sce profile edit        # Use VS Code

    After editing, the profile is validated. If validation fails,
    you'll see the error and can re-edit or revert changes.
    """
    from sports_coach_engine.core.paths import athlete_profile_path
    from sports_coach_engine.core.repository import RepositoryIO, ReadOptions
    from sports_coach_engine.schemas.profile import AthleteProfile
    from sports_coach_engine.schemas.repository import RepoError, RepoErrorType

    repo = RepositoryIO()
    profile_path = athlete_profile_path()
    profile_path_str = str(profile_path)

    # Check if profile exists
    result = repo.read_yaml(
        profile_path, AthleteProfile, ReadOptions(should_validate=True)
    )

    if isinstance(result, RepoError):
        if result.error_type == RepoErrorType.NOT_FOUND:
            envelope = create_error_envelope(
                error_type="not_found",
                message="Profile not found. Create a profile first using 'sce profile create'",
                data={"profile_path": profile_path_str}
            )
            output_json(envelope)
            raise typer.Exit(code=2)
        else:
            envelope = create_error_envelope(
                error_type="unknown",
                message=f"Failed to load profile: {result.message}",
                data={"profile_path": profile_path_str}
            )
            output_json(envelope)
            raise typer.Exit(code=1)

    # Get editor from environment (default: nano)
    editor = os.environ.get('EDITOR', 'nano')

    try:
        # Open editor (blocking - waits for user to close editor)
        subprocess.run([editor, profile_path_str], check=True)

        # Validate profile after editing
        validation_result = repo.read_yaml(
            profile_path, AthleteProfile, ReadOptions(should_validate=True)
        )

        if isinstance(validation_result, RepoError):
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Profile validation failed after editing: {validation_result.message}",
                data={
                    "profile_path": profile_path_str,
                    "next_steps": "Review the error, fix the YAML, and run 'sce profile edit' again"
                }
            )
            output_json(envelope)
            raise typer.Exit(code=5)

        # Success - profile edited and validated
        envelope = api_result_to_envelope(
            validation_result,
            success_message="Profile updated and validated successfully",
        )
        output_json(envelope)
        raise typer.Exit(code=0)

    except subprocess.CalledProcessError as e:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Editor exited with error: {str(e)}",
            data={"editor": editor, "profile_path": profile_path_str}
        )
        output_json(envelope)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        envelope = create_error_envelope(
            error_type="unknown",
            message=f"Editor not found: {editor}. Set EDITOR environment variable to a valid editor.",
            data={"editor": editor, "available_editors": "nano, vim, emacs, code"}
        )
        output_json(envelope)
        raise typer.Exit(code=1)
