"""Exact semantic evidence for durable publication deletion operations."""

from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    assert_remote_ownership,
    provider_event_fingerprint,
    publication_fingerprint,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthority,
)
from resilio.core.workout_publication.semantics import (
    WorkoutSemanticsError,
    expected_workout_semantics,
    provider_workout_semantics,
    workout_semantics_sha256,
)
from resilio.integrations.intervals_icu.dto import EventDTO, EventWriteDTO
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout
from resilio.schemas.publication_operations import PendingPublicationDeletionOperation


def pending_deletion_snapshot_matches(
    left: PendingWorkoutPublication,
    right: PendingWorkoutPublication,
) -> bool:
    """Compare deletion authority while ignoring additive informational metadata."""
    excluded = {"garmin_forwarding_eligible"}
    return left.model_dump(exclude=excluded) == right.model_dump(exclude=excluded)


def published_deletion_snapshot_matches(
    left: PublishedWorkout,
    right: PublishedWorkout,
) -> bool:
    """Compare legacy deletion snapshots outside separately bound step proof."""
    excluded = {"provider_step_semantics_sha256"}
    return left.model_dump(exclude=excluded) == right.model_dump(exclude=excluded)


def authority_step_semantics_sha256(
    authority: RetainedPublicationAuthority | None,
) -> str:
    """Hash the exact step semantics retained by one immutable authority."""
    if authority is None or authority.workout.prescription.structured_workout is None:
        raise PublicationSafetyError(
            "Publication deletion lacks exact parsed step-semantic authority"
        )
    try:
        semantics = expected_workout_semantics(
            authority.workout.prescription.structured_workout.steps
        )
    except WorkoutSemanticsError as exc:
        raise PublicationSafetyError(str(exc)) from exc
    return workout_semantics_sha256(semantics)


def _remote_step_semantics_sha256(remote: EventDTO) -> str:
    if remote.workout_doc is None:
        raise RemoteWorkoutDriftError("Late remote event lacks its parsed workout document")
    try:
        return workout_semantics_sha256(provider_workout_semantics(remote.workout_doc))
    except WorkoutSemanticsError as exc:
        raise RemoteWorkoutDriftError(str(exc)) from exc


def assert_remote_matches_deletion_pending(
    remote: EventDTO,
    pending: PendingWorkoutPublication,
    expected_step_semantics_sha256: str | None,
) -> None:
    """Require a late event to match the durable pending intent exactly."""
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
        raise RemoteWorkoutDriftError("Late remote event lacks the complete owned workout fields")
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
    if expected_step_semantics_sha256 is None:
        raise RemoteWorkoutDriftError(
            "Legacy publication deletion lacks parsed step-semantic authority; "
            "exact athlete confirmation is required"
        )
    if _remote_step_semantics_sha256(remote) != expected_step_semantics_sha256:
        raise RemoteWorkoutDriftError(
            "Late remote event differs from its exact parsed step semantics"
        )


def remote_matches_exact_previous_publication(
    remote: EventDTO,
    operation: PendingPublicationDeletionOperation,
) -> bool:
    """Return whether a remote is the operation's exact previous publication."""
    previous = operation.previous_publication
    expected_sha256 = operation.previous_step_semantics_sha256
    if previous is None or expected_sha256 is None:
        return False
    try:
        assert_remote_ownership(
            remote,
            uid=previous.uid,
            external_id=previous.external_id,
        )
        return (
            remote.id == previous.event_id
            and provider_event_fingerprint(remote) == previous.provider_event_fingerprint_sha256
            and _remote_step_semantics_sha256(remote) == expected_sha256
        )
    except PublicationSafetyError:
        return False


def assert_remote_matches_deletion_operation(
    remote: EventDTO,
    operation: PendingPublicationDeletionOperation,
) -> None:
    """Require a remote to match either exact authority retained by an operation."""
    if remote_matches_exact_previous_publication(remote, operation):
        return
    assert_remote_matches_deletion_pending(
        remote,
        operation.pending_publication,
        operation.pending_step_semantics_sha256,
    )
