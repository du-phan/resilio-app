"""Typed coaching-context inspection and evidence creation commands."""

from __future__ import annotations

from datetime import date

import typer

from resilio.api.coaching_context import (
    CoachingContextError,
    create_week_planning_context_evidence,
    get_coach_history,
    get_weekly_coach_context,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json

app = typer.Typer(
    name="coach",
    help="Build typed context for coaching procedures",
    no_args_is_help=True,
)


@app.command("context")
def context_command(
    week_start: str = typer.Option(
        ...,
        "--week-start",
        help="Monday starting the requested training week",
    ),
    as_of_date: str = typer.Option(
        ...,
        "--as-of",
        help="Latest local date whose facts may be included",
    ),
) -> None:
    """Return plan, activity, training-state, wellness, and coverage context."""
    result: object
    try:
        parsed_week_start = date.fromisoformat(week_start)
        parsed_as_of_date = date.fromisoformat(as_of_date)
    except ValueError as exc:
        result = CoachingContextError(
            error_type="validation",
            message=f"Dates must use YYYY-MM-DD format: {exc}",
        )
    else:
        result = get_weekly_coach_context(
            week_start=parsed_week_start,
            as_of_date=parsed_as_of_date,
        )
    envelope = api_result_to_envelope(
        result,
        success_message=f"Coaching context for week starting {week_start}",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command("history")
def history_command(
    as_of_date: str = typer.Option(..., "--as-of"),
    week_count: int = typer.Option(..., "--weeks", min=1, max=52),
) -> None:
    """Return contiguous weekly evidence ending in the as-of target week."""
    try:
        parsed_as_of_date = date.fromisoformat(as_of_date)
    except ValueError as exc:
        result: object = CoachingContextError(
            error_type="validation",
            message=f"Dates must use YYYY-MM-DD format: {exc}",
        )
    else:
        result = get_coach_history(
            as_of_date=parsed_as_of_date,
            week_count=week_count,
        )
    envelope = api_result_to_envelope(
        result,
        success_message=f"{week_count}-week coaching history through {as_of_date}",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command("create-planning-context")
def create_planning_context_command(
    week_number: int = typer.Option(..., "--week", min=1),
    evidence_as_of_date: str = typer.Option(..., "--evidence-as-of"),
    history_week_count: int = typer.Option(
        6,
        "--history-weeks",
        min=1,
        max=52,
    ),
) -> None:
    """Persist the exact future-week evidence used to author a proposal."""
    try:
        parsed_evidence_as_of_date = date.fromisoformat(evidence_as_of_date)
    except ValueError as exc:
        result: object = CoachingContextError(
            error_type="validation",
            message=f"Dates must use YYYY-MM-DD format: {exc}",
        )
    else:
        result = create_week_planning_context_evidence(
            week_number=week_number,
            evidence_as_of_date=parsed_evidence_as_of_date,
            history_week_count=history_week_count,
        )
    envelope = api_result_to_envelope(
        result,
        success_message=(f"Planning context for macro week {week_number}"),
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
