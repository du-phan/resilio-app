"""Secret-safe runtime configuration loading."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Union

import yaml
from dotenv import dotenv_values
from pydantic import SecretStr

from resilio.schemas.config import Config, ConfigErrorType, Settings


class ConfigError:
    """Typed, redacted configuration error."""

    def __init__(
        self,
        error_type: ConfigErrorType,
        message: str,
        path: Optional[str] = None,
    ):
        self.error_type = error_type
        self.message = message
        self.path = path

    def __repr__(self) -> str:
        return (
            f"ConfigError(error_type={self.error_type!r}, "
            f"message={self.message!r}, path={self.path!r})"
        )


ConfigResult = Union[Config, ConfigError]
SettingsResult = Union[Settings, ConfigError]


def get_repo_root() -> Path:
    """Find the repository root without consulting credentials."""
    current = Path.cwd()
    while True:
        if (current / ".git").exists() or (current / "AGENTS.md").exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError("Could not find repository root (.git or AGENTS.md not found)")
        current = parent


def load_settings(repo_root: Optional[Path] = None) -> SettingsResult:
    """Load non-secret settings only."""
    root = repo_root or get_repo_root()
    settings_path = root / "config" / "settings.yaml"
    if not settings_path.exists():
        return ConfigError(
            ConfigErrorType.FILE_NOT_FOUND,
            "Configuration file not found",
            str(settings_path),
        )
    try:
        raw = yaml.safe_load(settings_path.read_text()) or {}
    except yaml.YAMLError as exc:
        return ConfigError(
            ConfigErrorType.PARSE_ERROR,
            f"Settings YAML is invalid: {exc}",
            str(settings_path),
        )
    try:
        return Settings.model_validate(raw)
    except Exception as exc:
        return ConfigError(
            ConfigErrorType.VALIDATION_ERROR,
            f"Settings validation failed: {exc}",
            str(settings_path),
        )


def load_config(
    repo_root: Optional[Path] = None,
    environment: Optional[Mapping[str, str]] = None,
) -> ConfigResult:
    """Load settings and the personal API key without mutating global environment.

    Tests and callers that already own an environment mapping must pass it
    explicitly. Only an omitted mapping causes `.env.local` to be parsed.
    """
    root = repo_root or get_repo_root()
    settings = load_settings(root)
    if isinstance(settings, ConfigError):
        return settings

    if environment is None:
        env_path = root / ".env.local"
        if not env_path.exists():
            return ConfigError(
                ConfigErrorType.MISSING_SECRET,
                "INTERVALS_ICU_API_KEY is not configured in .env.local",
                str(env_path),
            )
        loaded = dotenv_values(env_path)
        local_environment = {
            str(key): str(value) for key, value in loaded.items() if value is not None
        }
    else:
        local_environment = dict(environment)

    key = local_environment.get("INTERVALS_ICU_API_KEY", "").strip()
    if not key:
        return ConfigError(
            ConfigErrorType.MISSING_SECRET,
            "INTERVALS_ICU_API_KEY is missing or empty",
        )

    return Config(
        settings=settings,
        intervals_icu_api_key=SecretStr(key),
        loaded_at=datetime.now(timezone.utc),
    )
