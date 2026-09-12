"""Retirement routing for workouts already protected by durable tombstones."""

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.publication_deletions import (
    load_publication_deletion_manifest,
    reconcile_publication_deletion_operation,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.schemas.publication import PublicationAction, PublicationResult


def retire_existing_tombstone(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    local_workout_id: str,
) -> PublicationResult | None:
    """Route late materialization through its existing permanent obligation."""
    operation = next(
        (
            candidate
            for candidate in load_publication_deletion_manifest(repo).operations.values()
            if candidate.pending_publication.workout_identity.local_workout_id == local_workout_id
        ),
        None,
    )
    if operation is None:
        return None
    item = reconcile_publication_deletion_operation(repo, client, operation)
    if item.status == "deleted":
        action: PublicationAction = "deleted"
    elif item.status == "deletion_monitoring":
        action = "deletion_monitoring"
    else:
        raise PublicationSafetyError("Publication deletion obligation returned an invalid action")
    pending = operation.pending_publication
    return PublicationResult(
        action=action,
        local_workout_id=local_workout_id,
        event_id=item.event_id,
        uid=pending.uid,
        external_id=pending.external_id,
        provider_occurrence_date=item.provider_occurrence_date,
    )
