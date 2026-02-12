"""
M2 - Config & Secrets

Load configuration from settings.yaml and secrets from secrets.local.yaml.
Validate required keys and provide explicit error messages for missing secrets.
"""

import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from sports_coach_engine.schemas.config import (
    Config,
    ConfigErrorType,
    Secrets,
    Settings,
)


# ============================================================
# ERROR TYPES
# ============================================================


class ConfigError:
    """Configuration error with details."""

    def __init__(
        self, error_type: ConfigErrorType, message: str, path: Optional[str] = None
    ):
        self.error_type = error_type
        self.message = message
        self.path = path


ConfigResult = Union[Config, ConfigError]


# ============================================================
# REPOSITORY ROOT DETECTION
# ============================================================


def get_repo_root() -> Path:
    """
    Find repository root by walking up from current directory.

    Searches for either a .git directory or CLAUDE.md file to identify
    the repository root.

    Returns:
        Path to repository root

    Raises:
        FileNotFoundError: If root cannot be determined (walked to filesystem root)
    """
    current = Path.cwd()

    while True:
        # Check for .git directory
        if (current / ".git").exists():
            return current

        # Check for CLAUDE.md
        if (current / "CLAUDE.md").exists():
            return current

        # Move to parent
        parent = current.parent

        # If we've reached filesystem root, fail
        if parent == current:
            raise FileNotFoundError(
                "Could not find repository root (.git or CLAUDE.md not found). "
                "Are you running from within the repository?"
            )

        current = parent


# ============================================================
# CONFIGURATION LOADING
# ============================================================


def load_config(repo_root: Optional[Path] = None) -> ConfigResult:
    """
    Load and validate complete configuration.

    Args:
        repo_root: Repository root directory (auto-detected if None)

    Returns:
        Config object or ConfigError

    Load order:
        1. Load settings.yaml (fail if missing)
        2. Load secrets.local.yaml (fail if missing)
        3. Validate all required fields
    """
    if repo_root is None:
        repo_root = get_repo_root()

    config_dir = repo_root / "config"

    # Load settings
    settings_path = config_dir / "settings.yaml"
    if not settings_path.exists():
        return ConfigError(
            error_type=ConfigErrorType.FILE_NOT_FOUND,
            message="Configuration file not found",
            path=str(settings_path),
        )

    try:
        with open(settings_path) as f:
            settings_data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        return ConfigError(
            error_type=ConfigErrorType.PARSE_ERROR,
            message=str(e),
            path=str(settings_path),
        )

    # Validate settings
    try:
        settings = Settings.model_validate(settings_data)
    except Exception as e:
        return ConfigError(
            error_type=ConfigErrorType.VALIDATION_ERROR,
            message=f"Settings validation failed: {e}",
        )

    # Load secrets
    secrets_path = config_dir / "secrets.local.yaml"
    if not secrets_path.exists():
        return ConfigError(
            error_type=ConfigErrorType.FILE_NOT_FOUND,
            message="Secrets file not found. Copy templates/secrets.local.yaml to config/",
            path=str(secrets_path),
        )

    try:
        with open(secrets_path) as f:
            secrets_data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        return ConfigError(
            error_type=ConfigErrorType.PARSE_ERROR,
            message=str(e),
            path=str(secrets_path),
        )

    try:
        secrets = Secrets.model_validate(secrets_data)
    except Exception as e:
        return ConfigError(
            error_type=ConfigErrorType.VALIDATION_ERROR,
            message=f"Secrets validation failed: {e}",
        )

    return Config(settings=settings, secrets=secrets, loaded_at=datetime.now())
