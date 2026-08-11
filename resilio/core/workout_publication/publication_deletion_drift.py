"""Athlete-confirmed resolution of drifted publication tombstones."""

from __future__ import annotations

from datetime import date, datetime, timezone

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    provider_event_fingerprint,
    provider_local_date,
)
from resilio.core.workout_publication.publication_deletions import (
    activate_publication_deletion_monitoring,
    assert_publication_deletion_integrity,
    load_publication_deletion_manifest,
    matching_tombstone_events,
    publication_deletion_drift_token,
    save_publication_deletion_manifest,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.integrations.intervals_icu.errors import IntervalsIcuError, IntervalsNotFoundError
from resilio.schemas.publication_operations import (
    PendingPublicationDeletionOperation,
    PublicationDeletionDriftResolution,
    PublicationDeletionManifest,
    PublicationDeletionOperationItem,
    PublicationDeletionOperationsReport,
    PublicationDeletionStatus,
)


def _resolution_by_token(
    manifest: PublicationDeletionManifest,
    token: str,
) -> PublicationDeletionDriftResolution | None:
    return next(
        (
            resolution
            for resolution in manifest.drift_resolutions
            if resolution.drift_resolution_token_sha256 == token
        ),
        None,
    )


def _current_resolution_target(
    manifest: PublicationDeletionManifest,
    provider_events: list[EventDTO],
    token: str,
) -> tuple[PendingPublicationDeletionOperation, EventDTO]:
    matches: list[tuple[PendingPublicationDeletionOperation, EventDTO]] = []
    for operation in manifest.operations.values():
        for remote in matching_tombstone_events(provider_events, operation):
            if publication_deletion_drift_token(operation, remote) == token:
                matches.append((operation, remote))
    if len(matches) != 1:
        raise PublicationSafetyError(
            "Publication deletion drift token does not identify one current target"
        )
    return matches[0]


def _persist_drift_resolutions(
    repo: RepositoryIO,
    manifest: PublicationDeletionManifest,
    provider_events: list[EventDTO],
    *,
    confirmed_tokens: list[str],
    athlete_confirmation_reference: str,
    confirmed_at_utc: datetime,
) -> list[PublicationDeletionDriftResolution]:
    resolutions: list[PublicationDeletionDriftResolution] = []
    for token in confirmed_tokens:
        prior = _resolution_by_token(manifest, token)
        if prior is not None:
            resolutions.append(prior)
            continue
        operation, remote = _current_resolution_target(
            manifest,
            provider_events,
            token,
        )
        resolution = PublicationDeletionDriftResolution(
            operation_id=operation.operation_id,
            event_id=remote.id,
            observed_remote_fingerprint_sha256=provider_event_fingerprint(remote),
            drift_resolution_token_sha256=token,
            athlete_confirmation_reference=athlete_confirmation_reference,
            confirmed_at_utc=confirmed_at_utc,
        )
        manifest.drift_resolutions.append(resolution)
        resolutions.append(resolution)
    save_publication_deletion_manifest(repo, manifest)
    return resolutions


def _result_item(
    operation: PendingPublicationDeletionOperation,
    *,
    status: PublicationDeletionStatus,
    event_id: int | None = None,
    error_type: str | None = None,
    message: str | None = None,
    drift_resolution_token_sha256: str | None = None,
) -> PublicationDeletionOperationItem:
    pending = operation.pending_publication
    return PublicationDeletionOperationItem(
        operation_id=operation.operation_id,
        local_workout_id=pending.workout_identity.local_workout_id,
        occurrence_date=pending.occurrence_date,
        provider_occurrence_date=provider_local_date(
            pending.provider_start_date_local
        ),
        status=status,
        event_id=event_id,
        error_type=error_type,
        message=message,
        drift_resolution_token_sha256=drift_resolution_token_sha256,
    )


def _apply_drift_resolution(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    manifest: PublicationDeletionManifest,
    resolution: PublicationDeletionDriftResolution,
    provider_events: list[EventDTO],
) -> PublicationDeletionOperationItem:
    operation = manifest.operations[resolution.operation_id]
    athlete = client.get_athlete()
    current_matches = matching_tombstone_events(provider_events, operation)
    if len(current_matches) > 1:
        raise PublicationSafetyError(
            "Multiple remote events claim a publication deletion identity"
        )
    if current_matches and current_matches[0].id != resolution.event_id:
        raise RemoteWorkoutDriftError(
            "A new tombstone event requires a fresh exact drift confirmation"
        )
    if not current_matches:
        try:
            client.get_event(resolution.event_id, athlete_id=athlete.id)
        except IntervalsNotFoundError:
            activate_publication_deletion_monitoring(repo, operation)
            return _result_item(operation, status="deletion_monitoring")
        raise PublicationSafetyError(
            "Confirmed tombstone event is absent from provider-wide identity discovery"
        )
    try:
        remote = client.get_event(resolution.event_id, athlete_id=athlete.id)
    except IntervalsNotFoundError:
        activate_publication_deletion_monitoring(repo, operation)
        return _result_item(operation, status="deletion_monitoring")
    assert_remote_external_ownership(
        remote,
        external_id=operation.pending_publication.external_id,
    )
    if (
        provider_event_fingerprint(remote)
        != resolution.observed_remote_fingerprint_sha256
        or publication_deletion_drift_token(operation, remote)
        != resolution.drift_resolution_token_sha256
    ):
        raise RemoteWorkoutDriftError(
            "Drifted tombstone event changed after athlete confirmation"
        )
    client.delete_event(remote.id, athlete_id=athlete.id)
    try:
        client.get_event(remote.id, athlete_id=athlete.id)
    except IntervalsNotFoundError:
        pass
    else:
        raise PublicationSafetyError("Confirmed drifted event still exists on read-back")
    activate_publication_deletion_monitoring(repo, operation)
    return _result_item(operation, status="deleted", event_id=remote.id)


def resolve_publication_deletion_drifts(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    *,
    confirmed_drift_tokens: list[str],
    athlete_confirmation_reference: str,
    confirmed_at_utc: datetime | None = None,
) -> PublicationDeletionOperationsReport:
    """Persist exact athlete authority, then delete only those confirmed bytes."""
    if not confirmed_drift_tokens or len(confirmed_drift_tokens) != len(
        set(confirmed_drift_tokens)
    ):
        raise PublicationSafetyError(
            "Publication deletion drift resolution requires unique exact tokens"
        )
    if not athlete_confirmation_reference.strip():
        raise PublicationSafetyError(
            "Publication deletion drift resolution requires athlete confirmation"
        )
    assert_publication_deletion_integrity(repo)
    manifest = load_publication_deletion_manifest(repo)
    athlete = client.get_athlete()
    provider_events = client.list_events(date.min, date.max, athlete_id=athlete.id)
    resolutions = _persist_drift_resolutions(
        repo,
        manifest,
        provider_events,
        confirmed_tokens=confirmed_drift_tokens,
        athlete_confirmation_reference=athlete_confirmation_reference,
        confirmed_at_utc=confirmed_at_utc or datetime.now(timezone.utc),
    )
    items: list[PublicationDeletionOperationItem] = []
    for resolution in resolutions:
        operation = manifest.operations[resolution.operation_id]
        try:
            items.append(
                _apply_drift_resolution(
                    repo,
                    client,
                    manifest,
                    resolution,
                    provider_events,
                )
            )
        except (
            IntervalsIcuError,
            OSError,
            PublicationSafetyError,
            RemoteWorkoutDriftError,
        ) as exc:
            current_matches = matching_tombstone_events(provider_events, operation)
            current_remote = current_matches[0] if len(current_matches) == 1 else None
            items.append(
                _result_item(
                    operation,
                    status="error",
                    event_id=(
                        current_remote.id
                        if current_remote is not None
                        else resolution.event_id
                    ),
                    error_type=(
                        "remote_drift"
                        if isinstance(exc, RemoteWorkoutDriftError)
                        else "publication_safety"
                        if isinstance(exc, PublicationSafetyError)
                        else "provider"
                    ),
                    message=str(exc),
                    drift_resolution_token_sha256=(
                        publication_deletion_drift_token(operation, current_remote)
                        if isinstance(exc, RemoteWorkoutDriftError)
                        and current_remote is not None
                        else None
                    ),
                )
            )
    partial = any(item.status == "error" for item in items)
    return PublicationDeletionOperationsReport(
        reconciliation_safe=not partial,
        partial=partial,
        items=items,
    )
