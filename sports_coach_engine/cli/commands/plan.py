"""
sce plan - Manage training plans.

View current plan or regenerate based on goal.
"""

import json
from pathlib import Path
from typing import Optional

import typer

from sports_coach_engine.api import (
    get_current_plan,
    api_validate_interval_structure,
    api_validate_plan_structure,
)
from sports_coach_engine.api.plan import (
    get_plan_weeks,
    build_macro_template,
    export_plan_structure,
    populate_plan_workouts,
    update_plan_from_week,
    save_training_plan_review,
    append_training_plan_adaptation,
    initialize_plan_training_log,
    append_weekly_training_summary,
    validate_plan_json_structure,
    validate_week_plan,
    revert_week_plan,
    PlanError,
)
from sports_coach_engine.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from sports_coach_engine.cli.output import create_error_envelope, create_success_envelope, output_json

# Create subcommand app
app = typer.Typer(help="Manage training plans")


@app.command(name="show")
def plan_show_command(
    ctx: typer.Context,
    type: str = typer.Option(
        "plan",
        "--type",
        help="What to show: 'plan' (default), 'review', or 'log'"
    ),
    last_weeks: Optional[int] = typer.Option(
        None,
        "--last-weeks",
        help="For log type: show only last N weeks (default: all)"
    )
) -> None:
    """Show training plan, review, or log (consolidated command).

    Replaces the old show, show-review, and show-log commands with a single
    unified command using --type flag.

    Plan (default):
    - Goal details: race type, target date, target time
    - Total weeks and current week
    - All weeks with phases and workouts
    - Weekly volume progression

    Review:
    - Complete plan review markdown including original structure
    - Any adaptations that have been appended

    Log:
    - Weekly training summaries with completed workouts
    - Metrics and coach observations

    Examples:
        sce plan show                      # Show plan (default)
        sce plan show --type plan          # Show plan explicitly
        sce plan show --type review        # Show plan review
        sce plan show --type log           # Show training log
        sce plan show --type log --last-weeks 4  # Show last 4 weeks of log
    """
    if type == "plan":
        # Original show command behavior
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

    elif type == "review":
        # show-review behavior
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

    elif type == "log":
        # show-log behavior
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

    else:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid type '{type}'. Must be 'plan', 'review', or 'log'",
            data={"provided_type": type, "valid_types": ["plan", "review", "log"]}
        )
        output_json(envelope)
        raise typer.Exit(code=5)


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


@app.command(name="status")
def plan_status_command(ctx: typer.Context) -> None:
    """Get summarized plan status for routing decisions."""
    from sports_coach_engine.api.profile import get_profile
    from sports_coach_engine.schemas.profile import AthleteProfile

    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        envelope = api_result_to_envelope(plan_result, success_message="")
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    plan = plan_result
    last_populated_week = 0
    next_unpopulated_week = None
    for week in plan.weeks:
        if week.workouts:
            last_populated_week = week.week_number
        if not week.workouts and next_unpopulated_week is None:
            next_unpopulated_week = week.week_number

    recovery_weeks = [w.week_number for w in plan.weeks if w.is_recovery_week]

    profile = None
    profile_result = get_profile()
    if isinstance(profile_result, AthleteProfile):
        profile = profile_result

    data = {
        "plan_start": plan.start_date,
        "plan_end": plan.end_date,
        "total_weeks": plan.total_weeks,
        "baseline_vdot": getattr(plan, "baseline_vdot", None),
        "current_vdot": getattr(plan, "current_vdot", None),
        "last_populated_week": last_populated_week,
        "next_unpopulated_week": next_unpopulated_week,
        "phases": plan.phases,
        "recovery_weeks": recovery_weeks,
        "conflict_policy": plan.conflict_policy,
        "run_days": getattr(getattr(profile, "training_constraints", None), "available_run_days", None),
        "max_run_days_per_week": getattr(getattr(profile, "training_constraints", None), "max_run_days_per_week", None),
    }

    envelope = api_result_to_envelope(
        plan,
        success_message="Plan status retrieved",
    )
    envelope.data = data
    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="next-unpopulated")
