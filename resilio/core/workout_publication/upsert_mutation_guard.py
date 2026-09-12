"""Fresh semantic guards for provider upserts that target an existing event."""

from resilio.core.workout_publication.policy import (
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    assert_remote_ownership,
    assert_remote_unchanged,
    provider_event_state_fingerprint,
)
from resilio.core.workout_publication.preparation import PreparedPublication
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import PublishedWorkout


def observe_existing_upsert_target(
    client: IntervalsIcuClient,
    prepared: PreparedPublication,
    previous: PublishedWorkout | None,
    *,
    confirmed_or_classified_target: tuple[int, str] | None,
) -> tuple[int, str] | None:
    """Fresh-read and authorize the existing identity before staging an upsert."""
    if previous is None and confirmed_or_classified_target is None:
        return None
    if confirmed_or_classified_target is not None:
        event_id = confirmed_or_classified_target[0]
    else:
        assert previous is not None
        event_id = previous.event_id
    remote = get_exact_event(
        client,
        event_id,
        athlete_id=prepared.athlete_id,
    )
    if previous is not None:
        assert_remote_ownership(
            remote,
            uid=previous.uid,
            external_id=previous.external_id,
        )
    else:
        assert_remote_external_ownership(
            remote,
            external_id=prepared.external_id,
        )
    observed = (remote.id, provider_event_state_fingerprint(remote))
    if confirmed_or_classified_target is not None:
        if observed != confirmed_or_classified_target:
            raise RemoteWorkoutDriftError("Remote event changed before publication update staging")
    else:
        assert previous is not None
        assert_remote_unchanged(remote, previous)
    return observed


def assert_upsert_target_still_fresh(
    client: IntervalsIcuClient,
    prepared: PreparedPublication,
    observed_target: tuple[int, str] | None,
) -> EventDTO | None:
    """Re-read an existing target after durable staging and before provider mutation."""
    if observed_target is None:
        return None
    remote = get_exact_event(
        client,
        observed_target[0],
        athlete_id=prepared.athlete_id,
    )
    assert_remote_external_ownership(
        remote,
        external_id=prepared.external_id,
    )
    if (
        remote.id,
        provider_event_state_fingerprint(remote),
    ) != observed_target:
        raise RemoteWorkoutDriftError("Remote event changed immediately before publication update")
    return remote
