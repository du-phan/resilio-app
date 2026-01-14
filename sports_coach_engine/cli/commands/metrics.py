"""
sce metrics - Manage training metrics.

Commands for recomputing metrics from local activity files without syncing from Strava.
"""

from datetime import datetime
from typing import Optional

import typer

from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.core.workflows import recompute_all_metrics
from sports_coach_engine.cli.output import output_json, OutputEnvelope

app = typer.Typer(name="metrics", help="Manage training metrics")


@app.command("recompute")
def recompute_metrics(
    ctx: typer.Context,
    start_date: Optional[str] = typer.Option(
        None,
        "--start",
        help="Start date (YYYY-MM-DD, default: earliest activity)",
    ),
    end_date: Optional[str] = typer.Option(
        None,
        "--end",
        help="End date (YYYY-MM-DD, default: today)",
    ),
):
    """
    Recompute metrics from activity files on disk.

    Reads all activity files, recomputes daily metrics (including rest days),
    and updates weekly summary. Does NOT sync from Strava.

    Use cases:
    - Fix metric calculation bugs without re-syncing
    - Backfill rest days for historical data
    - Regenerate metrics after manual activity edits

    Examples:
        sce metrics recompute                          # Full recompute
        sce metrics recompute --start 2025-06-01       # From June onwards
        sce metrics recompute --start 2025-12-01 --end 2026-01-14  # Specific range
    """
    repo = RepositoryIO()

    # Parse dates
    start = None
    if start_date:
        try:
            start = datetime.fromisoformat(start_date).date()
        except ValueError:
            envelope = OutputEnvelope(
                schema_version="1.0",
                ok=False,
                error_type="invalid_input",
                message=f"Invalid start date: {start_date}. Use YYYY-MM-DD format.",
                data=None,
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    end = None
    if end_date:
        try:
            end = datetime.fromisoformat(end_date).date()
        except ValueError:
            envelope = OutputEnvelope(
                schema_version="1.0",
                ok=False,
                error_type="invalid_input",
                message=f"Invalid end date: {end_date}. Use YYYY-MM-DD format.",
                data=None,
            )
            output_json(envelope)
            raise typer.Exit(code=5)

    # Recompute metrics
    try:
        result = recompute_all_metrics(repo, start_date=start, end_date=end)

        # Success
        envelope = OutputEnvelope(
            schema_version="1.0",
            ok=True,
            error_type=None,
            message=f"Recomputed {result['metrics_computed']} days of metrics",
            data={
                "start_date": result['start_date'].isoformat(),
                "end_date": result['end_date'].isoformat(),
                "metrics_computed": result['metrics_computed'],
                "rest_days_filled": result['rest_days_filled'],
            },
        )
        output_json(envelope)

    except Exception as e:
        # Error
        error_type = "unknown"
        if "No activities found" in str(e):
            error_type = "no_data"

        envelope = OutputEnvelope(
            schema_version="1.0",
            ok=False,
            error_type=error_type,
            message=f"Recompute failed: {str(e)}",
            data=None,
        )
        output_json(envelope)
        raise typer.Exit(code=1)
