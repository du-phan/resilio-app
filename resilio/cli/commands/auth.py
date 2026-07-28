"""Validate the configured personal API credential."""

from pathlib import Path

import typer

from resilio.cli.errors import EXIT_AUTH_FAILURE, EXIT_CONFIG_MISSING, EXIT_SUCCESS
from resilio.cli.output import create_error_envelope, create_success_envelope, output_json
from resilio.core.config import ConfigError, load_config
from resilio.integrations.intervals_icu import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError


app = typer.Typer(help="Validate external account access")


@app.command(name="status")
def auth_status_command(ctx: typer.Context) -> None:
    """Validate the configured key without displaying it."""
    repo_root = ctx.obj.repo_root or Path.cwd()
    config = load_config(repo_root)
    if isinstance(config, ConfigError):
        envelope = create_error_envelope(
            error_type=config.error_type.value,
            message=config.message,
            data={
                "authenticated": False,
                "next_steps": (
                    "Set INTERVALS_ICU_API_KEY in .env.local"
                ),
            },
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_CONFIG_MISSING)

    try:
        with IntervalsIcuClient(config) as client:
            athlete = client.get_athlete()
    except IntervalsIcuError as exc:
        envelope = create_error_envelope(
            error_type=exc.error_type,
            message=str(exc),
            data={"authenticated": False},
        )
        output_json(envelope)
        raise typer.Exit(code=EXIT_AUTH_FAILURE)

    envelope = create_success_envelope(
        message="External account access is valid",
        data={
            "authenticated": True,
            "athlete_id": athlete.id,
            "timezone": athlete.timezone,
        },
    )
    output_json(envelope)
    raise typer.Exit(code=EXIT_SUCCESS)
