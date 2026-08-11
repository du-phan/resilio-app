"""Persistence for athlete-confirmed run synchronization preferences."""

from resilio.core.repository import RepositoryIO
from resilio.schemas.publication import RunWorkoutSynchronizationPreferences
from resilio.schemas.repository import RepoError

RUN_SYNCHRONIZATION_PREFERENCES_PATH = "data/state/run_workout_synchronization_preferences.json"


def load_run_synchronization_preferences(
    repo: RepositoryIO,
) -> RunWorkoutSynchronizationPreferences:
    result = repo.read_json(
        RUN_SYNCHRONIZATION_PREFERENCES_PATH,
        RunWorkoutSynchronizationPreferences,
    )
    if result is None:
        return RunWorkoutSynchronizationPreferences()
    if isinstance(result, RepoError):
        raise ValueError(f"Invalid run synchronization preferences: {result}")
    return result


def save_run_synchronization_preferences(
    repo: RepositoryIO,
    preferences: RunWorkoutSynchronizationPreferences,
) -> None:
    validated = RunWorkoutSynchronizationPreferences.model_validate(
        preferences.model_dump(mode="python")
    )
    error = repo.write_json(RUN_SYNCHRONIZATION_PREFERENCES_PATH, validated)
    if error is not None:
        raise OSError(f"Failed to save run synchronization preferences: {error}")
