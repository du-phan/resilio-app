"""Day-specific facts without automatic workout recommendations."""

from datetime import date, timedelta
from typing import Optional

import typer

from resilio.api.coaching_context import CoachingContextError, get_weekly_coach_context
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json


def today_command(
    target_date_text: Optional[str] = typer.Option(
        None,
        "--date",
        help="Local date in YYYY-MM-DD format; defaults to today",
    ),
) -> None:
    result: object
    try:
        target_date = (
            date.fromisoformat(target_date_text) if target_date_text is not None else date.today()
        )
    except ValueError as exc:
        result = CoachingContextError(
            "validation",
            f"Date must use YYYY-MM-DD format: {exc}",
        )
    else:
        week_start = target_date - timedelta(days=target_date.weekday())
        context = get_weekly_coach_context(
            week_start=week_start,
            as_of_date=target_date,
        )
        if isinstance(context, CoachingContextError):
            result = context
        else:
            result = {
                "local_date": target_date,
                "training_state": context.training_state,
                "recovery": context.recovery,
                "completed_activities": [
                    activity
                    for activity in context.activities
                    if activity.local_date == target_date
                ],
                "planned_workouts": [
                    workout
                    for workout in context.adherence.workouts
                    if workout.occurrence_date == target_date
                ],
            }
    envelope = api_result_to_envelope(
        result,
        success_message=f"Training facts for {target_date_text or 'today'}",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
