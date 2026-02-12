"""
Sync state I/O helpers.
"""

import logging
from datetime import date, datetime

import yaml

from sports_coach_engine.core.paths import athlete_training_history_path
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.sync import SyncResumeState


logger = logging.getLogger(__name__)


def read_training_history(repo: RepositoryIO) -> dict:
    """Safely load training_history.yaml as a raw dict."""
    path = athlete_training_history_path()
    resolved = repo.resolve_path(path)
    if not resolved.exists():
        return {}

    try:
        with open(resolved) as handle:
            data = yaml.safe_load(handle)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}
    return data


def write_training_history(repo: RepositoryIO, history: dict) -> None:
    """Persist training_history.yaml dictionary."""
    repo.write_yaml(athlete_training_history_path(), history)


def _coerce_bool(value: object) -> bool:
    """Coerce bool-ish values into bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
        return bool(value)
    raise ValueError("invalid boolean value")


def _coerce_date(value: object) -> date:
    """Coerce date-ish values into date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value.strip())
    raise ValueError("invalid date value")


def _coerce_int(value: object) -> int:
    """Coerce int-ish values into int."""
    if isinstance(value, bool):
        raise ValueError("bool is not accepted as integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        return int(value.strip())
    raise ValueError("invalid integer value")


def _coerce_datetime(value: object) -> datetime:
    """Coerce datetime-ish values into datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized)
    raise ValueError("invalid datetime value")


def resume_state_from_history(history: dict) -> SyncResumeState:
    """Build SyncResumeState from raw history dict, tolerating malformed values."""
    state = SyncResumeState()
    if not isinstance(history, dict):
        logger.warning("[SyncState] training_history is not a dict; using defaults")
        return state

    if "backfill_in_progress" in history:
        try:
            state.backfill_in_progress = _coerce_bool(history["backfill_in_progress"])
        except Exception:
            logger.warning(
                "[SyncState] Ignoring invalid backfill_in_progress value: %r",
                history.get("backfill_in_progress"),
            )
    if "target_start_date" in history and history.get("target_start_date") is not None:
        try:
            state.target_start_date = _coerce_date(history["target_start_date"])
        except Exception:
            logger.warning(
                "[SyncState] Ignoring invalid target_start_date value: %r",
                history.get("target_start_date"),
            )
    if "resume_before_timestamp" in history and history.get("resume_before_timestamp") is not None:
        try:
            state.resume_before_timestamp = _coerce_int(history["resume_before_timestamp"])
        except Exception:
            logger.warning(
                "[SyncState] Ignoring invalid resume_before_timestamp value: %r",
                history.get("resume_before_timestamp"),
            )
    if "last_progress_at" in history and history.get("last_progress_at") is not None:
        try:
            state.last_progress_at = _coerce_datetime(history["last_progress_at"])
        except Exception:
            logger.warning(
                "[SyncState] Ignoring invalid last_progress_at value: %r",
                history.get("last_progress_at"),
            )

    return state


def read_resume_state(repo: RepositoryIO) -> SyncResumeState:
    """Read and normalize persisted resume state from training history."""
    history = read_training_history(repo)
    return resume_state_from_history(history)
