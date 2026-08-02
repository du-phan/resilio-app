"""Configure and reconcile approved running workouts."""

from datetime import date
from typing import Literal, cast

import typer

from resilio.api.publication import (
    configure_run_workout_synchronization,
    get_run_workout_synchronization_capabilities,
    get_run_workout_synchronization_preferences,
    get_week_run_workout_sync_status,
    reconcile_week_run_workouts,
    restore_local_week_run_workouts,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json

app = typer.Typer(help="Synchronize approved running workouts")


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("Use YYYY-MM-DD") from exc


def _emit(result: object, success_message: str) -> None:
    envelope = api_result_to_envelope(result, success_message=success_message)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command(name="config")
def config_command() -> None:
    _emit(
        get_run_workout_synchronization_preferences(),
        "Workout synchronization preferences loaded.",
    )


@app.command(name="configure")
def configure_command(
    run_mode: str = typer.Option(..., "--run-mode"),
    confirmation_reference: str | None = typer.Option(
        None,
        "--confirmation-reference",
    ),
) -> None:
    _emit(
        configure_run_workout_synchronization(
            run_synchronization_mode=cast(
                Literal["disabled", "after_weekly_apply"],
                run_mode,
            ),
            athlete_confirmation_reference=confirmation_reference,
        ),
        "Workout synchronization preferences updated.",
    )


@app.command(name="capabilities")
def capabilities_command(
    sport: str = typer.Option("run", "--sport"),
) -> None:
    if sport != "run":
        raise typer.BadParameter(
            "Only running-workout synchronization is supported",
            param_hint="--sport",
        )
    _emit(
        get_run_workout_synchronization_capabilities(),
        "Run synchronization capabilities loaded.",
    )


@app.command(name="status")
def status_command(
    week_number: int = typer.Option(..., "--week-number", min=1),
    as_of_date: str | None = typer.Option(None, "--as-of"),
) -> None:
    _emit(
        get_week_run_workout_sync_status(
            week_number,
            as_of_date=_parse_date(as_of_date),
        ),
        "Run workout synchronization status loaded.",
    )


@app.command(name="reconcile")
def reconcile_command(
    week_number: int = typer.Option(..., "--week-number", min=1),
    as_of_date: str | None = typer.Option(None, "--as-of"),
) -> None:
    _emit(
        reconcile_week_run_workouts(
            week_number,
            as_of_date=_parse_date(as_of_date),
        ),
        "Approved running workouts reconciled.",
    )


@app.command(name="resolve-drift")
def resolve_drift_command(
    week_number: int = typer.Option(..., "--week-number", min=1),
    restore_local: bool = typer.Option(False, "--restore-local"),
    confirmation_reference: str = typer.Option(..., "--confirmation-reference"),
    as_of_date: str | None = typer.Option(None, "--as-of"),
) -> None:
    if not restore_local:
        raise typer.BadParameter(
            "Only the explicit --restore-local strategy is supported",
            param_hint="--restore-local",
        )
    _emit(
        restore_local_week_run_workouts(
            week_number,
            athlete_confirmation_reference=confirmation_reference,
            as_of_date=_parse_date(as_of_date),
        ),
        "Owned remote drift replaced from the approved local week.",
    )