def plan_next_unpopulated_command(ctx: typer.Context) -> None:
    """Return the first week with empty workouts."""
    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        envelope = api_result_to_envelope(plan_result, success_message="")
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    plan = plan_result
    target_week = None
    for week in plan.weeks:
        if not week.workouts:
            target_week = week
            break

    if target_week is None:
        envelope = api_result_to_envelope(
            plan,
            success_message="All weeks already populated",
        )
        envelope.data = {"week_number": None}
        output_json(envelope)
        raise typer.Exit(code=0)

    envelope = api_result_to_envelope(
        plan,
        success_message=f"Next unpopulated week: {target_week.week_number}",
    )
    envelope.data = {
        "week_number": target_week.week_number,
        "start_date": target_week.start_date,
        "end_date": target_week.end_date,
        "phase": target_week.phase,
        "target_volume_km": target_week.target_volume_km,
        "is_recovery_week": target_week.is_recovery_week,
    }
    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="validate-macro")
def plan_validate_macro_command(ctx: typer.Context) -> None:
    """Validate macro plan structure (phases, weeks, dates)."""
    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        envelope = api_result_to_envelope(plan_result, success_message="")
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    plan = plan_result
    errors: list[str] = []
    warnings: list[str] = []

    # Basic checks
    if plan.start_date.weekday() != 0:
        errors.append("Plan start_date must be Monday")

    # Week sequence and date alignment
    expected_week = 1
    previous_start = None
    for week in plan.weeks:
        if week.week_number != expected_week:
            errors.append(f"Week numbers not sequential (expected {expected_week}, got {week.week_number})")
            expected_week = week.week_number
        if week.start_date.weekday() != 0:
            errors.append(f"Week {week.week_number}: start_date must be Monday")
        if week.end_date.weekday() != 6:
            errors.append(f"Week {week.week_number}: end_date must be Sunday")
        if previous_start and (week.start_date - previous_start).days != 7:
            errors.append(f"Week {week.week_number}: start_date not 7 days after previous week")
        if week.target_volume_km <= 0:
            warnings.append(f"Week {week.week_number}: target_volume_km is {week.target_volume_km} (expected > 0)")
        previous_start = week.start_date
        expected_week += 1

    is_valid = len(errors) == 0
    message = "Macro plan is valid" if is_valid else "Macro plan validation failed"
    data = {"errors": errors, "warnings": warnings}

    if is_valid:
        envelope = api_result_to_envelope(plan, success_message=message)
        envelope.data = data
        output_json(envelope)
        raise typer.Exit(code=0)

    envelope = create_error_envelope(
        error_type="validation",
        message=message,
        data=data
    )
    output_json(envelope)
    raise typer.Exit(code=1)


