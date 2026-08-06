"""Explicit, one-shot local athlete-state migrations."""

import typer

from resilio.cli.output import create_error_envelope, create_success_envelope, output_json
from resilio.core.evidence_migration import EvidenceMigrationError, migrate_evidence_state
from resilio.core.repository import RepositoryIO

app = typer.Typer(help="Validate or apply explicit athlete-state migrations")


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
