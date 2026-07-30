"""
Centralized path management for data directories.

This module provides functions to access configured data directory paths.
All modules should use these functions instead of hardcoded path strings.

Design:
- Reads path configuration from config/settings.yaml
- Caches configuration to avoid repeated file reads
- Provides type-safe path builders for common patterns
- Falls back to defaults if config load fails
"""

from pathlib import Path

from resilio.core.config import ConfigError, load_settings
from resilio.core.repository import RepositoryIO
from resilio.schemas.config import PathSettings

# Cache config to avoid repeated file reads
_config_cache: PathSettings | None = None
_config_cache_root: Path | None = None


def _get_paths() -> PathSettings:
    """Get path settings from config (cached)."""
    global _config_cache, _config_cache_root
    repo = RepositoryIO()
    if _config_cache is None or _config_cache_root != repo.repo_root:
        config_result = load_settings(repo.repo_root)
        if isinstance(config_result, ConfigError):
            _config_cache = PathSettings()
        else:
            _config_cache = config_result.paths
        _config_cache_root = repo.repo_root
    assert _config_cache is not None
    return _config_cache


# ==========================================================================
# BASE DIRECTORY ACCESSORS
# ==========================================================================


def get_athlete_dir() -> str:
    """Get athlete data directory path."""
    return _get_paths().athlete_dir


def get_activities_dir() -> str:
    """Get activities data directory path."""
    return _get_paths().activities_dir


# ==========================================================================
# ATHLETE PATHS
# ==========================================================================


def athlete_profile_path() -> str:
    """Get path to athlete profile.

    Returns:
        Path to profile.yaml (e.g., "data/athlete/profile.yaml")
    """
    return f"{get_athlete_dir()}/profile.yaml"


def athlete_memories_path() -> str:
    """Get path to memories file.

    Returns:
        Path to memories.yaml
    """
    return f"{get_athlete_dir()}/memories.yaml"


# ==========================================================================
# ACTIVITIES PATHS
# ==========================================================================


def activities_month_dir(year_month: str) -> str:
    """Get activities directory for a specific month.

    Args:
        year_month: Month in YYYY-MM format

    Returns:
        Path to month directory (e.g., "data/activities/2026-01")
    """
    return f"{get_activities_dir()}/{year_month}"


def activity_path(year_month: str, filename: str) -> str:
    """Get path to a specific activity file.

    Args:
        year_month: Month in YYYY-MM format
        filename: Activity filename

    Returns:
        Full path to activity file
    """
    return f"{get_activities_dir()}/{year_month}/{filename}"
