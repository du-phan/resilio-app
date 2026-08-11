"""Read-only verification of one desired workout publication state."""

from __future__ import annotations

from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    provider_event_fingerprint,
)
from resilio.core.workout_publication.preparation import (
    prepare_current_authority_pending,
    prepare_publication,
)
from resilio.core.workout_publication.semantics import StepSemantics
from resilio.core.workout_publication.service import WorkoutPublicationService
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO, EventWriteDTO
from resilio.schemas.publication import PublishedWorkout


def _assert_exact_confirmed_target(
    remote: EventDTO,
    expected_remote_target: tuple[int, str] | None,
) -> None:
    if expected_remote_target is None:
        return
    if (
        remote.id != expected_remote_target[0]
        or provider_event_fingerprint(remote) != expected_remote_target[1]
    ):
        raise PublicationSafetyError(
            "Remote event changed after athlete drift confirmation"
        )


def _matches_published_or_pending(
    remote: EventDTO,
    previous: PublishedWorkout,
    pending_event: EventWriteDTO,
    pending_semantics: tuple[StepSemantics, ...],
) -> None:
    try:
        assert_remote_unchanged(remote, previous)
        return
    except RemoteWorkoutDriftError:
        pass
    try:
        assert_remote_matches(remote, pending_event, pending_semantics)
    except PublicationSafetyError as exc:
        raise RemoteWorkoutDriftError(
            "Remote event matches neither published nor pending owned state"
        ) from exc


def verify_workout_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    workout_service: WorkoutPublicationService,
    workout: AuthoritativeWorkout,
    *,
    restore_local: bool,
    provider_name: str,
    provider_occurrence_date: date,
    expected_remote_target: tuple[int, str] | None,
) -> None:
    """Verify one exact desired, prior, or pending owned state without mutation."""
    manifest = load_manifest(repo)
    local_workout_id = workout.identity.local_workout_id
    previous = manifest.workouts.get(local_workout_id)
    prepared = prepare_publication(
        client,
        workout,
        previous=previous,
        provider_name=provider_name,
        provider_occurrence_date=provider_occurrence_date,
    )
    pending = manifest.pending.get(local_workout_id)
    matches = workout_service._identity_matches(prepared, previous, pending)
    remote = (
        client.get_event(previous.event_id, athlete_id=prepared.athlete_id)
        if previous is not None
        else matches[0]
        if matches
        else None
    )
    if remote is None:
        return
    if previous is not None:
        assert_remote_ownership(
            remote,
            uid=previous.uid,
            external_id=previous.external_id,
        )
    if restore_local:
        _assert_exact_confirmed_target(remote, expected_remote_target)
        return
    if pending is not None:
        pending_prepared = prepare_current_authority_pending(
            client,
            workout,
            previous=previous,
            pending=pending,
            provider_name=provider_name,
        )
        if previous is None:
            try:
                assert_remote_matches(
                    remote,
                    pending_prepared.event,
                    pending_prepared.expected_step_semantics,
                )
            except PublicationSafetyError as exc:
                raise RemoteWorkoutDriftError(
                    "Remote event differs from its pending owned state"
                ) from exc
            return
        _matches_published_or_pending(
            remote,
            previous,
            pending_prepared.event,
            pending_prepared.expected_step_semantics,
        )
        return
    if previous is None:
        raise PublicationSafetyError(
            "Remote owned-looking event exists without a local manifest"
        )
    assert_remote_unchanged(remote, previous)
    if previous.publication_fingerprint_sha256 == prepared.publication_fingerprint_sha256:
        assert_remote_matches(
            remote,
            prepared.event,
            prepared.expected_step_semantics,
        )
