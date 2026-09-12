"""Fresh-read guard for destructive provider event retirement."""

from collections.abc import Callable

from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_ownership,
    provider_event_state_fingerprint,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError


def assert_expected_remote_target(
    remote: EventDTO,
    expected_remote_target: tuple[int, str] | None,
    *,
    message: str,
) -> None:
    """Require the current event to be the exact athlete-confirmed target."""
    if expected_remote_target is not None and (
        remote.id != expected_remote_target[0]
        or provider_event_state_fingerprint(remote) != expected_remote_target[1]
    ):
        raise PublicationSafetyError(message)


def delete_remote_if_fresh(
    client: IntervalsIcuClient,
    observed: EventDTO,
    *,
    athlete_id: str,
    expected_uid: str,
    expected_external_id: str,
    expected_remote_target: tuple[int, str] | None,
    verify_semantics: Callable[[EventDTO], None] | None,
) -> bool:
    """Delete only after a fresh read proves the exact observed target is unchanged."""
    if verify_semantics is not None:
        verify_semantics(observed)
    try:
        fresh = get_exact_event(client, observed.id, athlete_id=athlete_id)
    except IntervalsNotFoundError:
        return False
    if provider_event_state_fingerprint(fresh) != provider_event_state_fingerprint(observed):
        raise RemoteWorkoutDriftError("Remote event changed immediately before retirement")
    assert_remote_ownership(
        fresh,
        uid=expected_uid,
        external_id=expected_external_id,
    )
    if expected_remote_target is not None and (
        fresh.id != expected_remote_target[0]
        or provider_event_state_fingerprint(fresh) != expected_remote_target[1]
    ):
        raise PublicationSafetyError("Remote event changed after athlete retirement confirmation")
    client.delete_event(fresh.id, athlete_id=athlete_id)
    try:
        get_exact_event(client, fresh.id, athlete_id=athlete_id)
    except IntervalsNotFoundError:
        return True
    raise PublicationSafetyError("Deleted event still exists on read-back")
