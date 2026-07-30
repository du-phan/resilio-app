"""Race-goal commands with explicit performance evidence."""

from __future__ import annotations

from datetime import date, timedelta

import typer

from resilio.api.profile import ProfileError, get_profile, set_goal
from resilio.api.vdot import VDOTError, calculate_vdot_from_race
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import create_error_envelope, create_success_envelope, output_json
from resilio.core.vdot import format_time_seconds
from resilio.schemas.profile import GoalType
from resilio.utils.dates import get_next_monday

app = typer.Typer(help="Manage athlete-confirmed race goals")


def _resolve_target_date(
    *,
    race_type: GoalType,
    target_date: str | None,
    horizon_weeks: int | None,
    today: date,
) -> date:
    if target_date is not None and horizon_weeks is not None:
        raise ValueError("Provide either --date or --horizon-weeks, not both.")
    if horizon_weeks is not None and horizon_weeks <= 0:
        raise ValueError("--horizon-weeks must be a positive integer.")
    if target_date is not None:
        try:
            resolved = date.fromisoformat(target_date)
        except ValueError as exc:
            raise ValueError("--date must use YYYY-MM-DD.") from exc
        if resolved < today:
            raise ValueError("--date cannot be in the past.")
        return resolved

    default_horizon_weeks = {
        GoalType.GENERAL_FITNESS: 4,
        GoalType.FIVE_K: 8,
        GoalType.TEN_K: 12,
        GoalType.HALF_MARATHON: 16,
        GoalType.MARATHON: 20,
    }
    weeks = horizon_weeks or default_horizon_weeks[race_type]
    return get_next_monday(today) + timedelta(weeks=weeks, days=-1)


def _target_vdot(race_type: GoalType, target_time: str | None) -> int | None:
    if target_time is None:
        return None
    if race_type is GoalType.GENERAL_FITNESS:
        raise ValueError("general_fitness goals cannot include --time.")

    result = calculate_vdot_from_race(race_type.value, target_time)
    if isinstance(result, VDOTError):
        raise ValueError(result.message)
    return result.vdot


@app.command(name="set")
def goal_set_command(
    ctx: typer.Context,
    race_type: str = typer.Option(
        ...,
        "--type",
        help="Goal type: 5k, 10k, half_marathon, marathon, or general_fitness",
    ),
    target_date: str | None = typer.Option(None, "--date", help="Target date (YYYY-MM-DD)"),
    target_time: str | None = typer.Option(
        None,
        "--time",
        help="Athlete-confirmed target finish time (HH:MM:SS)",
    ),
    horizon_weeks: int | None = typer.Option(
        None,
        "--horizon-weeks",
        help="Positive training horizon in weeks, as an alternative to --date",
    ),
) -> None:
    """Persist a goal and report its exact target VDOT when a time is supplied."""
    del ctx
    try:
        goal_type = GoalType(race_type)
        resolved_date = _resolve_target_date(
            race_type=goal_type,
            target_date=target_date,
            horizon_weeks=horizon_weeks,
            today=date.today(),
        )
        target_vdot = _target_vdot(goal_type, target_time)
    except ValueError as exc:
        output_json(create_error_envelope(error_type="validation", message=str(exc)))
        raise typer.Exit(code=5) from exc

    result = set_goal(
        race_type=goal_type.value,
        target_date=resolved_date,
        target_time=target_time,
    )
    if isinstance(result, ProfileError):
        envelope = api_result_to_envelope(result, success_message="Goal saved")
    else:
        envelope = create_success_envelope(
            message=f"Goal saved: {goal_type.value} on {resolved_date.isoformat()}",
            data={
                "goal": result.model_dump(mode="json"),
                "target_vdot": target_vdot,
                "assessment": (
                    "Target VDOT is a performance requirement, not an automatic "
                    "feasibility verdict. The coach must compare it with approved "
                    "baseline evidence, constraints, and available training time."
                    if target_vdot is not None
                    else None
                ),
            },
        )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="show")
def goal_show_command(ctx: typer.Context) -> None:
    """Show the saved goal and exact target VDOT evidence."""
    del ctx
    profile = get_profile()
    if isinstance(profile, ProfileError):
        envelope = api_result_to_envelope(profile, success_message="Goal loaded")
        output_json(envelope)
        raise typer.Exit(code=get_exit_code_from_envelope(envelope))

    try:
        target_time = (
            format_time_seconds(profile.goal.target_finish_time_seconds)
            if profile.goal.target_finish_time_seconds is not None
            else None
        )
        target_vdot = _target_vdot(profile.goal.type, target_time)
    except ValueError as exc:
        output_json(create_error_envelope(error_type="validation", message=str(exc)))
        raise typer.Exit(code=5) from exc

    output_json(
        create_success_envelope(
            message="Goal loaded",
            data={
                "goal": profile.goal.model_dump(mode="json"),
                "target_vdot": target_vdot,
            },
        )
    )
