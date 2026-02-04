"""
sce init - Initialize data directory structure.

Creates the required directory structure and template files for the Sports Coach Engine.
Safe to run multiple times (idempotent).
"""

import shutil
from pathlib import Path
from typing import List

import typer

from sports_coach_engine.cli.errors import get_exit_code_from_envelope
from sports_coach_engine.schemas.config import PathSettings
from sports_coach_engine.cli.output import create_success_envelope, output_json


def init_command(ctx: typer.Context) -> None:
    """Initialize data directory structure and config templates.

    Creates:
    - data/athlete/, data/activities/, data/metrics/, data/plans/ directories
    - config/ directory with settings.yaml and secrets.local.yaml templates

    Safe to run multiple times - won't overwrite existing files.
    """
    # Get repo_root from context (or use --repo-root if provided)
    cli_ctx = ctx.obj
    repo_root = cli_ctx.repo_root or Path.cwd()

    # Track what we create/skip
    created: List[str] = []
    skipped: List[str] = []

    # Define directory structure
    paths = PathSettings()
    data_dirs = [
        repo_root / paths.athlete_dir,
        repo_root / paths.activities_dir,
        repo_root / paths.metrics_dir / "daily",
        repo_root / paths.metrics_dir / "weekly",
        repo_root / paths.plans_dir / "archive",
        repo_root / paths.plans_dir / "workouts",
        repo_root / paths.state_dir,
    ]

    config_dir = repo_root / "config"

    # Create data directories
    for directory in data_dirs:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(str(directory.relative_to(repo_root)))
        else:
            skipped.append(str(directory.relative_to(repo_root)))

    # Create config directory
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        created.append(str(config_dir.relative_to(repo_root)))
    else:
        skipped.append(str(config_dir.relative_to(repo_root)))

    # Create/copy config files
    _setup_config_files(repo_root, config_dir, created, skipped)

    # Build success envelope
    envelope = create_success_envelope(
        message=f"Initialized data directory structure ({len(created)} created, {len(skipped)} already existed)",
        data={
            "created": created,
            "skipped": skipped,
            "next_steps": [
                "Edit config/secrets.local.yaml with your Strava credentials",
                "Run: sce auth url to get OAuth authorization link",
            ],
        },
    )

    # Output JSON
    output_json(envelope)

    # Exit with appropriate code
    exit_code = get_exit_code_from_envelope(envelope)
    raise typer.Exit(code=exit_code)


def _setup_config_files(
    repo_root: Path,
    config_dir: Path,
    created: List[str],
    skipped: List[str],
) -> None:
    """Set up configuration files (settings.yaml, secrets.local.yaml).

    Args:
        repo_root: Repository root path
        config_dir: Config directory path
        created: List to append created files to
        skipped: List to append skipped files to
    """
    templates_dir = repo_root / "templates"

    # settings.yaml
    settings_file = config_dir / "settings.yaml"
    settings_template = templates_dir / "settings.yaml"

    if not settings_file.exists():
        if settings_template.exists():
            shutil.copy(settings_template, settings_file)
            created.append(str(settings_file.relative_to(repo_root)))
        else:
            # Fallback: create minimal settings inline
            settings_file.write_text(
                """# Sports Coach Engine Settings
_schema:
  format_version: "1.0.0"
  schema_type: "settings"

# Data paths (relative to repo root)
paths:
  athlete_dir: "data/athlete"
  activities_dir: "data/activities"
  metrics_dir: "data/metrics"
  plans_dir: "data/plans"
  state_dir: "data/state"

# Strava API endpoints
strava:
  auth_url: "https://www.strava.com/oauth/authorize"
  token_url: "https://www.strava.com/oauth/token"
  api_base: "https://www.strava.com/api/v3"
  scopes: ["activity:read_all"]
"""
            )
            created.append(str(settings_file.relative_to(repo_root)))
    else:
        skipped.append(str(settings_file.relative_to(repo_root)))

    # secrets.local.yaml
    secrets_file = config_dir / "secrets.local.yaml"
    secrets_template = templates_dir / "secrets.local.yaml"

    if not secrets_file.exists():
        if secrets_template.exists():
            shutil.copy(secrets_template, secrets_file)
            created.append(str(secrets_file.relative_to(repo_root)))
        else:
            # Fallback: create template inline
            secrets_file.write_text(
                """# DO NOT COMMIT THIS FILE
# Add to .gitignore immediately

_schema:
  format_version: "1.0.0"
  schema_type: "secrets"

strava:
  client_id: "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"
  access_token: null
  refresh_token: null
  token_expires_at: null
"""
            )
            created.append(str(secrets_file.relative_to(repo_root)))
    else:
        skipped.append(str(secrets_file.relative_to(repo_root)))
