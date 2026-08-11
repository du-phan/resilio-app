"""Date-bounded discovery of exact Resilio-owned provider event identities."""

from __future__ import annotations

from datetime import date

from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_external_ownership,
    assert_remote_ownership,
    provider_local_date,
    training_week_bounds,
)
from resilio.core.workout_publication.preparation import PreparedPublication
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout


def discover_owned_identity_matches(
    client: IntervalsIcuClient,
    prepared: PreparedPublication,
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
    events = client.list_events(
        min(identity_dates),
        max(identity_dates),
        athlete_id=prepared.athlete_id,
    )
    matches = [
        event
        for event in events
        if event.uid == prepared.event.uid
        or event.external_id == prepared.external_id
    ]
    if pending is not None and previous is None and not matches:
        provider_events = client.list_events(
            date.min,
            date.max,
            athlete_id=prepared.athlete_id,
        )
        matches = [
            event
            for event in provider_events
            if event.uid == prepared.event.uid
            or event.external_id == prepared.external_id
        ]
    if len(matches) > 1:
        raise PublicationSafetyError(
            "Multiple remote events claim the workout ownership identity"
        )
    for remote in matches:
        if previous is not None:
            assert_remote_ownership(
                remote,
                uid=previous.uid,
                external_id=prepared.external_id,
            )
        else:
            assert_remote_external_ownership(
                remote,
                external_id=prepared.external_id,
            )
    return matches
