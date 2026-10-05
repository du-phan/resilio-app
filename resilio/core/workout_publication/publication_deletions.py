"""Permanent reaping of late events from ambiguous publication creates."""

from __future__ import annotations

from datetime import date, datetime, timezone

from resilio.canonical import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.state_migration_guard import (
    assert_state_migration_is_complete,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    provider_event_state_fingerprint,
    provider_local_date,
)
from resilio.core.workout_publication.publication_deletion_evidence import (
    assert_remote_matches_deletion_operation,
    assert_remote_matches_deletion_pending,
    pending_deletion_snapshot_matches,
    published_deletion_snapshot_matches,
    remote_matches_exact_previous_publication,
)
from resilio.core.workout_publication.publication_deletion_recovery import (
    forget_deleted_previous_publication,
    recover_absent_preserved_previous_publication,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout
from resilio.schemas.publication_operations import (
    PendingPublicationDeletionOperation,
    PublicationDeletionManifest,
    PublicationDeletionOperationItem,
    PublicationDeletionOperationsReport,
)
from resilio.schemas.repository import RepoError

PUBLICATION_DELETION_MANIFEST_PATH = "data/state/workout_publication_deletions.json"


def load_publication_deletion_manifest(
    repo: RepositoryIO,
) -> PublicationDeletionManifest:
    assert_state_migration_is_complete(repo)
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
    validated = PublicationDeletionManifest.model_validate(manifest.model_dump(mode="python"))
    error = repo.write_json(PUBLICATION_DELETION_MANIFEST_PATH, validated)
    if error is not None:
        raise OSError(f"Failed to save publication deletion manifest: {error}")


def publication_deletion_operation_id(
    pending: PendingWorkoutPublication,
    previous: PublishedWorkout | None = None,
    *,
    pending_step_semantics_sha256: str | None = None,
    previous_step_semantics_sha256: str | None = None,
    preserve_previous_publication: bool = False,
) -> str:
    identity_payload: dict[str, object] = {
        "pending_publication": pending.model_dump(
            mode="json",
            exclude={"garmin_forwarding_eligible"},
        ),
        "previous_publication": (
            previous.model_dump(
                mode="json",
                exclude={"provider_step_semantics_sha256"},
            )
            if previous is not None
            else None
        ),
        "reason": "workout_removed",
    }
    if preserve_previous_publication:
        identity_payload["preserve_previous_publication"] = True
    if pending_step_semantics_sha256 is not None:
        identity_payload["pending_step_semantics_sha256"] = pending_step_semantics_sha256
    if previous_step_semantics_sha256 is not None:
        identity_payload["previous_step_semantics_sha256"] = previous_step_semantics_sha256
    digest = canonical_data_sha256(identity_payload)
    return f"publication_deletion_{digest[:16]}"


def stage_pending_publication_deletion(
    repo: RepositoryIO,
    pending: PendingWorkoutPublication,
    *,
    previous: PublishedWorkout | None = None,
    pending_step_semantics_sha256: str,
    previous_step_semantics_sha256: str | None = None,
    preserve_previous_publication: bool = False,
    requested_at_utc: datetime | None = None,
) -> PendingPublicationDeletionOperation:
    """Persist exact ownership before concluding that a remote event is absent."""
    operation = PendingPublicationDeletionOperation(
        operation_id=publication_deletion_operation_id(
            pending,
            previous,
            pending_step_semantics_sha256=pending_step_semantics_sha256,
            previous_step_semantics_sha256=previous_step_semantics_sha256,
            preserve_previous_publication=preserve_previous_publication,
        ),
        pending_publication=pending,
        previous_publication=previous,
        pending_step_semantics_sha256=pending_step_semantics_sha256,
        previous_step_semantics_sha256=previous_step_semantics_sha256,
        preserve_previous_publication=preserve_previous_publication,
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
    legacy_operation_can_be_enriched = (
        existing is not None
        and pending_deletion_snapshot_matches(existing.pending_publication, pending)
        and existing.pending_step_semantics_sha256 is None
        and existing.preserve_previous_publication == preserve_previous_publication
        and (
            previous is None
            or (
                existing.previous_publication is not None
                and published_deletion_snapshot_matches(
                    existing.previous_publication,
                    previous,
                )
            )
        )
    )
    if legacy_operation_can_be_enriched:
        assert existing is not None
        enriched = operation.model_copy(
            update={
                "state": existing.state,
                "requested_at_utc": existing.requested_at_utc,
                "monitoring_started_at_utc": existing.monitoring_started_at_utc,
            }
        )
        validated = PendingPublicationDeletionOperation.model_validate(
            enriched.model_dump(mode="python")
        )
        del manifest.operations[existing.operation_id]
        manifest.operations[validated.operation_id] = validated
        manifest.drift_resolutions = [
            resolution
            for resolution in manifest.drift_resolutions
            if resolution.operation_id != existing.operation_id
        ]
        save_publication_deletion_manifest(repo, manifest)
        return validated
    if existing is not None and (
        not pending_deletion_snapshot_matches(existing.pending_publication, pending)
        or existing.pending_step_semantics_sha256 != pending_step_semantics_sha256
        or (
            previous is not None
            and existing.previous_step_semantics_sha256 != previous_step_semantics_sha256
        )
        or existing.preserve_previous_publication != preserve_previous_publication
        or (
            previous is not None
            and (
                existing.previous_publication is None
                or not published_deletion_snapshot_matches(
                    existing.previous_publication,
                    previous,
                )
            )
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
        active_publication = publication_manifest.workouts.get(local_workout_id)
        publication_is_safely_retained = active_publication is None or (
            operation.preserve_previous_publication
            and operation.previous_publication is not None
            and published_deletion_snapshot_matches(
                active_publication,
                operation.previous_publication,
            )
        )
        if (
            operation.state == "monitoring"
            and publication_is_safely_retained
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
                "monitoring_started_at_utc": (monitored_at_utc or datetime.now(timezone.utc)),
            }
        )
        validated = PendingPublicationDeletionOperation.model_validate(
            activated.model_dump(mode="python")
        )
        manifest.operations[validated.operation_id] = validated
        save_publication_deletion_manifest(repo, manifest)
    publication_manifest = load_manifest(repo)
    local_workout_id = validated.pending_publication.workout_identity.local_workout_id
    if (
        validated.previous_publication is not None
        and not validated.preserve_previous_publication
        and publication_manifest.workouts.get(local_workout_id) is not None
        and validated.previous_publication is not None
        and published_deletion_snapshot_matches(
            publication_manifest.workouts[local_workout_id],
            validated.previous_publication,
        )
    ):
        del publication_manifest.workouts[local_workout_id]
        del publication_manifest.workout_provider_occurrence_placements[local_workout_id]
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
            "observed_remote_fingerprint_sha256": (provider_event_state_fingerprint(remote)),
        }
    )


def _reconcile_operation(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    operation: PendingPublicationDeletionOperation,
    provider_events: list[EventDTO],
) -> PublicationDeletionOperationItem:
    pending = operation.pending_publication
    local_workout_id = pending.workout_identity.local_workout_id
    matches = matching_tombstone_events(provider_events, operation)
    if operation.preserve_previous_publication:
        matches = [
            remote
            for remote in matches
            if not remote_matches_exact_previous_publication(remote, operation)
        ]
    if len(matches) > 1:
        raise PublicationSafetyError("Multiple remote events claim a publication deletion identity")
    athlete = client.get_athlete()
    if not matches:
        preserved_provider_occurrence_date = recover_absent_preserved_previous_publication(
            repo,
            client,
            operation,
            athlete_id=athlete.id,
        )
        return PublicationDeletionOperationItem(
            operation_id=operation.operation_id,
            local_workout_id=local_workout_id,
            occurrence_date=pending.occurrence_date,
            provider_occurrence_date=(
                preserved_provider_occurrence_date
                or provider_local_date(pending.provider_start_date_local)
            ),
            status="deletion_monitoring",
        )
    listed_remote = matches[0]
    try:
        remote = get_exact_event(client, listed_remote.id, athlete_id=athlete.id)
    except IntervalsNotFoundError:
        preserved_provider_occurrence_date = recover_absent_preserved_previous_publication(
            repo,
            client,
            operation,
            athlete_id=athlete.id,
        )
        return PublicationDeletionOperationItem(
            operation_id=operation.operation_id,
            local_workout_id=local_workout_id,
            occurrence_date=pending.occurrence_date,
            provider_occurrence_date=(
                preserved_provider_occurrence_date
                or provider_local_date(pending.provider_start_date_local)
            ),
            status="deletion_monitoring",
        )
    if provider_event_state_fingerprint(remote) != provider_event_state_fingerprint(listed_remote):
        raise RemoteWorkoutDriftError("Late remote event changed immediately before deletion")
    if remote.start_date_local is None:
        raise RemoteWorkoutDriftError("Late remote event lacks a provider occurrence timestamp")
    remote_provider_occurrence_date = provider_local_date(remote.start_date_local)
    if operation.preserve_previous_publication:
        if remote_matches_exact_previous_publication(remote, operation):
            return PublicationDeletionOperationItem(
                operation_id=operation.operation_id,
                local_workout_id=local_workout_id,
                occurrence_date=pending.occurrence_date,
                provider_occurrence_date=remote_provider_occurrence_date,
                status="deletion_monitoring",
            )
        assert_remote_matches_deletion_pending(
            remote,
            pending,
            operation.pending_step_semantics_sha256,
        )
    else:
        assert_remote_matches_deletion_operation(remote, operation)
    client.delete_event(remote.id, athlete_id=athlete.id)
    try:
        get_exact_event(client, remote.id, athlete_id=athlete.id)
    except IntervalsNotFoundError:
        pass
    else:
        raise PublicationSafetyError("Deleted late event still exists on read-back")
    forget_deleted_previous_publication(repo, operation, remote.id)
    return PublicationDeletionOperationItem(
        operation_id=operation.operation_id,
        local_workout_id=local_workout_id,
        occurrence_date=pending.occurrence_date,
        provider_occurrence_date=remote_provider_occurrence_date,
        status="deleted",
        event_id=remote.id,
    )


def reconcile_publication_deletion_operation(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    operation: PendingPublicationDeletionOperation,
) -> PublicationDeletionOperationItem:
    """Reconcile one exact durable tombstone without changing its obligation."""
    assert_publication_deletion_integrity(repo)
    athlete = client.get_athlete()
    provider_events = client.list_events(date.min, date.max, athlete_id=athlete.id)
    item = _reconcile_operation(repo, client, operation, provider_events)
    activate_publication_deletion_monitoring(repo, operation)
    return item


def fresh_tombstone_error_target(
    client: IntervalsIcuClient,
    operation: PendingPublicationDeletionOperation,
    provider_events: list[EventDTO],
) -> EventDTO | None:
    matches = matching_tombstone_events(provider_events, operation)
    if len(matches) != 1:
        return None
    try:
        remote = get_exact_event(
            client,
            matches[0].id,
            athlete_id=client.get_athlete().id,
        )
    except IntervalsNotFoundError:
        return None
    return remote if matching_tombstone_events([remote], operation) else None


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
            item = _reconcile_operation(repo, client, operation, provider_events)
            activate_publication_deletion_monitoring(repo, operation)
            items.append(item)
        except RemoteWorkoutDriftError as exc:
            remote = fresh_tombstone_error_target(
                client,
                operation,
                provider_events,
            )
            items.append(
                PublicationDeletionOperationItem(
                    operation_id=operation.operation_id,
                    local_workout_id=(
                        operation.pending_publication.workout_identity.local_workout_id
                    ),
                    occurrence_date=operation.pending_publication.occurrence_date,
                    provider_occurrence_date=(
                        provider_local_date(remote.start_date_local)
                        if remote is not None and remote.start_date_local is not None
                        else provider_local_date(
                            operation.pending_publication.provider_start_date_local
                        )
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
            pending_step_semantics_sha256=(operation.pending_step_semantics_sha256),
            previous_step_semantics_sha256=(operation.previous_step_semantics_sha256),
            preserve_previous_publication=(operation.preserve_previous_publication),
        ):
            raise PublicationSafetyError(
                "Publication deletion tombstone ID does not match its exact intent"
            )
        current_pending = pending_by_local_id.get(local_workout_id)
        if current_pending is None or not pending_deletion_snapshot_matches(
            current_pending,
            pending,
        ):
            raise PublicationSafetyError(
                "Publication deletion tombstone lacks its exact retained pending intent"
            )
        current_publication = load_manifest(repo).workouts.get(local_workout_id)
        if current_publication is not None and (
            operation.previous_publication is None
            or not published_deletion_snapshot_matches(
                current_publication,
                operation.previous_publication,
            )
        ):
            raise PublicationSafetyError(
                "Publication deletion tombstone conflicts with active publication ownership"
            )
