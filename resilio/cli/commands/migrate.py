"""Explicit, one-shot local athlete-state migrations."""

import typer

from resilio.cli.output import create_error_envelope, create_success_envelope, output_json
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH
from resilio.core.evidence_migration import EvidenceMigrationError, migrate_evidence_state
from resilio.core.locking import OperationLock, OperationLockError
from resilio.core.planning.constants import PLAN_MUTATION_LOCK_PATH
from resilio.core.repository import RepositoryIO
from resilio.core.state_migration_transaction import recover_state_migration
from resilio.core.workout_fulfillment.migration import (
    WorkoutFulfillmentMigrationError,
    migrate_workout_fulfillment_state,
)
from resilio.core.workout_publication.locking import PUBLICATION_LOCK_PATH

app = typer.Typer(help="Validate or apply explicit athlete-state migrations")


@app.command(name="recover-state")
def recover_state_command() -> None:
    """Recover the exact journaled cutover without running another migration."""
    repo = RepositoryIO()
    try:
        # Recovery alone bypasses the normal gate that blocks prepared state.
        with (
            OperationLock(repo.resolve_path(PUBLICATION_LOCK_PATH), "recover_state_migration"),
            OperationLock(repo.resolve_path(PLAN_MUTATION_LOCK_PATH), "recover_state_migration"),
            OperationLock(
                repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH), "recover_state_migration"
            ),
        ):
            recovered = recover_state_migration(repo)
        envelope = create_success_envelope(
            message="State migration recovered" if recovered else "No pending state migration",
            data={"recovered": recovered},
        )
        exit_code = 0
    except (OperationLockError, OSError, ValueError) as exc:
        envelope = create_error_envelope(error_type="validation", message=str(exc))
        exit_code = 5
    output_json(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="evidence-v5")
def evidence_v5_command(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply the validated cutover; omission performs a read-only dry run",
    ),
) -> None:
    """Migrate canonical activities to v5 and wellness days to v2."""
    try:
        report = migrate_evidence_state(RepositoryIO(), apply=apply)
        envelope = create_success_envelope(
            message=(
                "Evidence-state migration applied"
                if report.applied
                else "Evidence state is already current"
                if apply and not report.changes_required
                else "Evidence-state migration dry run passed"
            ),
            data=report,
        )
        exit_code = 0
    except (EvidenceMigrationError, OSError, ValueError) as exc:
        envelope = create_error_envelope(
            error_type="validation",
            message=str(exc),
        )
        exit_code = 5
    output_json(envelope)
    raise typer.Exit(code=exit_code)


@app.command(name="workout-fulfillment-v2")
def workout_fulfillment_v2_command(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply the backed-up cutover; omission performs a read-only dry run",
    ),
) -> None:
    """Cut over legacy fulfillment state to native activity/event pairing v2."""
    try:
        report = migrate_workout_fulfillment_state(RepositoryIO(), apply=apply)
        envelope = create_success_envelope(
            message=(
                "Workout-fulfillment migration applied"
                if report.applied
                else "Workout-fulfillment state is already current"
                if apply and not report.changes_required
                else "Workout-fulfillment migration dry run passed"
            ),
            data=report,
        )
        exit_code = 0
    except (
        WorkoutFulfillmentMigrationError,
        OperationLockError,
        OSError,
        ValueError,
    ) as exc:
        envelope = create_error_envelope(
            error_type="validation",
            message=str(exc),
        )
        exit_code = 5
    output_json(envelope)
    raise typer.Exit(code=exit_code)
