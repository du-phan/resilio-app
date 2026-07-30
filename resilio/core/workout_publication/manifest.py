"""Publication-manifest repository."""

from resilio.core.repository import RepositoryIO
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.repository import RepoError

PUBLICATION_MANIFEST_PATH = "data/state/workout_publications.json"


def load_manifest(repo: RepositoryIO) -> PublicationManifest:
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
