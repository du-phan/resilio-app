"""Configure and reconcile approved running workouts."""

from datetime import date
from typing import Literal, cast

import typer

from resilio.api.publication import (
    configure_run_workout_synchronization,
    get_run_workout_synchronization_capabilities,
    get_run_workout_synchronization_preferences,
    get_week_run_workout_sync_status,
    reconcile_remote_workout_pairing_operations,
    reconcile_week_run_workouts,
    resolve_week_run_workout_pairing_drift,
    restore_local_week_run_workouts,
)
from resilio.api.workout_fulfillment import (
    confirm_workout_fulfillment,
    dismiss_workout_fulfillment_candidate,
    get_workout_fulfillment_candidates,
    get_workout_fulfillment_week_status,
    revoke_workout_fulfillment,
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


@app.command(name="reconcile-pairing-operations")
def reconcile_pairing_operations_command() -> None:
    _emit(
        reconcile_remote_workout_pairing_operations(),
        "Durable native pairing operations reconciled.",
    )


@app.command(name="resolve-drift")
def resolve_drift_command(
    week_number: int = typer.Option(..., "--week-number", min=1),
    confirmation_reference: str = typer.Option(..., "--confirmation-reference"),
    drift_target_tokens: list[str] | None = typer.Option(
        None,
        "--drift-target-token",
    ),
    as_of_date: str | None = typer.Option(None, "--as-of"),
) -> None:
    operation = restore_local_week_run_workouts(
        week_number,
        athlete_confirmation_reference=confirmation_reference,
        confirmed_drift_target_tokens=drift_target_tokens or [],
        as_of_date=_parse_date(as_of_date),
    )
    _emit(
        operation,
        "Owned remote drift replaced from the approved local week.",
    )


@app.command(name="resolve-pairing-drift")
def resolve_pairing_drift_command(
    week_number: int = typer.Option(..., "--week-number", min=1),
    confirmation_reference: str = typer.Option(..., "--confirmation-reference"),
    pairing_drift_tokens: list[str] | None = typer.Option(
        None,
        "--pairing-drift-token",
    ),
    as_of_date: str | None = typer.Option(None, "--as-of"),
) -> None:
    _emit(
        resolve_week_run_workout_pairing_drift(
            week_number,
            athlete_confirmation_reference=confirmation_reference,
            confirmed_pairing_drift_tokens=pairing_drift_tokens or [],
            as_of_date=_parse_date(as_of_date),
        ),
        "Confirmed native activity/event pairing drift reconciled.",
    )


@app.command(name="fulfillment-candidates")
def fulfillment_candidates_command(
    local_activity_id: str = typer.Option(..., "--activity-id"),
) -> None:
    _emit(
        get_workout_fulfillment_candidates(local_activity_id=local_activity_id),
        "Workout fulfillment candidates loaded.",
    )


@app.command(name="confirm-fulfillment")
def confirm_fulfillment_command(
    local_activity_id: str = typer.Option(..., "--activity-id"),
    local_workout_id: str = typer.Option(..., "--workout-id"),
    candidate_sha256: str = typer.Option(..., "--candidate-sha256"),
    confirmation_reference: str = typer.Option(..., "--confirmation-reference"),
    coaching_rationale: str = typer.Option(..., "--rationale"),
) -> None:
    _emit(
        confirm_workout_fulfillment(
            local_activity_id=local_activity_id,
            local_workout_id=local_workout_id,
            candidate_sha256=candidate_sha256,
            athlete_confirmation_reference=confirmation_reference,
            coaching_rationale=coaching_rationale,
        ),
        "Workout fulfillment recorded.",
    )


@app.command(name="dismiss-fulfillment-candidate")
def dismiss_fulfillment_candidate_command(
    local_activity_id: str = typer.Option(..., "--activity-id"),
    local_workout_id: str = typer.Option(..., "--workout-id"),
    candidate_sha256: str = typer.Option(..., "--candidate-sha256"),
    athlete_response_reference: str = typer.Option(..., "--response-reference"),
) -> None:
    _emit(
        dismiss_workout_fulfillment_candidate(
            local_activity_id=local_activity_id,
            local_workout_id=local_workout_id,
            candidate_sha256=candidate_sha256,
            athlete_response_reference=athlete_response_reference,
        ),
        "Workout fulfillment candidate dismissed.",
    )


@app.command(name="revoke-fulfillment")
def revoke_fulfillment_command(
    local_activity_id: str = typer.Option(..., "--activity-id"),
    local_workout_id: str = typer.Option(..., "--workout-id"),
    reason: str = typer.Option(..., "--reason"),
    confirmation_reference: str = typer.Option(..., "--confirmation-reference"),
    coaching_rationale: str = typer.Option(..., "--rationale"),
) -> None:
    allowed_reasons = {
        "activity_deleted",
        "activity_reclassified",
        "association_incorrect",
    }
    if reason not in allowed_reasons:
        raise typer.BadParameter(
            "Use activity_deleted, activity_reclassified, or association_incorrect",
            param_hint="--reason",
        )
    _emit(
        revoke_workout_fulfillment(
            local_activity_id=local_activity_id,
            local_workout_id=local_workout_id,
            reason=cast(
                Literal[
                    "activity_deleted",
                    "activity_reclassified",
                    "association_incorrect",
                ],
                reason,
            ),
            athlete_confirmation_reference=confirmation_reference,
            coaching_rationale=coaching_rationale,
        ),
        "Workout fulfillment revoked and its schedule state reopened.",
    )


@app.command(name="fulfillment-status")
def fulfillment_status_command(
    week_number: int = typer.Option(..., "--week-number", min=1),
) -> None:
    _emit(
        get_workout_fulfillment_week_status(week_number=week_number),
        "Workout fulfillment status loaded.",
    )