@app.command(name="generate-week")
def plan_generate_week_command(
    ctx: typer.Context,
    week: Optional[int] = typer.Option(
        None,
        "--week",
        help="Week number to generate (defaults to next unpopulated week)"
    ),
    run_days: str = typer.Option(
        ...,
        "--run-days",
        help="Comma-separated weekday indices to run (0=Mon..6=Sun), e.g., '0,2,6'"
    ),
    long_run_day: int = typer.Option(
        ...,
        "--long-run-day",
        help="Weekday index for long run (0=Mon..6=Sun)"
    ),
    long_run_pct: float = typer.Option(
        ...,
        "--long-run-pct",
        help="Long run fraction of weekly volume (e.g., 0.45)"
    ),
    easy_run_paces: str = typer.Option(
        ...,
        "--easy-run-paces",
        help="Easy run pace range (e.g., '6:30-6:50')"
    ),
    long_run_pace: str = typer.Option(
        ...,
        "--long-run-pace",
        help="Long run pace range (e.g., '6:30-6:50')"
    ),
    structure: Optional[str] = typer.Option(
        None,
        "--structure",
        help="Optional descriptive structure string (e.g., '3 easy + 1 long')"
    ),
    out: Optional[str] = typer.Option(
        None,
        "--out",
        help="Output path for weekly JSON (defaults to /tmp/weekly_plan_w<week>.json)"
    ),
    allow_populated: bool = typer.Option(
        False,
        "--allow-populated",
        help="Allow generating for a week that already has workouts"
    ),
) -> None:
    """Generate a single week's intent-based plan JSON (no apply)."""
    from datetime import date as dt_date

    def parse_run_days(value: str) -> list[int]:
        value = value.strip()
        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON array for run_days: {e}") from e
            if not isinstance(parsed, list):
                raise ValueError("run_days JSON must be an array of integers")
            return parsed
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if not parts:
            raise ValueError("run_days must include at least one day")
        return [int(p) for p in parts]

    plan_result = get_current_plan()
    if isinstance(plan_result, PlanError):
        envelope = api_result_to_envelope(plan_result, success_message="")
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    plan = plan_result

    target_week = None
    if week is not None:
        for w in plan.weeks:
            if w.week_number == week:
                target_week = w
                break
        if target_week is None:
            envelope = create_error_envelope(
                error_type="not_found",
                message=f"Week {week} not found in current plan",
            )
            output_json(envelope)
            raise typer.Exit(code=2)
    else:
        for w in plan.weeks:
            if not w.workouts:
                target_week = w
                break
        if target_week is None:
            envelope = create_error_envelope(
                error_type="validation",
                message="All weeks already populated; specify --week to regenerate",
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    if target_week.workouts and not allow_populated:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Week {target_week.week_number} already has workouts. Use --allow-populated to proceed.",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    try:
        run_days_list = parse_run_days(run_days)
    except ValueError as e:
        envelope = create_error_envelope(
            error_type="validation",
            message=str(e),
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if not all(isinstance(d, int) for d in run_days_list):
        envelope = create_error_envelope(
            error_type="validation",
            message="run_days must be integers (0=Mon..6=Sun)",
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if any(d < 0 or d > 6 for d in run_days_list):
        envelope = create_error_envelope(
            error_type="validation",
            message="run_days must be within 0-6 (Mon=0 .. Sun=6)",
            data={"run_days": run_days_list},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    run_days_list = sorted(set(run_days_list))
    if long_run_day not in run_days_list:
        envelope = create_error_envelope(
            error_type="validation",
            message="long_run_day must be included in run_days",
            data={"long_run_day": long_run_day, "run_days": run_days_list},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if long_run_pct <= 0 or long_run_pct >= 1:
        envelope = create_error_envelope(
            error_type="validation",
            message="long_run_pct must be between 0 and 1",
            data={"long_run_pct": long_run_pct},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    structure_text = structure
    if structure_text is None:
        structure_text = f"{max(len(run_days_list) - 1, 0)} easy + 1 long"

    weekly_payload = {
        "weeks": [
            {
                "week_number": target_week.week_number,
                "phase": target_week.phase,
                "start_date": target_week.start_date.isoformat()
                if isinstance(target_week.start_date, dt_date)
                else str(target_week.start_date),
                "end_date": target_week.end_date.isoformat()
                if isinstance(target_week.end_date, dt_date)
                else str(target_week.end_date),
                "target_volume_km": target_week.target_volume_km,
                "target_systemic_load_au": getattr(target_week, "target_systemic_load_au", 0.0),
                "workout_pattern": {
                    "structure": structure_text,
                    "run_days": run_days_list,
                    "long_run_day": long_run_day,
                    "long_run_pct": long_run_pct,
                    "easy_run_paces": easy_run_paces,
                    "long_run_pace": long_run_pace,
                },
            }
        ]
    }

    out_path = out or f"/tmp/weekly_plan_w{target_week.week_number}.json"
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(weekly_payload, indent=2))

    envelope = create_success_envelope(
        message=f"Weekly plan JSON generated for week {target_week.week_number}",
        data={
            "week_number": target_week.week_number,
            "file": str(out_file),
            "phase": target_week.phase,
            "target_volume_km": target_week.target_volume_km,
            "run_days": run_days_list,
            "long_run_day": long_run_day,
            "long_run_pct": long_run_pct,
        },
    )
    output_json(envelope)
    raise typer.Exit(code=0)


@app.command(name="populate")
def plan_populate_command(
    ctx: typer.Context,
    from_json: str = typer.Option(
        ...,
        "--from-json",
        help="Path to JSON file with weekly workout data"
    ),
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Validate weekly plan JSON before populating (blocks on errors)"
    ),
) -> None:
    """Add or update weekly workouts in the training plan.

    Merges weeks into the plan: updates existing weeks (same week_number) or
    adds new weeks. Safe to call multiple times - existing weeks are preserved.
    Requires approval state for the exact weekly JSON payload.

    Progressive workflow:
        sce plan populate --from-json /tmp/week1.json   # Add week 1
        sce plan populate --from-json /tmp/week2.json   # Add week 2 (week 1 preserved)
        sce plan populate --from-json /tmp/week3.json   # Add week 3 (weeks 1-2 preserved)

    Bulk addition also works:
        sce plan populate --from-json /tmp/weeks_1_to_5.json

    JSON Format:
        {
          "weeks": [
            {
              "week_number": 1,
              "phase": "base",
              "start_date": "2026-01-15",
              "end_date": "2026-01-21",
              "target_volume_km": 22.0,
              "workouts": [...]
            }
          ]
        }
    """
    # Optional validation gate (reuses same rules as plan validate-week)
    if validate:
        is_valid, errors, warnings = _validate_weekly_plan_file(from_json, verbose=False)
        if not is_valid:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"Weekly plan validation failed: {len(errors)} error(s)",
                data={"file": from_json, "errors": errors, "warnings": warnings}
            )
            output_json(envelope)
            raise typer.Exit(code=1)

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
    if not isinstance(weeks_data, list):
        envelope = create_error_envelope(
            error_type="validation",
            message="'weeks' must be an array",
            data={"type": type(weeks_data).__name__}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Approval gate: require exact approved weekly JSON file before writing
    from sports_coach_engine.core.state import load_approval_state
    from sports_coach_engine.schemas.repository import RepoError

    approval_state = load_approval_state()
    if isinstance(approval_state, RepoError):
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to load approvals state: {approval_state}",
            data={"path": getattr(approval_state, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if approval_state is None or approval_state.weekly_approval is None:
        envelope = create_error_envelope(
            error_type="validation",
            message="Weekly approval is required before applying a plan",
            data={
                "next_steps": "Run: sce approvals approve-week --week <N> --file <approved_json>"
            },
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if len(weeks_data) != 1:
        envelope = create_error_envelope(
            error_type="validation",
            message="Approval gate requires a single-week JSON payload",
            data={"week_count": len(weeks_data)},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    week_number = weeks_data[0].get("week_number")
    if week_number is None:
        envelope = create_error_envelope(
            error_type="validation",
            message="Week payload missing required field: week_number",
            data={"keys_found": list(weeks_data[0].keys())},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    approved = approval_state.weekly_approval
    if week_number != approved.week_number:
        envelope = create_error_envelope(
            error_type="validation",
            message="Approved week number does not match payload",
            data={"approved_week": approved.week_number, "payload_week": week_number},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    resolved_payload = Path(from_json).expanduser().resolve()
    resolved_approved = Path(approved.approved_file).expanduser().resolve()
    if resolved_payload != resolved_approved:
        envelope = create_error_envelope(
            error_type="validation",
            message="Approved file path does not match payload path",
            data={
                "approved_file": str(resolved_approved),
                "payload_file": str(resolved_payload),
            },
        )
        output_json(envelope)
        raise typer.Exit(code=5)

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


@app.command(name="validate-week")
def plan_validate_week_command(
    ctx: typer.Context,
    file: str = typer.Option(
        ...,
        "--file",
        help="Path to weekly plan JSON file to validate"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show detailed validation output"
    )
) -> None:
    """Validate a single-week plan JSON before populating (unified validation).

    Runs two-stage validation:
    1. Syntax check: JSON structure, required fields, date alignment
    2. Semantic check: Guardrails, minimum durations, volume limits

    This unified command automatically runs both checks.

    Returns exit code 0 if valid, 1 if errors found.

    Examples:
        sce plan validate-week --file /tmp/week1.json
        sce plan validate-week --file /tmp/week1.json --verbose
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

    # STAGE 1: Syntax validation (fast check)
    is_syntax_valid, syntax_errors, syntax_warnings = validate_plan_json_structure(file, verbose)

    if not is_syntax_valid:
        # Fail fast on syntax errors
        import json as json_module
        result = {
            "success": False,
            "message": f"Syntax validation failed: {len(syntax_errors)} error(s) in JSON",
            "error_type": "validation",
            "data": {
                "file": file,
                "stage": "syntax",
                "errors": syntax_errors,
                "warnings": syntax_warnings,
                "errors_count": len(syntax_errors),
                "warnings_count": len(syntax_warnings)
            }
        }
        print(json_module.dumps(result, indent=2))
        raise typer.Exit(code=1)

    # STAGE 2: Semantic validation (guardrails, minimums, etc.)
    from sports_coach_engine.api.plan import validate_week_plan

    semantic_result = validate_week_plan(weekly_plan_path=file, verbose=verbose)

    # Check result type
    if isinstance(semantic_result, PlanError):
        envelope = api_result_to_envelope(semantic_result, success_message="")
        output_json(envelope)
        raise typer.Exit(code=1)

    # Build combined result
    is_semantic_valid = semantic_result.get("is_valid", False)
    semantic_errors = semantic_result.get("errors", [])
    semantic_warnings = semantic_result.get("warnings", [])

    # Combine warnings from both stages
    all_warnings = syntax_warnings + semantic_warnings

    import json as json_module

    if is_semantic_valid:
        result = {
            "success": True,
            "message": "Weekly plan is valid and ready to populate!",
            "data": {
                "file": file,
                "stages_passed": ["syntax", "semantic"],
                "warnings": all_warnings,
                "warnings_count": len(all_warnings)
            }
        }
        print(json_module.dumps(result, indent=2))
        raise typer.Exit(code=0)
    else:
        result = {
            "success": False,
            "message": f"Semantic validation failed: {len(semantic_errors)} error(s) in weekly plan",
            "error_type": "validation",
            "data": {
                "file": file,
                "stage": "semantic",
                "errors": semantic_errors,
                "warnings": all_warnings,
                "errors_count": len(semantic_errors),
                "warnings_count": len(all_warnings)
            }
        }
        print(json_module.dumps(result, indent=2))
        raise typer.Exit(code=1)


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


@app.command(name="validate-intervals")
def plan_validate_intervals_command(
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
        sce plan validate-intervals \\
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


@app.command(name="validate-structure")
def plan_validate_structure_command(
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
        sce plan validate-structure \\
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


@app.command(name="export-structure")
def plan_export_structure_command(
    ctx: typer.Context,
    out_dir: str = typer.Option(
        "/tmp",
        "--out-dir",
        help="Output directory for structure JSON files (default: /tmp)",
    ),
) -> None:
    """Export stored macro plan structure into validation-ready JSON files.

    Writes:
    - plan_phases.json (dict: phase -> weeks)
    - weekly_volumes_list.json (list of weekly volumes, length = total_weeks)
    - recovery_weeks.json (list of recovery week numbers)
    """
    export_result = export_plan_structure()
    if isinstance(export_result, PlanError):
        envelope = api_result_to_envelope(export_result, success_message="")
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    out_path = Path(out_dir).expanduser()
    try:
        out_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=f"Failed to create output directory: {e}",
            data={"out_dir": str(out_path)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    phases_file = out_path / "plan_phases.json"
    volumes_file = out_path / "weekly_volumes_list.json"
    recovery_file = out_path / "recovery_weeks.json"

    with open(phases_file, "w") as f:
        json.dump(export_result.phases, f, indent=2)
    with open(volumes_file, "w") as f:
        json.dump(export_result.weekly_volumes_km, f, indent=2)
    with open(recovery_file, "w") as f:
        json.dump(export_result.recovery_weeks, f, indent=2)

    envelope = create_success_envelope(
        message="Plan structure exported",
        data={
            "total_weeks": export_result.total_weeks,
            "goal_type": export_result.goal_type,
            "race_week": export_result.race_week,
            "phases": export_result.phases,
            "weekly_volumes_km": export_result.weekly_volumes_km,
            "recovery_weeks": export_result.recovery_weeks,
            "phases_file": str(phases_file),
            "weekly_volumes_file": str(volumes_file),
            "recovery_weeks_file": str(recovery_file),
        },
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="template-macro")
def plan_template_macro_command(
    ctx: typer.Context,
    total_weeks: int = typer.Option(..., "--total-weeks", help="Total weeks in plan"),
    out: str = typer.Option(
        "/tmp/macro_template.json",
        "--out",
        help="Output path for macro template JSON (default: /tmp/macro_template.json)",
    ),
) -> None:
    """Generate a blank macro template with required fields.

    The template includes null placeholders that must be filled before calling
    create-macro.
    """
    template = build_macro_template(total_weeks)
    if isinstance(template, PlanError):
        envelope = api_result_to_envelope(template, success_message="")
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    out_path = Path(out).expanduser()
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        envelope = create_error_envelope(
            error_type="invalid_input",
            message=f"Failed to create output directory: {e}",
            data={"out": str(out_path)},
        )
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    with open(out_path, "w") as f:
        json.dump(template, f, indent=2)

    envelope = create_success_envelope(
        message="Macro template created",
        data={
            "template_path": str(out_path),
            "total_weeks": total_weeks,
            "template_version": template.get("template_version"),
        },
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


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


def _validate_weekly_plan_file(file_path: str, verbose: bool) -> tuple[bool, list[str], list[str]]:
    """Validate weekly plan JSON file; return (is_valid, errors, warnings)."""
    # Stage 1: Syntax validation
    is_syntax_valid, syntax_errors, syntax_warnings = validate_plan_json_structure(file_path, verbose)
    if not is_syntax_valid:
        return False, syntax_errors, syntax_warnings

    # Stage 2: Semantic validation
    semantic_result = validate_week_plan(weekly_plan_path=file_path, verbose=verbose)
    if isinstance(semantic_result, PlanError):
        return False, [semantic_result.message], []

    is_semantic_valid = semantic_result.get("is_valid", False)
    semantic_errors = semantic_result.get("errors", [])
    semantic_warnings = semantic_result.get("warnings", [])
    all_warnings = syntax_warnings + semantic_warnings

    return is_semantic_valid, semantic_errors, all_warnings


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
    baseline_vdot: Optional[float] = typer.Option(
        None,
        "--baseline-vdot",
        help="Approved baseline VDOT for macro plan"
    ),
    macro_template_json: str = typer.Option(
        ...,
        "--macro-template-json",
        help="Path to macro template JSON (generated by sce plan template-macro)"
    ),
) -> None:
    """
    Generate high-level training plan structure (macro plan).

    Creates the structural roadmap for the full training period without detailed
    workout prescriptions. Shows phases, volume progression, CTL trajectory,
    recovery weeks, and macro-level workout structure hints.

    This provides the "big picture" for athlete confidence. Monthly plans provide
    execution detail generated every 4 weeks.

    Examples:
        sce plan create-macro --goal-type half_marathon --race-date 2026-05-03 \\
            --target-time "1:30:00" --total-weeks 16 --start-date 2026-01-20 \\
            --current-ctl 44.0 --baseline-vdot 48.0 \\
            --macro-template-json /tmp/macro_template.json

    Requires an approved baseline VDOT and a filled macro template JSON.

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

    # Enforce baseline VDOT approval before creating macro plan
    if baseline_vdot is None:
        envelope = create_error_envelope(
            error_type="validation",
            message="baseline_vdot is required and must be approved before macro creation",
            data={"next_steps": "Run: sce approvals approve-vdot --value <VDOT>"},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    from sports_coach_engine.core.state import load_approval_state
    from sports_coach_engine.schemas.repository import RepoError
    import math

    approval_state = load_approval_state()
    if isinstance(approval_state, RepoError):
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Failed to load approvals state: {approval_state}",
            data={"path": getattr(approval_state, "path", None)},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    approved_vdot = getattr(approval_state, "approved_baseline_vdot", None) if approval_state else None
    if approved_vdot is None:
        envelope = create_error_envelope(
            error_type="validation",
            message="Approved baseline VDOT not found in approvals state",
            data={"next_steps": "Run: sce approvals approve-vdot --value <VDOT>"},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if not math.isclose(float(baseline_vdot), float(approved_vdot), abs_tol=0.01):
        envelope = create_error_envelope(
            error_type="validation",
            message="Provided baseline_vdot does not match approved baseline VDOT",
            data={"approved_baseline_vdot": approved_vdot, "provided_baseline_vdot": baseline_vdot},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Call API
    json_path = Path(macro_template_json)
    if not json_path.exists():
        envelope = create_error_envelope(
            error_type="not_found",
            message=f"Macro template JSON file not found: {macro_template_json}",
            data={"path": str(json_path.absolute())}
        )
        output_json(envelope)
        raise typer.Exit(code=2)
    try:
        with open(json_path, "r") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Invalid JSON in macro template file: {str(e)}",
            data={"file": macro_template_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if not isinstance(payload, dict) or "volumes_km" not in payload or "workout_structure_hints" not in payload:
        envelope = create_error_envelope(
            error_type="validation",
            message="Macro template must include 'volumes_km' and 'workout_structure_hints'",
            data={"file": macro_template_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if payload.get("template_version") != "macro_template_v1":
        envelope = create_error_envelope(
            error_type="validation",
            message="Macro template missing template_version (generate with sce plan template-macro)",
            data={"file": macro_template_json},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    template_total_weeks = payload.get("total_weeks")
    if template_total_weeks != total_weeks:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"Macro template total_weeks {template_total_weeks} != --total-weeks {total_weeks}",
            data={"file": macro_template_json},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    def _is_placeholder(value):
        """Check if a value is a placeholder."""
        if value is None:
            return True
        if isinstance(value, str):
            # Check for common placeholder patterns
            placeholders = ["TODO", "FILL", "TBD", "<", ">", "XXX", "PLACEHOLDER"]
            return any(p in value.upper() for p in placeholders)
        if isinstance(value, (int, float)):
            # Negative numbers are invalid for volumes/loads
            return value < 0
        return False

    def _find_placeholder_paths(value, path="root", depth=0):
        """Recursively find placeholder paths with max depth limit."""
        if depth > 50:  # Prevent stack overflow on malformed data
            return []

        paths = []
        if _is_placeholder(value):
            paths.append(path)
        elif isinstance(value, dict):
            for key, item in value.items():
                paths.extend(_find_placeholder_paths(item, f"{path}.{key}", depth + 1))
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                paths.extend(_find_placeholder_paths(item, f"{path}[{idx}]", depth + 1))
        return paths

    weekly_volumes_km = payload["weekly_volumes_km"]
    if not isinstance(weekly_volumes_km, list) or len(weekly_volumes_km) == 0:
        envelope = create_error_envelope(
            error_type="validation",
            message="'weekly_volumes_km' must be a non-empty array",
            data={"file": macro_template_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    if len(weekly_volumes_km) != total_weeks:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"'weekly_volumes_km' length {len(weekly_volumes_km)} != total_weeks {total_weeks}",
            data={"file": macro_template_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    # Extract and validate target_systemic_load_au (optional for multi-sport)
    weekly_systemic_load_au = payload.get("target_systemic_load_au")
    if weekly_systemic_load_au is not None:
        if not isinstance(weekly_systemic_load_au, list) or len(weekly_systemic_load_au) == 0:
            envelope = create_error_envelope(
                error_type="validation",
                message="'target_systemic_load_au' must be a non-empty array if provided",
                data={"file": macro_template_json}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

        if len(weekly_systemic_load_au) != total_weeks:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"'target_systemic_load_au' length {len(weekly_systemic_load_au)} != total_weeks {total_weeks}",
                data={"file": macro_template_json}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    placeholder_paths = _find_placeholder_paths(weekly_volumes_km, "weekly_volumes_km")
    if weekly_systemic_load_au is not None:
        placeholder_paths.extend(_find_placeholder_paths(weekly_systemic_load_au, "target_systemic_load_au"))
    weekly_structure_hints = payload["workout_structure_hints"]
    placeholder_paths.extend(_find_placeholder_paths(weekly_structure_hints, "workout_structure_hints"))
    if placeholder_paths:
        envelope = create_error_envelope(
            error_type="validation",
            message="Macro template contains placeholders; fill all required fields",
            data={"missing_fields": placeholder_paths[:20], "file": macro_template_json},
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    for idx, value in enumerate(weekly_volumes_km, start=1):
        if not isinstance(value, (int, float)) or value <= 0:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"weekly_volumes_km[{idx}] must be a positive number",
                data={"file": macro_template_json}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    # Validate systemic load values if provided
    if weekly_systemic_load_au is not None:
        for idx, value in enumerate(weekly_systemic_load_au, start=1):
            if not isinstance(value, (int, float)) or value < 0:
                envelope = create_error_envelope(
                    error_type="validation",
                    message=f"target_systemic_load_au[{idx}] must be a non-negative number",
                    data={"file": macro_template_json}
                )
                output_json(envelope)
                raise typer.Exit(code=5)

    if not isinstance(weekly_structure_hints, list) or len(weekly_structure_hints) == 0:
        envelope = create_error_envelope(
            error_type="validation",
            message="'workout_structure_hints' must be a non-empty array",
            data={"file": macro_template_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)
    if len(weekly_structure_hints) != total_weeks:
        envelope = create_error_envelope(
            error_type="validation",
            message=f"'workout_structure_hints' length {len(weekly_structure_hints)} != total_weeks {total_weeks}",
            data={"file": macro_template_json}
        )
        output_json(envelope)
        raise typer.Exit(code=5)

    from sports_coach_engine.schemas.plan import WorkoutStructureHints
    for idx, hint in enumerate(weekly_structure_hints, start=1):
        try:
            WorkoutStructureHints.model_validate(hint)
        except Exception as e:
            envelope = create_error_envelope(
                error_type="validation",
                message=f"workout_structure_hints[{idx}] invalid: {str(e)}",
                data={"file": macro_template_json}
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    result = create_macro_plan(
        goal_type=goal_type,
        race_date=race_date_parsed,
        target_time=target_time,
        total_weeks=total_weeks,
        start_date=start_date_parsed,
        current_ctl=current_ctl,
        baseline_vdot=baseline_vdot,
        weekly_volumes_km=weekly_volumes_km,
        weekly_systemic_load_au=weekly_systemic_load_au,
        weekly_structure_hints=weekly_structure_hints,
    )

    # Construct success message only if result is successful
    if not isinstance(result, PlanError):
        success_message = (
            f"Training plan skeleton created: {total_weeks} weeks, {len(result.phases)} phases\n"
            f"Saved to: data/plans/current_plan.yaml (0 weeks populated)\n"
            f"Next: Present macro plan to athlete for approval, then use weekly-plan-generate "
            f"+ weekly-plan-apply for Week 1"
        )
    else:
        success_message = "Macro plan creation failed"

    # Convert to envelope
    envelope = api_result_to_envelope(
        result,
        success_message=success_message
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="assess-period")
def assess_period_command(
    ctx: typer.Context,
    month_number: int = typer.Option(..., "--period-number", help="Period number (1-indexed, typically 1-5)"),
    week_numbers: str = typer.Option(..., "--week-numbers", help="Comma-separated week numbers (e.g., '1,2,3,4' or '9,10,11')"),
    planned_workouts_json: str = typer.Option(..., "--planned-workouts", help="Path to JSON file with planned workouts"),
    completed_activities_json: str = typer.Option(..., "--completed-activities", help="Path to JSON file with completed activities"),
    starting_ctl: float = typer.Option(..., "--starting-ctl", help="CTL at period start"),
    ending_ctl: float = typer.Option(..., "--ending-ctl", help="CTL at period end"),
    target_ctl: float = typer.Option(..., "--target-ctl", help="Target CTL for period end"),
    current_vdot: float = typer.Option(..., "--current-vdot", help="VDOT used for period's paces"),
) -> None:
    """
    Assess completed training period for adaptive planning.

    Flexible assessment for any N-week period (typically 2-6 weeks, often 4).
    Analyzes execution and response to inform next planning cycle:
    - Adherence rates
    - CTL progression vs. targets
    - VDOT recalibration needs
    - Injury/illness signals from activity notes
    - Volume tolerance
    - Patterns detected

    Examples:
        # Assess 4-week period (weeks 1-4)
        sce plan assess-period --period-number 1 --week-numbers "1,2,3,4" \\
            --planned-workouts /tmp/planned.json \\
            --completed-activities /tmp/completed.json \\
            --starting-ctl 44.0 --ending-ctl 50.5 --target-ctl 52.0 --current-vdot 48.0

        # Assess 3-week period (weeks 9-11 of an 11-week plan)
        sce plan assess-period --period-number 3 --week-numbers "9,10,11" \\
            --planned-workouts /tmp/planned.json \\
            --completed-activities /tmp/completed.json \\
            --starting-ctl 58.0 --ending-ctl 60.5 --target-ctl 62.0 --current-vdot 49.5

    Returns:
        Period assessment with adherence, CTL analysis, VDOT recommendations,
        signals detected, and recommendations for next period.
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
