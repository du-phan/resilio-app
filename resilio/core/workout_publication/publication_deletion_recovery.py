"""Crash recovery after deletion of an obsolete publication target."""

from datetime import date

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import (
    RemoteWorkoutDriftError,
    provider_local_date,
)
from resilio.core.workout_publication.publication_deletion_evidence import (
    published_deletion_snapshot_matches,
    remote_matches_exact_previous_publication,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.publication_operations import PendingPublicationDeletionOperation


def forget_deleted_previous_publication(
    repo: RepositoryIO,
    operation: PendingPublicationDeletionOperation,
    deleted_event_id: int,
) -> None:
    """Remove active ownership only for the exact preserved event just deleted."""
    previous = operation.previous_publication
    if (
        not operation.preserve_previous_publication
        or previous is None
        or previous.event_id != deleted_event_id
    ):
        return
    publication_manifest = load_manifest(repo)
    local_workout_id = previous.workout_identity.local_workout_id
    current = publication_manifest.workouts.get(local_workout_id)
    if current is not None and published_deletion_snapshot_matches(
        current,
        previous,
    ):
        del publication_manifest.workouts[local_workout_id]
        del publication_manifest.workout_provider_occurrence_placements[local_workout_id]
        save_manifest(repo, publication_manifest)


def recover_absent_preserved_previous_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    operation: PendingPublicationDeletionOperation,
    *,
    athlete_id: str,
) -> date | None:
    """Repair deleted ownership or return the exact preserved provider date."""
    previous = operation.previous_publication
    if not operation.preserve_previous_publication or previous is None:
        return None
    try:
        remote = get_exact_event(client, previous.event_id, athlete_id=athlete_id)
    except IntervalsNotFoundError:
        forget_deleted_previous_publication(repo, operation, previous.event_id)
        return None
    if not remote_matches_exact_previous_publication(remote, operation):
        raise RemoteWorkoutDriftError(
            "Preserved publication changed while recovering deletion state"
        )
    if remote.start_date_local is None:
        raise RemoteWorkoutDriftError("Preserved publication lacks a provider occurrence timestamp")
    return provider_local_date(remote.start_date_local)
