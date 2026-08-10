"""Athlete-confirmed profile and provider-candidate commands."""

from __future__ import annotations

from datetime import date
from typing import NoReturn

import typer

from resilio.api.profile import (
    ProfileError,
    create_profile,
    get_profile,
    get_provider_profile_candidates,
    remove_athlete_managed_sport,
    set_flexible_athlete_managed_sport,
    set_personal_best,
    set_recurring_athlete_managed_sport,
    set_sport_active_state,
    set_training_priority,
    update_profile,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json
from resilio.schemas.profile import Weekday

app = typer.Typer(help="Manage athlete-confirmed facts and provider candidates")


def _emit(result: object, message: str) -> NoReturn:
    envelope = api_result_to_envelope(result, success_message=message)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


def _weekdays(value: str | None) -> list[Weekday]:
    if value is None or not value.strip():
        return []
    try:
        return [Weekday(item.strip().casefold()) for item in value.split(",")]
    except ValueError as exc:
        raise typer.BadParameter("Days must be comma-separated weekday names") from exc


@app.command(name="create")
def profile_create_command(
    athlete_name: str = typer.Option(..., "--athlete-name"),
    training_timezone: str = typer.Option(..., "--training-timezone"),
    age_years: int | None = typer.Option(None, "--age-years"),
    running_experience_years: float | None = typer.Option(None, "--running-experience-years"),
    minimum_run_days_per_week: int = typer.Option(2, "--minimum-run-days-per-week"),
    maximum_run_days_per_week: int = typer.Option(4, "--maximum-run-days-per-week"),
    unavailable_run_days: str | None = typer.Option(None, "--unavailable-run-days"),
    maximum_session_duration_minutes: int
    | None = typer.Option(90, "--maximum-session-duration-minutes"),
    weather_location: str | None = typer.Option(None, "--weather-location"),
) -> None:
    _emit(
        create_profile(
            athlete_name=athlete_name,
            training_timezone=training_timezone,
            age_years=age_years,
            running_experience_years=running_experience_years,
            minimum_run_days_per_week=minimum_run_days_per_week,
            maximum_run_days_per_week=maximum_run_days_per_week,
            unavailable_run_days=_weekdays(unavailable_run_days),
            maximum_session_duration_minutes=maximum_session_duration_minutes,
            weather_location=weather_location,
        ),
        "Athlete profile created",
    )


@app.command(name="get")
def profile_get_command() -> None:
    _emit(get_profile(), "Athlete profile loaded")


@app.command(name="set")
def profile_set_command(
    athlete_name: str | None = typer.Option(None, "--athlete-name"),
    training_timezone: str | None = typer.Option(None, "--training-timezone"),
    age_years: int | None = typer.Option(None, "--age-years"),
    running_experience_years: float | None = typer.Option(None, "--running-experience-years"),
    minimum_run_days_per_week: int | None = typer.Option(None, "--minimum-run-days-per-week"),
    maximum_run_days_per_week: int | None = typer.Option(None, "--maximum-run-days-per-week"),
    unavailable_run_days: str | None = typer.Option(None, "--unavailable-run-days"),
    maximum_session_duration_minutes: int
    | None = typer.Option(None, "--maximum-session-duration-minutes"),
    weather_location: str | None = typer.Option(None, "--weather-location"),
) -> None:
    profile = get_profile()
    if isinstance(profile, ProfileError):
        _emit(profile, "Athlete profile updated")
    fields: dict[str, object] = {}
    for name, value in [
        ("athlete_name", athlete_name),
        ("training_timezone", training_timezone),
        ("age_years", age_years),
        ("running_experience_years", running_experience_years),
    ]:
        if value is not None:
            fields[name] = value

    constraint_updates: dict[str, object] = {
        name: value
        for name, value in [
            ("minimum_run_days_per_week", minimum_run_days_per_week),
            ("maximum_run_days_per_week", maximum_run_days_per_week),
            (
                "maximum_session_duration_minutes",
                maximum_session_duration_minutes,
            ),
        ]
        if value is not None
    }
    if unavailable_run_days is not None:
        constraint_updates["unavailable_run_days"] = [
            item.value for item in _weekdays(unavailable_run_days)
        ]
    if constraint_updates:
        constraints = profile.constraints.model_dump(mode="json")
        constraints.update(constraint_updates)
        fields["constraints"] = constraints
    if weather_location is not None:
        fields["weather_preferences"] = {"location_query": weather_location.strip()}
    _emit(update_profile(**fields), "Athlete profile updated")


@app.command(name="candidates")
def profile_candidates_command(
    as_of_date: str | None = typer.Option(None, "--as-of-date"),
) -> None:
    try:
        resolved_date = date.fromisoformat(as_of_date) if as_of_date is not None else date.today()
    except ValueError as exc:
        raise typer.BadParameter("--as-of-date must use YYYY-MM-DD") from exc
    _emit(
        get_provider_profile_candidates(as_of_date=resolved_date),
        "Provider profile candidates loaded",
    )


@app.command(name="set-personal-best")
def profile_set_personal_best_command(
    distance: str = typer.Option(..., "--distance"),
    elapsed_time: str = typer.Option(..., "--elapsed-time"),
    performance_date: str = typer.Option(..., "--performance-date"),
) -> None:
    try:
        parsed_date = date.fromisoformat(performance_date)
    except ValueError as exc:
        raise typer.BadParameter("--performance-date must use YYYY-MM-DD") from exc
    _emit(
        set_personal_best(
            distance=distance,
            elapsed_time=elapsed_time,
            performance_date=parsed_date,
        ),
        "Personal best saved",
    )


@app.command(name="set-flexible-sport")
def profile_set_flexible_sport_command(
    sport_name: str = typer.Option(..., "--sport-name"),
    expected_sessions_per_week: int = typer.Option(..., "--expected-sessions-per-week"),
    typical_session_duration_minutes: int = typer.Option(60, "--typical-session-duration-minutes"),
    typical_intensity: str = typer.Option("moderate", "--typical-intensity"),
    athlete_context_note: str | None = typer.Option(None, "--athlete-context-note"),
) -> None:
    _emit(
        set_flexible_athlete_managed_sport(
            sport_name=sport_name,
            expected_sessions_per_week=expected_sessions_per_week,
            typical_session_duration_minutes=typical_session_duration_minutes,
            typical_intensity=typical_intensity,
            athlete_context_note=athlete_context_note,
        ),
        "Flexible athlete-managed sport saved",
    )


@app.command(name="set-recurring-sport")
def profile_set_recurring_sport_command(
    sport_name: str = typer.Option(..., "--sport-name"),
    weekdays: str = typer.Option(..., "--weekdays"),
    run_same_day_permission: str = typer.Option(..., "--run-same-day-permission"),
    typical_session_duration_minutes: int = typer.Option(60, "--typical-session-duration-minutes"),
    typical_intensity: str = typer.Option("moderate", "--typical-intensity"),
    athlete_context_note: str | None = typer.Option(None, "--athlete-context-note"),
) -> None:
    _emit(
        set_recurring_athlete_managed_sport(
            sport_name=sport_name,
            weekdays=_weekdays(weekdays),
            run_same_day_permission=run_same_day_permission,
            typical_session_duration_minutes=typical_session_duration_minutes,
            typical_intensity=typical_intensity,
            athlete_context_note=athlete_context_note,
        ),
        "Recurring athlete-managed sport saved",
    )


@app.command(name="set-training-priority")
def profile_set_training_priority_command(
    kind: str = typer.Option(..., "--kind"),
    priority_sport_name: str | None = typer.Option(None, "--priority-sport-name"),
) -> None:
    _emit(
        set_training_priority(
            kind=kind,
            priority_sport_name=priority_sport_name,
        ),
        "Training priority saved",
    )


@app.command(name="remove-athlete-managed-sport")
def profile_remove_athlete_managed_sport_command(
    sport_name: str = typer.Option(..., "--sport-name"),
) -> None:
    _emit(remove_athlete_managed_sport(sport_name), "Athlete-managed sport removed")


@app.command(name="pause-sport")
def profile_pause_sport_command(
    sport_name: str = typer.Option(..., "--sport-name"),
    reason: str = typer.Option(..., "--reason"),
    paused_on: str | None = typer.Option(None, "--paused-on"),
) -> None:
    try:
        parsed_date = date.fromisoformat(paused_on) if paused_on else None
    except ValueError as exc:
        raise typer.BadParameter("--paused-on must use YYYY-MM-DD") from exc
    _emit(
        set_sport_active_state(
            sport_name=sport_name,
            active=False,
            pause_reason=reason,
            paused_on=parsed_date,
        ),
        "Athlete-managed sport paused",
    )


@app.command(name="resume-sport")
def profile_resume_sport_command(
    sport_name: str = typer.Option(..., "--sport-name"),
) -> None:
    _emit(
        set_sport_active_state(sport_name=sport_name, active=True),
        "Athlete-managed sport resumed",
    )
