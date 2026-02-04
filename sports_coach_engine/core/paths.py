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

from datetime import date
from typing import Optional

from sports_coach_engine.core.config import load_config
from sports_coach_engine.core.repository import RepositoryIO

# Cache config to avoid repeated file reads
_config_cache: Optional[object] = None
_config_cache_root: Optional[object] = None


def _get_paths():
    """Get path settings from config (cached)."""
    global _config_cache, _config_cache_root
    repo = RepositoryIO()
    if _config_cache is None or _config_cache_root != repo.repo_root:
        config_result = load_config(repo.repo_root)
        if hasattr(config_result, "error_type"):
            # Config load failed, use defaults
            from sports_coach_engine.schemas.config import PathSettings

            _config_cache = PathSettings()
        else:
            _config_cache = config_result.settings.paths
        _config_cache_root = repo.repo_root
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


def get_metrics_dir() -> str:
    """Get metrics data directory path."""
    return _get_paths().metrics_dir


def get_plans_dir() -> str:
    """Get plans data directory path."""
    return _get_paths().plans_dir


def get_state_dir() -> str:
    """Get state data directory path."""
    return _get_paths().state_dir


# ==========================================================================
# ATHLETE PATHS
# ==========================================================================


def athlete_profile_path() -> str:
    """Get path to athlete profile.

    Returns:
        Path to profile.yaml (e.g., "data/athlete/profile.yaml")
    """
    return f"{get_athlete_dir()}/profile.yaml"


def athlete_training_history_path() -> str:
    """Get path to training history.

    Returns:
        Path to training_history.yaml
    """
    return f"{get_athlete_dir()}/training_history.yaml"


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


# ==========================================================================
# METRICS PATHS
# ==========================================================================


def daily_metrics_path(target_date: date) -> str:
    """Get path to daily metrics for a date.

    Args:
        target_date: Date object

    Returns:
        Path to daily metrics file (e.g., "data/metrics/daily/2026-01-14.yaml")
    """
    return f"{get_metrics_dir()}/daily/{target_date.isoformat()}.yaml"


def weekly_metrics_summary_path() -> str:
    """Get path to weekly metrics summary.

    Returns:
        Path to weekly_summary.yaml
    """
    return f"{get_metrics_dir()}/weekly_summary.yaml"


# ==========================================================================
# PLANS PATHS
# ==========================================================================


def current_plan_path() -> str:
    """Get path to current training plan.

    Returns:
        Path to current_plan.yaml
    """
    return f"{get_plans_dir()}/current_plan.yaml"


def plan_archive_dir() -> str:
    """Get path to plan archive directory.

    Returns:
        Path to archive directory
    """
    return f"{get_plans_dir()}/archive"


def plan_workouts_dir(week_number: int) -> str:
    """Get path to workouts directory for a specific week.

    Args:
        week_number: Week number (1-based)

    Returns:
        Path to week's workout directory (e.g., "data/plans/workouts/week_01")
    """
    return f"{get_plans_dir()}/workouts/week_{week_number:02d}"


def approvals_state_path() -> str:
    """Get path to approvals state JSON."""
    return f"{get_state_dir()}/approvals.json"


def current_plan_review_path() -> str:
    """Get path to current plan review markdown.

    Returns:
        Path to current_plan_review.md (e.g., "data/plans/current_plan_review.md")
    """
    return f"{get_plans_dir()}/current_plan_review.md"


def current_training_log_path() -> str:
    """Get path to current training log markdown.

    Returns:
        Path to current_training_log.md (e.g., "data/plans/current_training_log.md")
    """
    return f"{get_plans_dir()}/current_training_log.md"
