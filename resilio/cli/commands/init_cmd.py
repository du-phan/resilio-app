"""
resilio init - Initialize data directory structure.

Creates the required directory structure and template files for the Resilio.
Safe to run multiple times (idempotent).
"""

import shutil
from pathlib import Path
from typing import List

import typer

from resilio.cli.errors import get_exit_code_from_envelope
from resilio.schemas.config import PathSettings
from resilio.cli.output import create_success_envelope, output_json


def init_command(ctx: typer.Context) -> None:
    """Initialize data directory structure and config templates.

    Creates:
    - data/athlete/, data/activities/, data/metrics/, data/plans/ directories
    - config/ directory with settings.yaml
    - .env.local API-key template

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
                "Set INTERVALS_ICU_API_KEY in .env.local",
                "Run: resilio auth status",
                "Log in to Intervals.icu at least once every 90 days on a free account",
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
    """Set up non-secret settings and the local environment template.

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
                """# Resilio Settings
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

# External activity/calendar integration
intervals_icu:
  api_base_url: "https://intervals.icu/api/v1"
  athlete_alias: "0"
  history_start_date: "2022-01-20"
"""
            )
            created.append(str(settings_file.relative_to(repo_root)))
    else:
        skipped.append(str(settings_file.relative_to(repo_root)))

    environment_file = repo_root / ".env.local"
    if not environment_file.exists():
        environment_file.write_text(
            "# DO NOT COMMIT THIS FILE\n"
            "INTERVALS_ICU_API_KEY=\n"
        )
        environment_file.chmod(0o600)
        created.append(str(environment_file.relative_to(repo_root)))
    else:
        skipped.append(str(environment_file.relative_to(repo_root)))
