"""Exact-identity reads for provider workout events."""

from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO


def get_exact_event(
    client: IntervalsIcuClient,
    event_id: int,
    *,
    athlete_id: str | None = None,
) -> EventDTO:
    """Read one event and reject a provider response for another identity."""
    remote = client.get_event(event_id, athlete_id=athlete_id)
    if remote.id != event_id:
        raise PublicationSafetyError("Intervals event readback identity changed")
    return remote
