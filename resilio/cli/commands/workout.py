"""Publish or delete ownership-proven planned workouts."""

from datetime import date, time

import typer

from resilio.api.publication import (
    delete_published_workout,
    publish_plan_workouts,
    publish_workout,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json

app = typer.Typer(help="Publish structured planned workouts")


def _parse_time(value: str | None) -> time | None:
    if value is None:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("Use HH:MM or HH:MM:SS local time") from exc


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("Use YYYY-MM-DD") from exc


@app.command(name="publish")
def publish_command(
    workout_id: str = typer.Option(..., "--id", help="Local workout ID"),
    start_time: str | None = typer.Option(
        None,
        "--time",
        help="Local start time; otherwise use sport settings",
    ),
) -> None:
    result = publish_workout(
        workout_id,
        start_time_local=_parse_time(start_time),
    )
    envelope = api_result_to_envelope(
        result,
        success_message="Workout publication completed.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="publish-plan")
def publish_plan_command(
    from_date: str | None = typer.Option(
        None,
        "--from",
        help="First local plan date to reconcile; defaults to today",
    ),
) -> None:
    result = publish_plan_workouts(from_date=_parse_date(from_date))
    envelope = api_result_to_envelope(
        result,
        success_message="Future workout publication reconciliation completed.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="delete")
def delete_command(
    workout_id: str = typer.Option(..., "--id", help="Local workout ID"),
) -> None:
    result = delete_published_workout(workout_id)
    envelope = api_result_to_envelope(
        result,
        success_message="Owned workout event deleted.",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
