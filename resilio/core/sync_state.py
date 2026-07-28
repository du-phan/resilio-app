"""Strict activity sync-state persistence."""

from resilio.core.repository import RepositoryIO
from resilio.schemas.repository import RepoError
from resilio.schemas.sync import ActivitySyncState, SyncProgress


SYNC_STATE_PATH = "data/state/activity_sync.json"
SYNC_PROGRESS_PATH = "data/state/activity_sync_progress.json"


def read_sync_state(repo: RepositoryIO) -> ActivitySyncState:
    result = repo.read_json(SYNC_STATE_PATH, ActivitySyncState)
    if result is None:
        return ActivitySyncState()
    if isinstance(result, RepoError):
        raise ValueError(f"Invalid activity sync state: {result}")
    return result


def write_sync_state(repo: RepositoryIO, state: ActivitySyncState) -> None:
    error = repo.write_json(SYNC_STATE_PATH, state)
    if error is not None:
        raise OSError(f"Failed to persist activity sync state: {error}")


def read_sync_progress(repo: RepositoryIO) -> SyncProgress | None:
    result = repo.read_json(SYNC_PROGRESS_PATH, SyncProgress)
    if result is None:
        return None
    if isinstance(result, RepoError):
        raise ValueError(f"Invalid activity sync progress: {result}")
    return result


def write_sync_progress(repo: RepositoryIO, progress: SyncProgress) -> None:
    error = repo.write_json(SYNC_PROGRESS_PATH, progress)
    if error is not None:
        raise OSError(f"Failed to persist activity sync progress: {error}")


def clear_sync_progress(repo: RepositoryIO) -> None:
    if repo.file_exists(SYNC_PROGRESS_PATH):
        repo.delete_file(SYNC_PROGRESS_PATH)
