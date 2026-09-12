"""Date-bounded discovery of exact Resilio-owned provider event identities."""

from __future__ import annotations

from datetime import date

from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_external_ownership,
    assert_remote_ownership,
    external_id_for,
    provider_local_date,
    training_week_bounds,
    uid_for,
)
from resilio.core.workout_publication.preparation import (
    PreparedPublication,
    RetainedPublicationVerification,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout


def _fresh_identity_matches(
    client: IntervalsIcuClient,
    *,
    athlete_id: str,
    uid: str,
    external_id: str,
    identity_dates: set[date],
    search_provider_wide: bool,
) -> list[EventDTO]:
    oldest = date.min if search_provider_wide else min(identity_dates)
    newest = date.max if search_provider_wide else max(identity_dates)
    events = client.list_events(oldest, newest, athlete_id=athlete_id)
    matches = [
        event for event in events if event.uid == uid or event.external_id == external_id
    ]
    if len(matches) > 1:
        raise PublicationSafetyError("Multiple remote events claim the workout ownership identity")
    return [
        get_exact_event(client, remote.id, athlete_id=athlete_id) for remote in matches
    ]


def discover_owned_identity_matches(
    client: IntervalsIcuClient,
    prepared: PreparedPublication | RetainedPublicationVerification,
    *,
    previous: PublishedWorkout | None,
    pending: PendingWorkoutPublication | None,
) -> list[EventDTO]:
    """Find one exact identity in its week, then provider-wide when pending-only."""
    week_start, week_end = training_week_bounds(prepared.workout.date)
    identity_dates = {
        week_start,
        week_end,
        prepared.workout.date,
        prepared.provider_occurrence_date,
    }
    if previous is not None:
        identity_dates.add(provider_local_date(previous.provider_start_date_local))
    if pending is not None:
        identity_dates.add(pending.occurrence_date)
        identity_dates.add(provider_local_date(pending.provider_start_date_local))
    fresh_matches = _fresh_identity_matches(
        client,
        athlete_id=prepared.athlete_id,
        uid=prepared.event.uid,
        external_id=prepared.event.external_id,
        identity_dates=identity_dates,
        search_provider_wide=pending is not None and previous is None,
    )
    for remote in fresh_matches:
        if previous is not None:
            assert_remote_ownership(
                remote,
                uid=previous.uid,
                external_id=prepared.event.external_id,
            )
        else:
            assert_remote_external_ownership(
                remote,
                external_id=prepared.event.external_id,
            )
    return fresh_matches


def discover_pending_owned_identity_matches(
    client: IntervalsIcuClient,
    pending: PendingWorkoutPublication,
    *,
    athlete_id: str,
) -> list[EventDTO]:
    """Find a pending-only event without reconstructing renderer-derived bytes."""
    local_workout_id = pending.workout_identity.local_workout_id
    if (
        pending.external_id != external_id_for(local_workout_id)
        or pending.uid != uid_for(local_workout_id)
    ):
        raise PublicationSafetyError(
            "Pending-only publication identity differs from its deterministic workout identity"
        )
    week_start, week_end = training_week_bounds(pending.occurrence_date)
    fresh_matches = _fresh_identity_matches(
        client,
        athlete_id=athlete_id,
        uid=pending.uid,
        external_id=pending.external_id,
        identity_dates={
            week_start,
            week_end,
            pending.occurrence_date,
            provider_local_date(pending.provider_start_date_local),
        },
        search_provider_wide=True,
    )
    for remote in fresh_matches:
        assert_remote_external_ownership(
            remote,
            external_id=pending.external_id,
        )
    return fresh_matches
