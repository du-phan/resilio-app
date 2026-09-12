"""Read-only verification of one desired workout publication state."""

from __future__ import annotations

from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.authority_matching import (
    publication_record_has_retained_workout_authority,
)
from resilio.core.workout_publication.execution_placement import (
    assert_fulfillment_pair_matches_remote_placement as assert_pair_remote,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_matches,
    assert_remote_ownership,
    assert_remote_unchanged,
    pending_matches,
    provider_event_state_fingerprint,
    provider_local_date,
    training_week_bounds,
)
from resilio.core.workout_publication.preparation import (
    PreparedPublication,
    prepare_current_authority_pending,
    prepare_publication,
    prepare_retained_publication_verification,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.core.workout_publication.retained_authority import (
    retained_publication_authority,
)
from resilio.core.workout_publication.schedule_adoption import (
    adoptable_same_week_occurrence_date,
)
from resilio.core.workout_publication.service import WorkoutPublicationService
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout
from resilio.schemas.publication_placement import ProviderOccurrencePlacement


def _assert_exact_confirmed_target(
    remote: EventDTO,
    expected_remote_target: tuple[int, str] | None,
) -> None:
    if expected_remote_target is None:
        return
    if (
        remote.id != expected_remote_target[0]
        or provider_event_state_fingerprint(remote) != expected_remote_target[1]
    ):
        raise PublicationSafetyError("Remote event changed after athlete drift confirmation")


def _verification_remote(
    client: IntervalsIcuClient,
    previous: PublishedWorkout | None,
    matches: list[EventDTO],
    *,
    athlete_id: str,
) -> EventDTO | None:
    if previous is not None:
        return get_exact_event(client, previous.event_id, athlete_id=athlete_id)
    return matches[0] if matches else None


def _matches_published_or_pending(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    remote: EventDTO,
    previous: PublishedWorkout,
    pending_prepared: PreparedPublication,
    *,
    desired_provider_occurrence_date: date,
    allow_remote_schedule_adoption: bool,
) -> date:
    try:
        assert_remote_unchanged(remote, previous)
        return desired_provider_occurrence_date
    except PublicationSafetyError:
        pass
    pending_error: PublicationSafetyError | None = None
    try:
        assert_remote_matches(
            remote,
            pending_prepared.event,
            pending_prepared.expected_step_semantics,
        )
        return desired_provider_occurrence_date
    except PublicationSafetyError as exc:
        adopted_occurrence_date = (
            adoptable_same_week_occurrence_date(remote, pending_prepared)
            if allow_remote_schedule_adoption
            else None
        )
        if adopted_occurrence_date is not None:
            return adopted_occurrence_date
        pending_error = exc
    retained_move = (
        _retained_previous_move_date(repo, client, remote, previous)
        if allow_remote_schedule_adoption
        else None
    )
    if retained_move is not None:
        return retained_move
    if pending_error is not None:
        raise RemoteWorkoutDriftError(
            "Remote event matches neither published nor pending owned state"
        ) from pending_error
    return desired_provider_occurrence_date


def _retained_previous_move_date(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    remote: EventDTO,
    previous: PublishedWorkout,
) -> date | None:
    """Recognize exact retained content moved within its immutable training week."""
    if remote.start_date_local is None:
        return None
    remote_occurrence_date = provider_local_date(remote.start_date_local)
    try:
        retained = retained_publication_authority(repo, previous)
        expected = prepare_retained_publication_verification(
            retained.workout,
            previous,
            athlete_id=client.get_athlete().id,
            provider_name=retained.provider_name,
            provider_occurrence_date=remote_occurrence_date,
        )
        assert_remote_matches(
            remote,
            expected.event,
            expected.expected_step_semantics,
        )
    except PublicationSafetyError:
        return None
    if training_week_bounds(remote_occurrence_date) != training_week_bounds(
        previous.occurrence_date
    ):
        return None
    return remote_occurrence_date


def _verify_published_remote(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    remote: EventDTO,
    previous: PublishedWorkout,
    prepared: PreparedPublication,
    *,
    allow_remote_schedule_adoption: bool,
) -> date:
    try:
        assert_remote_unchanged(remote, previous)
    except PublicationSafetyError as drift_error:
        try:
            assert_remote_matches(
                remote,
                prepared.event,
                prepared.expected_step_semantics,
            )
        except PublicationSafetyError:
            adopted_occurrence_date = (
                adoptable_same_week_occurrence_date(remote, prepared)
                if allow_remote_schedule_adoption
                else None
            )
            if adopted_occurrence_date is not None:
                return adopted_occurrence_date
            retained_move = (
                _retained_previous_move_date(
                    repo,
                    client,
                    remote,
                    previous,
                )
                if allow_remote_schedule_adoption
                else None
            )
            if retained_move is None:
                raise drift_error
            return retained_move
        return prepared.provider_occurrence_date
    if previous.publication_fingerprint_sha256 == prepared.publication_fingerprint_sha256:
        assert_remote_matches(
            remote,
            prepared.event,
            prepared.expected_step_semantics,
        )
    return prepared.provider_occurrence_date


def _verify_superseded_pending_remote(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    remote: EventDTO,
    workout: AuthoritativeWorkout,
    pending: PendingWorkoutPublication,
    previous: PublishedWorkout | None,
    prepared: PreparedPublication,
    *,
    allow_remote_schedule_adoption: bool,
) -> date:
    """Classify remote state when old renderer bytes cannot be reconstructed."""
    if not publication_record_has_retained_workout_authority(pending, workout):
        raise PublicationSafetyError(
            "Superseded pending publication lacks retained workout authority"
        )
    if previous is not None:
        return _verify_published_remote(
            repo,
            client,
            remote,
            previous,
            prepared,
            allow_remote_schedule_adoption=allow_remote_schedule_adoption,
        )
    try:
        assert_remote_matches(
            remote,
            prepared.event,
            prepared.expected_step_semantics,
        )
    except PublicationSafetyError as exc:
        adopted_occurrence_date = (
            adoptable_same_week_occurrence_date(remote, prepared)
            if allow_remote_schedule_adoption
            else None
        )
        if adopted_occurrence_date is not None:
            return adopted_occurrence_date
        raise RemoteWorkoutDriftError(
            "Remote event differs from the current workout after its "
            "pending representation was superseded"
        ) from exc
    return prepared.provider_occurrence_date


def verify_workout_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    workout_service: WorkoutPublicationService,
    workout: AuthoritativeWorkout,
    *,
    restore_local: bool,
    provider_name: str,
    provider_occurrence_date: date,
    provider_occurrence_placement: ProviderOccurrencePlacement,
    expected_remote_target: tuple[int, str] | None,
    allow_remote_schedule_adoption: bool,
) -> date:
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
        provider_occurrence_placement=provider_occurrence_placement,
    )
    pending = manifest.pending.get(local_workout_id)
    matches = workout_service._identity_matches(prepared, previous, pending)
    remote = _verification_remote(
        client,
        previous,
        matches,
        athlete_id=prepared.athlete_id,
    )
    if previous is None:
        assert_pair_remote(repo, client, provider_occurrence_placement, remote)
    if remote is None:
        return provider_occurrence_date
    if previous is not None:
        assert_remote_ownership(
            remote,
            uid=previous.uid,
            external_id=previous.external_id,
        )
    if restore_local:
        _assert_exact_confirmed_target(remote, expected_remote_target)
        return provider_occurrence_date
    if pending is not None:
        try:
            pending_prepared = prepare_current_authority_pending(
                client,
                workout,
                previous=previous,
                pending=pending,
                pending_occurrence_placement=(
                    manifest.pending_provider_occurrence_placements[local_workout_id]
                ),
                provider_name=provider_name,
            )
        except PublicationSafetyError:
            if pending_matches(
                pending,
                uid=prepared.event.uid,
                external_id=prepared.external_id,
                fingerprint=prepared.publication_fingerprint_sha256,
            ):
                raise
            return _verify_superseded_pending_remote(
                repo,
                client,
                remote,
                workout,
                pending,
                previous,
                prepared,
                allow_remote_schedule_adoption=allow_remote_schedule_adoption,
            )
        if previous is None:
            try:
                assert_remote_matches(
                    remote,
                    pending_prepared.event,
                    pending_prepared.expected_step_semantics,
                )
            except PublicationSafetyError as exc:
                adopted_occurrence_date = (
                    adoptable_same_week_occurrence_date(
                        remote,
                        pending_prepared,
                    )
                    if allow_remote_schedule_adoption
                    else None
                )
                if adopted_occurrence_date is not None:
                    return adopted_occurrence_date
                raise RemoteWorkoutDriftError(
                    "Remote event differs from its pending owned state"
                ) from exc
            return provider_occurrence_date
        return _matches_published_or_pending(
            repo,
            client,
            remote,
            previous,
            pending_prepared,
            desired_provider_occurrence_date=provider_occurrence_date,
            allow_remote_schedule_adoption=allow_remote_schedule_adoption,
        )
    if previous is None:
        raise PublicationSafetyError("Remote owned-looking event exists without a local manifest")
    return _verify_published_remote(
        repo,
        client,
        remote,
        previous,
        prepared,
        allow_remote_schedule_adoption=allow_remote_schedule_adoption,
    )
