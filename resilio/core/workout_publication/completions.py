"""Provider-neutral completed-activity to planned-workout matches."""

from resilio.core.repository import RepositoryIO
from resilio.schemas.publication import WorkoutCompletionManifest
from resilio.schemas.repository import RepoError

WORKOUT_COMPLETIONS_PATH = "data/state/workout_completions.json"


def load_completion_manifest(
    repo: RepositoryIO,
) -> WorkoutCompletionManifest:
    result = repo.read_json(
        WORKOUT_COMPLETIONS_PATH,
        WorkoutCompletionManifest,
    )
    if result is None:
        return WorkoutCompletionManifest()
    if isinstance(result, RepoError):
        raise ValueError(f"Invalid workout completion manifest: {result}")
    return result


def save_completion_manifest(
    repo: RepositoryIO,
    manifest: WorkoutCompletionManifest,
) -> None:
    validated = WorkoutCompletionManifest.model_validate(
        manifest.model_dump(mode="python")
    )
    error = repo.write_json(WORKOUT_COMPLETIONS_PATH, validated)
    if error is not None:
        raise OSError(f"Failed to save workout completion manifest: {error}")
