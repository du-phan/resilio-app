"""Publication-manifest repository."""

import json

from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.cutover_guard import (
    assert_fulfillment_cutover_is_complete,
)
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.repository import RepoError

PUBLICATION_MANIFEST_PATH = "data/state/workout_publications.json"


def load_manifest(repo: RepositoryIO) -> PublicationManifest:
    assert_fulfillment_cutover_is_complete(repo)
    path = repo.resolve_path(PUBLICATION_MANIFEST_PATH)
    if path.exists():
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise ValueError("Workout publication state is not valid JSON") from exc
        if isinstance(raw, dict) and raw.get("schema_version") in {6, 7}:
            raise ValueError(
                "Workout publication state requires `resilio migrate "
                "workout-fulfillment-v2 --apply` before publication access"
            )
    result = repo.read_json(PUBLICATION_MANIFEST_PATH, PublicationManifest)
    if result is None:
        return PublicationManifest()
    if isinstance(result, RepoError):
        raise ValueError(f"Invalid publication manifest: {result}")
    return result


def save_manifest(repo: RepositoryIO, manifest: PublicationManifest) -> None:
    validated = PublicationManifest.model_validate(manifest.model_dump(mode="python"))
    error = repo.write_json(PUBLICATION_MANIFEST_PATH, validated)
    if error is not None:
        raise OSError(f"Failed to save publication manifest: {error}")
