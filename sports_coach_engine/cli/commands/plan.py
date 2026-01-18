"""
sce plan - Manage training plans.

View current plan or regenerate based on goal.
"""

import json
from pathlib import Path

import typer

from sports_coach_engine.api import get_current_plan, regenerate_plan
from sports_coach_engine.api.plan import (
    populate_plan_workouts,
    update_plan_week,
    update_plan_from_week,
    save_training_plan_review,
    append_training_plan_adaptation,
    initialize_plan_training_log,
    append_weekly_training_summary,
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
