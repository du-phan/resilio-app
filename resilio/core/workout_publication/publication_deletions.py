"""Permanent reaping of late events from ambiguous publication creates."""

from __future__ import annotations

from datetime import date, datetime, timezone

from resilio.canonical import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.cutover_guard import (
    assert_fulfillment_cutover_is_complete,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    assert_remote_ownership,
    provider_event_fingerprint,
    provider_local_date,
    publication_fingerprint,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO, EventWriteDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout
from resilio.schemas.publication_operations import (
    PendingPublicationDeletionOperation,
    PublicationDeletionManifest,
    PublicationDeletionOperationItem,
    PublicationDeletionOperationsReport,
)
from resilio.schemas.repository import RepoError

PUBLICATION_DELETION_MANIFEST_PATH = (
    "data/state/workout_publication_deletions.json"
)


def load_publication_deletion_manifest(
    repo: RepositoryIO,
) -> PublicationDeletionManifest:
    assert_fulfillment_cutover_is_complete(repo)
    result = repo.read_json(
        PUBLICATION_DELETION_MANIFEST_PATH,
        PublicationDeletionManifest,
    )
    if result is None:
        return PublicationDeletionManifest()
    if isinstance(result, RepoError):
        raise ValueError(f"Invalid publication deletion manifest: {result}")
    return result


def save_publication_deletion_manifest(
    repo: RepositoryIO,
    manifest: PublicationDeletionManifest,
) -> None:
    validated = PublicationDeletionManifest.model_validate(
        manifest.model_dump(mode="python")
    )
    error = repo.write_json(PUBLICATION_DELETION_MANIFEST_PATH, validated)
    if error is not None:
        raise OSError(f"Failed to save publication deletion manifest: {error}")


def publication_deletion_operation_id(
    pending: PendingWorkoutPublication,
    previous: PublishedWorkout | None = None,
) -> str:
    digest = canonical_data_sha256(
        {
            "pending_publication": pending.model_dump(mode="json"),
            "previous_publication": (
                previous.model_dump(mode="json") if previous is not None else None
            ),
            "reason": "workout_removed",
        }
    )
    return f"publication_deletion_{digest[:16]}"


def stage_pending_publication_deletion(
    repo: RepositoryIO,
    pending: PendingWorkoutPublication,
    *,
    previous: PublishedWorkout | None = None,
    requested_at_utc: datetime | None = None,
) -> PendingPublicationDeletionOperation:
    """Persist exact ownership before concluding that a remote event is absent."""
    operation = PendingPublicationDeletionOperation(
        operation_id=publication_deletion_operation_id(pending, previous),
        pending_publication=pending,
        previous_publication=previous,
        requested_at_utc=requested_at_utc or datetime.now(timezone.utc),
    )
    manifest = load_publication_deletion_manifest(repo)
    existing = next(
        (
            candidate
            for candidate in manifest.operations.values()
            if candidate.pending_publication.workout_identity.local_workout_id
            == pending.workout_identity.local_workout_id
        ),
        None,
    )
    if existing is not None and (
        existing.pending_publication != pending
        or (
            previous is not None
            and existing.previous_publication != previous
        )
    ):
        raise PublicationSafetyError(
            "Workout already has a different durable publication deletion obligation"
        )
    if existing is None:
        manifest.operations[operation.operation_id] = operation
        save_publication_deletion_manifest(repo, manifest)
    return existing or operation


def monitored_pending_workout_ids(repo: RepositoryIO) -> set[str]:
    """Return pending-only workouts protected by exact durable tombstones."""
    publication_manifest = load_manifest(repo)
    operation_manifest = load_publication_deletion_manifest(repo)
    monitored: set[str] = set()
    for operation in operation_manifest.operations.values():
        pending = operation.pending_publication
        local_workout_id = pending.workout_identity.local_workout_id
        if (
            operation.state == "monitoring"
            and
            local_workout_id not in publication_manifest.workouts
            and publication_manifest.pending.get(local_workout_id) == pending
        ):
            monitored.add(local_workout_id)
    return monitored


def publication_deletion_workout_ids(repo: RepositoryIO) -> set[str]:
    """Return every workout ID permanently reserved by a deletion tombstone."""
    return {
        operation.pending_publication.workout_identity.local_workout_id
        for operation in load_publication_deletion_manifest(repo).operations.values()
    }


def activate_publication_deletion_monitoring(
    repo: RepositoryIO,
    operation: PendingPublicationDeletionOperation,
    *,
    monitored_at_utc: datetime | None = None,
) -> PendingPublicationDeletionOperation:
    """Record that the exact provider identity was absent after deletion intent."""
    manifest = load_publication_deletion_manifest(repo)
    current = manifest.operations.get(operation.operation_id)
    if current != operation:
        raise PublicationSafetyError(
            "Publication deletion obligation changed before monitoring activation"
        )
    if current.state == "monitoring":
        validated = current
    else:
        activated = current.model_copy(
            update={
                "state": "monitoring",
                "monitoring_started_at_utc": (
                    monitored_at_utc or datetime.now(timezone.utc)
                ),
            }
        )
        validated = PendingPublicationDeletionOperation.model_validate(
            activated.model_dump(mode="python")
        )
        manifest.operations[validated.operation_id] = validated
        save_publication_deletion_manifest(repo, manifest)
    publication_manifest = load_manifest(repo)
    local_workout_id = (
        validated.pending_publication.workout_identity.local_workout_id
    )
    if (
        validated.previous_publication is not None
        and publication_manifest.workouts.get(local_workout_id)
        == validated.previous_publication
    ):
        del publication_manifest.workouts[local_workout_id]
        save_manifest(repo, publication_manifest)
    return validated


def matching_tombstone_events(
    events: list[EventDTO],
    operation: PendingPublicationDeletionOperation,
) -> list[EventDTO]:
    pending = operation.pending_publication
    return [
        event
        for event in events
        if event.uid == pending.uid or event.external_id == pending.external_id
    ]


def publication_deletion_drift_token(
    operation: PendingPublicationDeletionOperation,
    remote: EventDTO,
) -> str:
    return canonical_data_sha256(
        {
            "operation_id": operation.operation_id,
            "event_id": remote.id,
            "observed_remote_fingerprint_sha256": provider_event_fingerprint(remote),
        }
    )


def _assert_remote_matches_pending(
    remote: EventDTO,
    pending: PendingWorkoutPublication,
) -> None:
    assert_remote_external_ownership(remote, external_id=pending.external_id)
    owned_fields = (
        remote.category,
        remote.type,
        remote.name,
        remote.description,
        remote.start_date_local,
        remote.target,
    )
    if any(value is None for value in owned_fields):
        raise RemoteWorkoutDriftError(
            "Late remote event lacks the complete owned workout fields"
        )
    event = EventWriteDTO(
        uid=pending.uid,
        external_id=pending.external_id,
        category=remote.category,  # type: ignore[arg-type]
        type=remote.type,  # type: ignore[arg-type]
        name=remote.name,  # type: ignore[arg-type]
        description=remote.description,  # type: ignore[arg-type]
        start_date_local=remote.start_date_local,  # type: ignore[arg-type]
        target=remote.target,  # type: ignore[arg-type]
    )
    if (
        publication_fingerprint(
            event,
            pending.sport_settings_version_sha256,
        )
        != pending.publication_fingerprint_sha256
    ):
        raise RemoteWorkoutDriftError(
            "Late remote event differs from its exact durable publication intent"
        )


def _assert_remote_matches_operation(
    remote: EventDTO,
    operation: PendingPublicationDeletionOperation,
) -> None:
    previous = operation.previous_publication
    if previous is not None:
        try:
            assert_remote_ownership(
                remote,
                uid=previous.uid,
                external_id=previous.external_id,
            )
            if provider_event_fingerprint(remote) == (
                previous.provider_event_fingerprint_sha256
            ):
                return
        except PublicationSafetyError:
            pass
    _assert_remote_matches_pending(remote, operation.pending_publication)


def _reconcile_operation(
    client: IntervalsIcuClient,
    operation: PendingPublicationDeletionOperation,
    provider_events: list[EventDTO],
) -> PublicationDeletionOperationItem:
    pending = operation.pending_publication
    local_workout_id = pending.workout_identity.local_workout_id
    matches = matching_tombstone_events(provider_events, operation)
    if len(matches) > 1:
        raise PublicationSafetyError(
            "Multiple remote events claim a publication deletion identity"
        )
    if not matches:
        return PublicationDeletionOperationItem(
            operation_id=operation.operation_id,
            local_workout_id=local_workout_id,
            occurrence_date=pending.occurrence_date,
            provider_occurrence_date=provider_local_date(
                pending.provider_start_date_local
            ),
            status="deletion_monitoring",
        )
    remote = matches[0]
    _assert_remote_matches_operation(remote, operation)
    athlete = client.get_athlete()
    client.delete_event(remote.id, athlete_id=athlete.id)
    try:
        client.get_event(remote.id, athlete_id=athlete.id)
    except IntervalsNotFoundError:
        pass
    else:
        raise PublicationSafetyError("Deleted late event still exists on read-back")
    return PublicationDeletionOperationItem(
        operation_id=operation.operation_id,
        local_workout_id=local_workout_id,
        occurrence_date=pending.occurrence_date,
        provider_occurrence_date=provider_local_date(
            pending.provider_start_date_local
        ),
        status="deleted",
        event_id=remote.id,
    )


def reconcile_publication_deletion_operations(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
) -> PublicationDeletionOperationsReport:
    """Delete exact late materializations while retaining permanent tombstones."""
    assert_publication_deletion_integrity(repo)
    manifest = load_publication_deletion_manifest(repo)
    if not manifest.operations:
        return PublicationDeletionOperationsReport(
            reconciliation_safe=True,
            items=[],
        )
    athlete = client.get_athlete()
    provider_events = client.list_events(date.min, date.max, athlete_id=athlete.id)
    items: list[PublicationDeletionOperationItem] = []
    for operation in manifest.operations.values():
        try:
            item = _reconcile_operation(client, operation, provider_events)
            activate_publication_deletion_monitoring(repo, operation)
            items.append(item)
        except RemoteWorkoutDriftError as exc:
            matches = matching_tombstone_events(provider_events, operation)
            remote = matches[0] if len(matches) == 1 else None
            items.append(
                PublicationDeletionOperationItem(
                    operation_id=operation.operation_id,
                    local_workout_id=(
                        operation.pending_publication.workout_identity.local_workout_id
                    ),
                    occurrence_date=operation.pending_publication.occurrence_date,
                    provider_occurrence_date=provider_local_date(
                        operation.pending_publication.provider_start_date_local
                    ),
                    status="error",
                    event_id=remote.id if remote is not None else None,
                    error_type="remote_drift",
                    message=str(exc),
                    drift_resolution_token_sha256=(
                        publication_deletion_drift_token(operation, remote)
                        if remote is not None
                        else None
                    ),
                )
            )
        except Exception as exc:
            items.append(
                PublicationDeletionOperationItem(
                    operation_id=operation.operation_id,
                    local_workout_id=(
                        operation.pending_publication.workout_identity.local_workout_id
                    ),
                    occurrence_date=operation.pending_publication.occurrence_date,
                    provider_occurrence_date=provider_local_date(
                        operation.pending_publication.provider_start_date_local
                    ),
                    status="error",
                    error_type=(
                        "remote_drift"
                        if isinstance(exc, RemoteWorkoutDriftError)
                        else "publication_safety"
                        if isinstance(exc, PublicationSafetyError)
                        else "provider"
                    ),
                    message=str(exc),
                )
            )
    partial = any(item.status == "error" for item in items)
    return PublicationDeletionOperationsReport(
        reconciliation_safe=not partial,
        partial=partial,
        items=items,
    )


def assert_publication_deletion_integrity(repo: RepositoryIO) -> None:
    """Fail if durable operations lose the publication ownership they preserve."""
    pending_by_local_id = load_manifest(repo).pending
    for operation in load_publication_deletion_manifest(repo).operations.values():
        pending = operation.pending_publication
        local_workout_id = pending.workout_identity.local_workout_id
        if operation.operation_id != publication_deletion_operation_id(
            pending,
            operation.previous_publication,
        ):
            raise PublicationSafetyError(
                "Publication deletion tombstone ID does not match its exact intent"
            )
        if pending_by_local_id.get(local_workout_id) != pending:
            raise PublicationSafetyError(
                "Publication deletion tombstone lacks its exact retained pending intent"
            )
        current_publication = load_manifest(repo).workouts.get(local_workout_id)
        if (
            current_publication is not None
            and current_publication != operation.previous_publication
        ):
            raise PublicationSafetyError(
                "Publication deletion tombstone conflicts with active publication ownership"
            )
