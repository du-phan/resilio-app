"""Persistence for exact provider- or athlete-proven workout fulfillment."""

import json

from resilio.core.repository import RepositoryIO
from resilio.schemas.repository import RepoError
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest

WORKOUT_FULFILLMENTS_PATH = "data/state/workout_fulfillments.json"
LEGACY_WORKOUT_COMPLETIONS_PATH = "data/state/workout_completions.json"
WORKOUT_PUBLICATIONS_PATH = "data/state/workout_publications.json"


class WorkoutFulfillmentCutoverRequiredError(ValueError):
    """Normal fulfillment access is blocked until the one-shot cutover succeeds."""


def _legacy_publication_manifest_exists(repo: RepositoryIO) -> bool:
    path = repo.resolve_path(WORKOUT_PUBLICATIONS_PATH)
    if not path.exists():
        return False
    if not path.is_file() or path.is_symlink():
        raise ValueError("Workout publication state must be a regular JSON file")
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("Workout publication state is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Workout publication state must be a JSON object")
    return payload.get("schema_version") == 6


def load_fulfillment_manifest(repo: RepositoryIO) -> WorkoutFulfillmentManifest:
    if repo.file_exists(LEGACY_WORKOUT_COMPLETIONS_PATH) or (
        _legacy_publication_manifest_exists(repo)
    ):
        raise WorkoutFulfillmentCutoverRequiredError(
            "Legacy workout completion state requires `resilio migrate "
            "workout-fulfillment-v1 --apply` before fulfillment access"
        )
    result = repo.read_json(WORKOUT_FULFILLMENTS_PATH, WorkoutFulfillmentManifest)
    if result is None:
        return WorkoutFulfillmentManifest()
    if isinstance(result, RepoError):
        raise ValueError(f"Invalid workout fulfillment manifest: {result}")
    return result


def save_fulfillment_manifest(
    repo: RepositoryIO,
    manifest: WorkoutFulfillmentManifest,
) -> None:
    validated = WorkoutFulfillmentManifest.model_validate(manifest.model_dump(mode="python"))
    error = repo.write_json(WORKOUT_FULFILLMENTS_PATH, validated)
    if error is not None:
        raise OSError(f"Failed to save workout fulfillment manifest: {error}")
