"""Current typed Monday-Sunday coaching context."""

from datetime import date, timedelta

import typer

from resilio.api.coaching_context import get_weekly_coach_context
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json


def week_command() -> None:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    result = get_weekly_coach_context(
        week_start=week_start,
        as_of_date=today,
    )
    envelope = api_result_to_envelope(
        result,
        success_message=f"Coaching context for week starting {week_start}",
    )
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))
