"""
sce plan - Manage training plans.

View current plan or regenerate based on goal.
"""

import json
from pathlib import Path
from typing import Optional

import typer

from sports_coach_engine.api import get_current_plan, regenerate_plan
from sports_coach_engine.api.plan import (
    get_plan_weeks,
    populate_plan_workouts,
    update_plan_week,
    update_plan_from_week,
    save_training_plan_review,
    append_training_plan_adaptation,
    initialize_plan_training_log,
    append_weekly_training_summary,
    validate_plan_json_structure,
)
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


@app.command(name="week")
def plan_week_command(
    ctx: typer.Context,
    week: Optional[int] = typer.Option(
        None,
        "--week",
        help="Week number (1-indexed). Defaults to current week."
    ),
    next_week: bool = typer.Option(
        False,
        "--next",
        help="Get next week instead of current week"
    ),
    date_str: Optional[str] = typer.Option(
        None,
        "--date",
        help="Get week containing this date (YYYY-MM-DD)"
    ),
    count: int = typer.Option(
        1,
        "--count",
        help="Number of consecutive weeks to return (default: 1)"
    ),
) -> None:
    """Get specific week(s) from the training plan.

    Returns just the requested week(s) with workouts, not the entire plan.
    Useful for previewing upcoming training or reviewing specific weeks.

    Examples:
        sce plan week                    # Current week
        sce plan week --next             # Next week
        sce plan week --week 5           # Week 5 specifically
        sce plan week --date 2026-02-15  # Week containing this date
        sce plan week --week 5 --count 2 # Weeks 5-6
    """
    # Parse date if provided
    target_date = None
    if date_str:
        try:
            from datetime import datetime
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Invalid date format: {date_str}. Use YYYY-MM-DD",
                data={"provided": date_str}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    # Call API
    result = get_plan_weeks(
        week_number=week,
        target_date=target_date,
        next_week=next_week,
        count=count
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=_build_week_message(result),
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


@app.command(name="validate-json")
def plan_validate_json_command(
    ctx: typer.Context,
    file: str = typer.Option(
        ...,
        "--file",
        help="Path to JSON file to validate"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show detailed validation output"
    )
) -> None:
    """Validate training plan JSON before populating.

    Checks for:
    - JSON structure and syntax
    - Required fields present
    - Date alignment (Monday-Sunday)
    - Valid enum values
    - If using explicit format: workout distances sum to target

    Returns exit code 0 if valid, 1 if errors found.

    Examples:
        sce plan validate-json --file /tmp/plan.json
        sce plan validate-json --file /tmp/plan.json --verbose
    """
    # Validate file exists
    json_path = Path(file)
    if not json_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"JSON file not found: {file}",
            data={"path": str(json_path.absolute())}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Call API validation
    is_valid, errors, warnings = validate_plan_json_structure(file, verbose)

    # Build result as plain JSON (not a dataclass envelope)
    import sys
    import json as json_module

    if is_valid:
        result = {
            "success": True,
            "message": "JSON is valid and ready to populate!",
            "data": {
                "file": file,
                "warnings": warnings,
                "warnings_count": len(warnings)
            }
        }
        print(json_module.dumps(result, indent=2))
        raise typer.Exit(code=0)
    else:
        result = {
            "success": False,
            "message": f"Found {len(errors)} error(s) in JSON",
            "error_type": "validation",
            "data": {
                "file": file,
                "errors": errors,
                "warnings": warnings,
                "errors_count": len(errors),
                "warnings_count": len(warnings)
            }
        }
        print(json_module.dumps(result, indent=2))
        raise typer.Exit(code=1)


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


def _build_week_message(result: any) -> str:
    """Build human-readable message for plan weeks.

    Args:
        result: PlanWeeksResult from API

    Returns:
        Human-readable message
    """
    from sports_coach_engine.api.plan import PlanWeeksResult

    if not isinstance(result, PlanWeeksResult):
        return "Plan weeks retrieved"

    if len(result.weeks) == 1:
        week = result.weeks[0]
        return f"{result.week_range}: {week.phase} phase ({week.start_date} to {week.end_date})"
    else:
        return f"{result.week_range}: {len(result.weeks)} weeks retrieved"


@app.command(name="save-review")
def plan_save_review_command(
    ctx: typer.Context,
    from_file: str = typer.Option(
        ...,
        "--from-file",
        help="Path to review markdown file (e.g., /tmp/training_plan_review_2026_01_20.md)"
    ),
    approved: bool = typer.Option(
        True,
        "--approved/--draft",
        help="Mark as approved plan (default) or draft review"
    )
) -> None:
    """Save training plan review markdown to repository.

    Workflow:
    1. Reads review markdown from source file
    2. Enhances with approval metadata (timestamp, athlete name, plan ID)
    3. Saves to data/plans/reviews/{start_date}_{goal_type}.md
    4. Creates symlink at data/plans/current_plan_review.md

    Use this after athlete approves a plan to preserve the review document.

    Example:
        sce plan save-review --from-file /tmp/training_plan_review_2026_01_20.md --approved

    Returns JSON with saved path and symlink location.
    """
    # Validate file exists
    file_path = Path(from_file)
    if not file_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"Review file not found: {from_file}",
            data={"path": str(file_path.absolute())}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Call API
    result = save_training_plan_review(
        review_file_path=from_file,
        approved=approved
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message="Plan review saved to repository",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="init-log")
def plan_init_log_command(ctx: typer.Context) -> None:
    """Initialize training log for current plan.

    Creates initial training log markdown file with plan header.
    Called automatically after plan approval to set up logging.

    Workflow:
    1. Reads current plan details
    2. Reads athlete profile for name
    3. Creates log file at data/plans/logs/{start_date}_{goal_type}_log.md
    4. Creates symlink at data/plans/current_training_log.md

    Example:
        sce plan init-log

    Returns JSON with log path and symlink location.
    """
    # Call API
    result = initialize_plan_training_log()

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message="Training log initialized",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="append-week")
def plan_append_week_command(
    ctx: typer.Context,
    week_number: int = typer.Option(..., "--week", help="Week number to append"),
    from_json: str = typer.Option(
        ...,
        "--from-json",
        help="Path to JSON file with weekly summary data"
    )
) -> None:
    """Append weekly training summary to log.

    Adds completed week summary to training log with workouts,
    metrics, and coach observations.

    Called by weekly-analysis skill after week completes.

    JSON Format:
        {
          "week_number": 1,
          "week_dates": "Jan 20-26",
          "planned_volume_km": 22.0,
          "actual_volume_km": 20.0,
          "adherence_pct": 91.0,
          "completed_workouts": [
            {
              "date": "2026-01-21",
              "day": "Tue, Jan 21",
              "type": "easy",
              "distance_km": 6.0,
              "pace_per_km": "6:42",
              "hr_avg": 148,
              "notes": "Felt great, no ankle discomfort"
            }
          ],
          "key_metrics": {
            "ctl_start": 28,
            "ctl_end": 30,
            "tsb_start": 3,
            "tsb_end": 1,
            "acwr": 1.1
          },
          "coach_observations": "Great first week establishing routine...",
          "milestones": ["First week completed with 91% adherence"]
        }

    Example:
        sce plan append-week --week 1 --from-json /tmp/week_1_summary.json

    Returns JSON with confirmation and appended week number.
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

    # Validate week_data is a dict
    if not isinstance(week_data, dict):
        envelope = create_error_envelope(
            error_type="validation",
            message="JSON must contain a single week summary object (not an array)",
            data={"type": type(week_data).__name__}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Call API
    result = append_weekly_training_summary(week_data)

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Appended week {week_number} summary to training log",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="append-adaptation")
def plan_append_adaptation_command(
    ctx: typer.Context,
    from_file: str = typer.Option(
        ...,
        "--from-file",
        help="Path to adaptation markdown file (e.g., /tmp/plan_adaptation_2026_02_15.md)"
    ),
    reason: str = typer.Option(
        ...,
        "--reason",
        help="Adaptation reason (illness/injury/schedule_change/missed_workouts/etc)"
    )
) -> None:
    """Append plan adaptation to existing review.

    Updates the plan review markdown with adaptation details
    when plan is modified mid-cycle.

    Called by plan-adaptation skill after athlete approves changes.

    Workflow:
    1. Reads existing plan review
    2. Reads adaptation markdown from source file
    3. Appends adaptation section with header and context
    4. Saves updated review back to repository

    Example:
        sce plan append-adaptation \\
            --from-file /tmp/plan_adaptation_2026_02_15.md \\
            --reason illness

    Returns JSON with updated review path and adaptation timestamp.
    """
    # Validate file exists
    file_path = Path(from_file)
    if not file_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"Adaptation file not found: {from_file}",
            data={"path": str(file_path.absolute())}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Call API
    result = append_training_plan_adaptation(
        adaptation_file_path=from_file,
        reason=reason
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Appended {reason} adaptation to plan review",
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="show-review")
def plan_show_review_command(ctx: typer.Context) -> None:
    """Display current plan review markdown.

    Shows the complete plan review including original structure
    and any adaptations that have been appended.

    Useful for coach to reference during coaching sessions.

    Example:
        sce plan show-review

    Returns markdown content for display.
    """
    from sports_coach_engine.core.paths import current_plan_review_path
    from sports_coach_engine.core.repository import RepositoryIO

    repo = RepositoryIO()
    review_path = current_plan_review_path()
    review_abs_path = repo.resolve_path(review_path)

    if not review_abs_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message="Plan review not found. Generate and save a plan first.",
            data={"expected_path": review_path}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Read and return markdown content
    with open(review_abs_path, 'r') as f:
        content = f.read()

    envelope = {
        "success": True,
        "message": "Plan review retrieved",
        "data": {
            "path": review_path,
            "content": content
        }
    }

    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="show-log")
def plan_show_log_command(
    ctx: typer.Context,
    last_weeks: int = typer.Option(
        None,
        "--last-weeks",
        help="Show only last N weeks (default: all weeks)"
    )
) -> None:
    """Display current training log markdown.

    Shows weekly training summaries with completed workouts,
    metrics, and coach observations.

    Useful for reviewing recent progress during coaching sessions.

    Example:
        sce plan show-log              # Show entire log
        sce plan show-log --last-weeks 4   # Show last 4 weeks only

    Returns markdown content for display.
    """
    from sports_coach_engine.core.paths import current_training_log_path
    from sports_coach_engine.core.repository import RepositoryIO

    repo = RepositoryIO()
    log_path = current_training_log_path()
    log_abs_path = repo.resolve_path(log_path)

    if not log_abs_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message="Training log not found. Initialize it with: sce plan init-log",
            data={"expected_path": log_path}
        )
        output_json(envelope)
        raise typer.Exit(code=2)

    # Read markdown content
    with open(log_abs_path, 'r') as f:
        content = f.read()

    # If last_weeks specified, filter content
    if last_weeks is not None:
        # Split by week markers (## Week N:)
        import re
        weeks = re.split(r'(## Week \d+:)', content)

        # Reconstruct with header and last N weeks
        if len(weeks) > 1:
            # First element is the header before first week
            header = weeks[0]
            # Remaining elements alternate: [marker, content, marker, content, ...]
            week_pairs = [(weeks[i], weeks[i+1]) for i in range(1, len(weeks)-1, 2)]

            # Take last N weeks
            selected_weeks = week_pairs[-last_weeks:] if last_weeks < len(week_pairs) else week_pairs

            # Reconstruct content
            content = header + ''.join([marker + text for marker, text in selected_weeks])

    envelope = {
        "success": True,
        "message": f"Training log retrieved{' (last ' + str(last_weeks) + ' weeks)' if last_weeks else ''}",
        "data": {
            "path": log_path,
            "content": content,
            "weeks_shown": last_weeks if last_weeks else "all"
        }
    }

    output_json(envelope)
    raise typer.Exit(code=0)


# ============================================================
# PROGRESSIVE DISCLOSURE COMMANDS (Phase 2: Monthly Planning)
# ============================================================


@app.command(name="create-macro")
def create_macro_command(
    ctx: typer.Context,
    goal_type: str = typer.Option(..., "--goal-type", help="Race distance: 5k, 10k, half_marathon, marathon"),
    race_date: str = typer.Option(..., "--race-date", help="Race date (YYYY-MM-DD)"),
    target_time: Optional[str] = typer.Option(None, "--target-time", help="Target finish time (e.g., '1:30:00')"),
    total_weeks: int = typer.Option(..., "--total-weeks", help="Total weeks in plan"),
    start_date: str = typer.Option(..., "--start-date", help="Plan start date (YYYY-MM-DD, must be Monday)"),
    current_ctl: float = typer.Option(..., "--current-ctl", help="Current CTL"),
    starting_volume_km: float = typer.Option(..., "--starting-volume-km", help="Initial weekly volume (km)"),
    peak_volume_km: float = typer.Option(..., "--peak-volume-km", help="Peak weekly volume (km)"),
) -> None:
    """
    Generate high-level training plan structure (macro plan).

    Creates the structural roadmap for the full training period without detailed
    workout prescriptions. Shows phases, volume progression, CTL trajectory,
    recovery weeks, and key milestones.

    This provides the "big picture" for athlete confidence. Monthly plans provide
    execution detail generated every 4 weeks.

    Examples:
        sce plan create-macro --goal-type half_marathon --race-date 2026-05-03 \\
            --target-time "1:30:00" --total-weeks 16 --start-date 2026-01-20 \\
            --current-ctl 44.0 --starting-volume-km 25.0 --peak-volume-km 55.0

    Returns:
        Macro plan structure with phases, volume trajectory, CTL projections,
        recovery weeks, and assessment milestones.
    """
    from sports_coach_engine.api.plan import create_macro_plan
    from datetime import date as dt_date

    # Parse dates
    try:
        race_date_parsed = dt_date.fromisoformat(race_date)
        start_date_parsed = dt_date.fromisoformat(start_date)
    except ValueError as e:
        envelope = {
            "success": False,
            "message": f"Invalid date format: {e}",
            "error_type": "validation",
            "data": None
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Call API
    result = create_macro_plan(
        goal_type=goal_type,
        race_date=race_date_parsed,
        target_time=target_time,
        total_weeks=total_weeks,
        start_date=start_date_parsed,
        current_ctl=current_ctl,
        starting_volume_km=starting_volume_km,
        peak_volume_km=peak_volume_km
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Macro plan created: {total_weeks} weeks, {len(result.get('phases', []))} phases"
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="assess-month")
def assess_month_command(
    ctx: typer.Context,
    month_number: int = typer.Option(..., "--month-number", help="Month number (1-indexed)"),
    week_numbers: str = typer.Option(..., "--week-numbers", help="Comma-separated week numbers (e.g., '1,2,3,4')"),
    planned_workouts_json: str = typer.Option(..., "--planned-workouts", help="Path to JSON file with planned workouts"),
    completed_activities_json: str = typer.Option(..., "--completed-activities", help="Path to JSON file with completed activities"),
    starting_ctl: float = typer.Option(..., "--starting-ctl", help="CTL at month start"),
    ending_ctl: float = typer.Option(..., "--ending-ctl", help="CTL at month end"),
    target_ctl: float = typer.Option(..., "--target-ctl", help="Target CTL for month end"),
    current_vdot: float = typer.Option(..., "--current-vdot", help="VDOT used for month's paces"),
) -> None:
    """
    Assess completed month for next month planning.

    Analyzes execution and response to inform adaptive planning:
    - Adherence rates
    - CTL progression vs. targets
    - VDOT recalibration needs
    - Injury/illness signals from activity notes
    - Volume tolerance
    - Patterns detected

    Examples:
        sce plan assess-month --month-number 1 --week-numbers "1,2,3,4" \\
            --planned-workouts /tmp/planned.json \\
            --completed-activities /tmp/completed.json \\
            --starting-ctl 44.0 --ending-ctl 50.5 --target-ctl 52.0 --current-vdot 48.0

    Returns:
        Monthly assessment with adherence, CTL analysis, VDOT recommendations,
        signals detected, and recommendations for next month.
    """
    from sports_coach_engine.api.plan import assess_month_completion
    import json

    # Parse week numbers
    try:
        week_nums = [int(w.strip()) for w in week_numbers.split(',')]
    except ValueError as e:
        envelope = {
            "success": False,
            "message": f"Invalid week numbers format: {e}",
            "error_type": "validation",
            "data": None
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Load JSON files
    try:
        with open(planned_workouts_json, 'r') as f:
            planned = json.load(f)
        with open(completed_activities_json, 'r') as f:
            completed = json.load(f)
    except FileNotFoundError as e:
        envelope = {
            "success": False,
            "message": f"File not found: {e}",
            "error_type": "not_found",
            "data": None
        }
        output_json(envelope)
        raise typer.Exit(code=2)
    except json.JSONDecodeError as e:
        envelope = {
            "success": False,
            "message": f"Invalid JSON: {e}",
            "error_type": "validation",
            "data": None
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Call API
    result = assess_month_completion(
        month_number=month_number,
        week_numbers=week_nums,
        planned_workouts=planned,
        completed_activities=completed,
        starting_ctl=starting_ctl,
        ending_ctl=ending_ctl,
        target_ctl=target_ctl,
        current_vdot=current_vdot
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Month {month_number} assessed: {result.get('adherence_pct', 0):.1f}% adherence"
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="validate-month")
def validate_month_command(
    ctx: typer.Context,
    monthly_plan_json: str = typer.Option(..., "--monthly-plan", help="Path to JSON file with 4 weeks of monthly plan"),
    macro_targets_json: str = typer.Option(..., "--macro-targets", help="Path to JSON file with 4 volume targets from macro plan"),
) -> None:
    """
    Validate 4-week monthly plan before saving.

    Checks for:
    - Volume discrepancies vs. macro plan targets (<5% acceptable, >10% regenerate)
    - Guardrail violations (minimum workout durations)
    - Phase consistency
    - Workout field completeness

    Examples:
        sce plan validate-month \\
            --monthly-plan /tmp/monthly_plan.json \\
            --macro-targets /tmp/macro_targets.json

    Returns:
        Validation result with overall_ok status, violations list, warnings,
        and summary message.
    """
    from sports_coach_engine.api.plan import validate_month_plan
    import json

    # Load JSON files
    try:
        with open(monthly_plan_json, 'r') as f:
            monthly_weeks = json.load(f)
        with open(macro_targets_json, 'r') as f:
            macro_targets = json.load(f)
    except FileNotFoundError as e:
        envelope = {
            "success": False,
            "message": f"File not found: {e}",
            "error_type": "not_found",
            "data": None
        }
        output_json(envelope)
        raise typer.Exit(code=2)
    except json.JSONDecodeError as e:
        envelope = {
            "success": False,
            "message": f"Invalid JSON: {e}",
            "error_type": "validation",
            "data": None
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Call API
    result = validate_month_plan(
        monthly_plan_weeks=monthly_weeks,
        macro_volume_targets=macro_targets
    )

    # Convert to envelope
    summary = result.get("summary", "Validation complete")
    envelope = api_result_to_envelope(result, success_message=summary)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="generate-month")
def generate_month_command(
    ctx: typer.Context,
    month_number: int = typer.Option(..., "--month-number", help="Month number (1-5)"),
    week_numbers: str = typer.Option(..., "--week-numbers", help="Comma-separated week numbers (e.g., '1,2,3,4' or '9,10,11')"),
    from_macro: str = typer.Option(..., "--from-macro", help="Path to macro plan JSON file"),
    current_vdot: float = typer.Option(..., "--current-vdot", help="Current VDOT (30-85)"),
    profile_path: str = typer.Option(..., "--profile", help="Path to athlete profile file"),
    volume_adjustment: float = typer.Option(1.0, "--volume-adjustment", help="Volume multiplier (0.5-1.5, default 1.0)"),
) -> None:
    """
    Generate detailed monthly plan (2-6 weeks) with workout prescriptions.

    Examples:
        # Generate first month (4 weeks)
        sce plan generate-month --month-number 1 --week-numbers "1,2,3,4" \\
          --from-macro /tmp/macro.json --current-vdot 48 --profile data/athlete/profile.yaml

        # Generate 3-week cycle for 11-week plan
        sce plan generate-month --month-number 3 --week-numbers "9,10,11" \\
          --from-macro /tmp/macro.json --current-vdot 49 --profile data/athlete/profile.yaml

        # Generate with volume reduction (10% less)
        sce plan generate-month --month-number 2 --week-numbers "5,6,7,8" \\
          --from-macro /tmp/macro.json --current-vdot 48.5 --profile data/athlete/profile.yaml \\
          --volume-adjustment 0.9
    """
    import json
    import yaml
    from pathlib import Path
    from sports_coach_engine.api.plan import generate_month_plan
    from sports_coach_engine.cli.output import output_json, api_result_to_envelope, get_exit_code_from_envelope

    # Parse week numbers
    try:
        week_nums = [int(w.strip()) for w in week_numbers.split(",")]
    except ValueError:
        envelope = {
            "ok": False,
            "error": "validation",
            "message": f"Invalid week-numbers format: '{week_numbers}'. Expected comma-separated integers."
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Validate week_numbers
    if not week_nums:
        envelope = {
            "ok": False,
            "error": "validation",
            "message": "week-numbers cannot be empty"
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    if not (2 <= len(week_nums) <= 6):
        envelope = {
            "ok": False,
            "error": "validation",
            "message": f"Cycle must be 2-6 weeks, got {len(week_nums)} weeks: {week_nums}"
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Load macro plan
    macro_path = Path(from_macro)
    if not macro_path.exists():
        envelope = {
            "ok": False,
            "error": "file_not_found",
            "message": f"Macro plan file not found: {from_macro}"
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    try:
        with open(macro_path) as f:
            macro_plan = json.load(f)
    except json.JSONDecodeError as e:
        envelope = {
            "ok": False,
            "error": "invalid_json",
            "message": f"Invalid macro plan JSON: {str(e)}"
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Load profile
    profile_file = Path(profile_path)
    if not profile_file.exists():
        envelope = {
            "ok": False,
            "error": "file_not_found",
            "message": f"Profile file not found: {profile_path}"
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    try:
        with open(profile_file) as f:
            if profile_path.endswith(".yaml") or profile_path.endswith(".yml"):
                profile = yaml.safe_load(f)
            else:
                profile = json.load(f)
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        envelope = {
            "ok": False,
            "error": "invalid_file",
            "message": f"Invalid profile file: {str(e)}"
        }
        output_json(envelope)
        raise typer.Exit(code=5)

    # Call API
    result = generate_month_plan(
        month_number=month_number,
        week_numbers=week_nums,
        macro_plan=macro_plan,
        current_vdot=current_vdot,
        profile=profile,
        volume_adjustment=volume_adjustment
    )

    # Convert to envelope
    cycle_weeks = f"{len(week_nums)}-week"
    success_message = f"Monthly plan generated for month {month_number} ({cycle_weeks} cycle): weeks {min(week_nums)}-{max(week_nums)}"
    envelope = api_result_to_envelope(result, success_message=success_message)

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="suggest-run-count")
def plan_suggest_run_count_command(
    ctx: typer.Context,
    volume: float = typer.Option(..., "--volume", help="Weekly volume in km"),
    max_runs: int = typer.Option(..., "--max-runs", help="Maximum run days from profile"),
    phase: str = typer.Option("base", "--phase", help="Training phase (base/build/peak/taper/recovery)"),
    profile_path: Optional[str] = typer.Option(None, "--profile", help="Path to athlete profile (for historical minimums)")
) -> None:
    """Suggest optimal number of running sessions for given weekly volume.

    Helps AI Coach choose appropriate run count within max_runs constraint.
    Considers:
    - Weekly volume target
    - Minimum practical workout distances
    - Athlete's historical patterns (if profile provided)
    - Training phase (affects long run %)

    Examples:
        sce plan suggest-run-count --volume 23 --max-runs 4 --phase base
        sce plan suggest-run-count --volume 48 --max-runs 5 --phase build
    """
    from sports_coach_engine.api.plan import suggest_optimal_run_count
    from sports_coach_engine.api.profile import ProfileError

    # Load profile if provided
    profile_dict = None
    if profile_path:
        from sports_coach_engine.api.profile import get_profile
        profile_result = get_profile()
        if not isinstance(profile_result, ProfileError):
            profile_dict = profile_result.model_dump()

    # Call API
    result = suggest_optimal_run_count(
        target_volume_km=volume,
        max_runs=max_runs,
        phase=phase,
        profile=profile_dict
    )

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=f"Recommend {result['recommended_runs']} runs for {volume}km"
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)
