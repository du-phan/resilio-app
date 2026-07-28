"""Inspect and operate the one-time canonical activity migration."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from resilio.cli.errors import EXIT_SUCCESS
from resilio.cli.output import create_error_envelope, create_success_envelope, output_json
from resilio.core.activity_migration.service import ActivityV2Migrator, MigrationError
from resilio.schemas.migration import MigrationRunEnvelope

app = typer.Typer(help="Inspect or operate the activity archive migration")


def _root(ctx: typer.Context) -> Path:
    return ctx.obj.repo_root or Path.cwd()


def _emit_error(exc: Exception) -> None:
    output_json(
        create_error_envelope(
            error_type="migration",
            message=str(exc),
        )
    )
    raise typer.Exit(code=1)


@app.command("status")
def status_command(ctx: typer.Context) -> None:
    """Show migration runs without mutating the archive."""
    run_root = _root(ctx) / "data/migrations/activity-v2"
    runs: list[dict] = []
    if run_root.is_dir():
        for path in sorted(run_root.glob("*/run.json")):
            try:
                envelope = MigrationRunEnvelope.model_validate_json(path.read_text())
            except Exception as exc:
                _emit_error(
                    MigrationError(
                        f"Invalid migration state: {path.relative_to(_root(ctx))}: "
                        f"{type(exc).__name__}"
                    )
                )
            runs.append(envelope.model_dump(mode="json"))
    output_json(
        create_success_envelope(
            message=f"Found {len(runs)} activity migration run(s)",
            data={"runs": runs},
        )
    )
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("dry-run")
def dry_run_command(ctx: typer.Context) -> None:
    """Build and reconcile a candidate archive without switching it."""
    try:
        report = ActivityV2Migrator(_root(ctx)).dry_run()
    except (MigrationError, ValueError, OSError) as exc:
        _emit_error(exc)
    output_json(
        create_success_envelope(
            message="Activity migration dry run passed",
            data=report.model_dump(mode="json"),
        )
    )
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("apply")
def apply_command(
    ctx: typer.Context,
    input_manifest_sha256: str = typer.Option(
        ...,
        "--input-manifest-sha256",
        help="Exact digest returned by the successful dry run",
    ),
) -> None:
    """Atomically switch to a reconciled candidate archive."""
    try:
        path = ActivityV2Migrator(_root(ctx)).apply(input_manifest_sha256)
    except (MigrationError, ValueError, OSError, json.JSONDecodeError) as exc:
        _emit_error(exc)
    output_json(
        create_success_envelope(
            message="Activity migration applied",
            data={"active_archive": str(path.relative_to(_root(ctx)))},
        )
    )
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("repair-linked-history")
def repair_linked_history_command(
    ctx: typer.Context,
    input_manifest_sha256: str = typer.Option(
        ...,
        "--input-manifest-sha256",
        help="Exact digest of the applied migration",
    ),
) -> None:
    """Restore migrated facts while retaining safe external links/enrichment."""
    try:
        report = ActivityV2Migrator(_root(ctx)).repair_linked_history(
            input_manifest_sha256
        )
    except (MigrationError, ValueError, OSError, json.JSONDecodeError) as exc:
        _emit_error(exc)
    output_json(
        create_success_envelope(
            message="Linked historical facts restored",
            data=report,
        )
    )
    raise typer.Exit(code=EXIT_SUCCESS)


@app.command("rollback")
def rollback_command(
    ctx: typer.Context,
    input_manifest_sha256: str = typer.Option(
        ...,
        "--input-manifest-sha256",
        help="Exact digest of the applied migration",
    ),
) -> None:
    """Restore the verified pre-migration archive."""
    try:
        path = ActivityV2Migrator(_root(ctx)).rollback(input_manifest_sha256)
    except (MigrationError, ValueError, OSError, json.JSONDecodeError) as exc:
        _emit_error(exc)
    output_json(
        create_success_envelope(
            message="Activity migration rolled back and source hashes verified",
            data={"active_archive": str(path.relative_to(_root(ctx)))},
        )
    )
    raise typer.Exit(code=EXIT_SUCCESS)
