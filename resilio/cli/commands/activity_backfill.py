"""Operate the approved historical bouldering backfill."""

from __future__ import annotations

import typer

from resilio.api.historical_backfill import (
    dry_run_historical_backfill,
    historical_backfill_status,
    mutate_historical_backfill,
    record_historical_backfill_approval,
)
from resilio.cli.errors import api_result_to_envelope, get_exit_code_from_envelope
from resilio.cli.output import output_json
from resilio.schemas.historical_backfill import ApprovalStage

app = typer.Typer(help="Publish approved historical bouldering without changing metrics")


def _root(ctx: typer.Context):
    return ctx.obj.repo_root


def _emit(result, message: str) -> None:
    envelope = api_result_to_envelope(result, success_message=message)
    output_json(envelope)
    raise typer.Exit(code=get_exit_code_from_envelope(envelope))


@app.command("status")
def status_command(ctx: typer.Context) -> None:
    """Inspect immutable runs, pending intents, and ownership receipts."""
    _emit(
        historical_backfill_status(repo_root=_root(ctx)),
        "Historical activity backfill status fetched.",
    )


@app.command("dry-run")
def dry_run_command(
    ctx: typer.Context,
    confirm_downloads_disabled: bool = typer.Option(
        False,
        "--confirm-downloads-disabled",
        help=(
            "Record that future activity downloads were disabled in the "
            "Intervals.icu UI"
        ),
    ),
) -> None:
    """Re-fetch inventory and create an immutable, non-publishing plan."""
    _emit(
        dry_run_historical_backfill(
            downloads_disabled_confirmed=confirm_downloads_disabled,
            repo_root=_root(ctx),
        ),
        "Historical activity backfill dry run passed.",
    )


@app.command("record-approval")
def record_approval_command(
    ctx: typer.Context,
    stage: ApprovalStage = typer.Option(..., "--stage"),
    plan_digest: str = typer.Option(..., "--plan-digest"),
    canary_digest: str | None = typer.Option(None, "--canary-digest"),
) -> None:
    """Record the athlete's separate approval for one mutation stage."""
    _emit(
        record_historical_backfill_approval(
            stage=stage,
            plan_digest_sha256=plan_digest,
            canary_digest_sha256=canary_digest,
            repo_root=_root(ctx),
        ),
        f"Historical activity backfill {stage.value} approval recorded.",
    )


@app.command("canary")
def canary_command(
    ctx: typer.Context,
    plan_digest: str = typer.Option(..., "--plan-digest"),
) -> None:
    """Publish and prove only the separately approved canary."""
    _emit(
        mutate_historical_backfill(
            operation="canary",
            plan_digest_sha256=plan_digest,
            repo_root=_root(ctx),
        ),
        "Historical activity canary verified.",
    )


def _approved_mutation(
    ctx: typer.Context,
    *,
    operation: str,
    plan_digest: str,
    canary_digest: str,
) -> None:
    _emit(
        mutate_historical_backfill(
            operation=operation,
            plan_digest_sha256=plan_digest,
            canary_digest_sha256=canary_digest,
            repo_root=_root(ctx),
        ),
        f"Historical activity backfill {operation} completed.",
    )


@app.command("apply")
def apply_command(
    ctx: typer.Context,
    plan_digest: str = typer.Option(..., "--plan-digest"),
    canary_digest: str = typer.Option(..., "--canary-digest"),
) -> None:
    """Apply the separately approved checkpointed batches."""
    _approved_mutation(
        ctx,
        operation="apply",
        plan_digest=plan_digest,
        canary_digest=canary_digest,
    )


@app.command("resume")
def resume_command(
    ctx: typer.Context,
    plan_digest: str = typer.Option(..., "--plan-digest"),
    canary_digest: str = typer.Option(..., "--canary-digest"),
) -> None:
    """Recover uncertain outcomes and continue only proven-absent records."""
    _approved_mutation(
        ctx,
        operation="resume",
        plan_digest=plan_digest,
        canary_digest=canary_digest,
    )


@app.command("rollback")
def rollback_command(
    ctx: typer.Context,
    plan_digest: str = typer.Option(..., "--plan-digest"),
    canary_digest: str = typer.Option(..., "--canary-digest"),
) -> None:
    """Delete only exact owned activities and restore verified local originals."""
    _approved_mutation(
        ctx,
        operation="rollback",
        plan_digest=plan_digest,
        canary_digest=canary_digest,
    )


@app.command("set-default-rpe")
def set_default_rpe_command(
    ctx: typer.Context,
    value: int = typer.Option(..., "--value", min=1, max=10),
    plan_digest: str = typer.Option(..., "--plan-digest"),
    canary_digest: str = typer.Option(..., "--canary-digest"),
) -> None:
    """Set RPE only on exact owned backfill activities that have none."""
    _emit(
        mutate_historical_backfill(
            operation="set-default-rpe",
            plan_digest_sha256=plan_digest,
            canary_digest_sha256=canary_digest,
            default_rpe=value,
            repo_root=_root(ctx),
        ),
        "Historical activity default RPE repair completed.",
    )
