"""Durable removal intent and synchronization suppression for missed runs."""

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.state_migration_guard import assert_state_migration_is_complete
from resilio.core.workout_publication.authority_matching import (
    publication_record_matches_current_workout_authority,
)
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.schemas.calendar_removal import CalendarRemovalManifest
from resilio.schemas.repository import RepoError

CALENDAR_REMOVAL_PATH = "data/state/missed_workout_calendar_removals.json"


def load_removal_manifest(repo: RepositoryIO) -> CalendarRemovalManifest:
    assert_state_migration_is_complete(repo)
    result = repo.read_json(CALENDAR_REMOVAL_PATH, CalendarRemovalManifest)
    if isinstance(result, RepoError):
        raise PublicationSafetyError(f"Calendar removal state is invalid: {result}")
    return result or CalendarRemovalManifest()


def save_removal_manifest(repo: RepositoryIO, manifest: CalendarRemovalManifest) -> None:
    validated = CalendarRemovalManifest.model_validate(manifest.model_dump(mode="python"))
    error = repo.write_json(CALENDAR_REMOVAL_PATH, validated)
    if error is not None:
        raise OSError(f"Calendar removal intent could not be persisted: {error}")


def calendar_removal_is_complete(repo: RepositoryIO, workout: AuthoritativeWorkout) -> bool:
    """Prevent reconciliation from recreating a confirmed removed event."""
    removal = load_removal_manifest(repo).removals.get(workout.identity.local_workout_id)
    if removal is None:
        return False
    if not publication_record_matches_current_workout_authority(removal.publication, workout):
        raise PublicationSafetyError("Calendar removal differs from retained workout authority")
    if removal.completed_at_utc is None:
        raise PublicationSafetyError(
            "Calendar removal is pending; retry its explicit removal command"
        )
    return True
