"""Semantic verification for retained owned workout publications."""

from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_matches,
    provider_local_date,
    training_week_bounds,
)
from resilio.core.workout_publication.preparation import (
    prepare_retained_publication_verification,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthority,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublishedWorkout,
)


def remote_matches_retained_record(
    client: IntervalsIcuClient,
    remote: EventDTO,
    record: PublishedWorkout | PendingWorkoutPublication,
    authority: RetainedPublicationAuthority,
) -> bool:
    """Return whether remote content and occurrence match retained authority."""
    if remote.start_date_local is None:
        return False
    try:
        remote_occurrence_date = provider_local_date(remote.start_date_local)
        expected = prepare_retained_publication_verification(
            authority.workout,
            record,
            athlete_id=client.get_athlete().id,
            provider_name=authority.provider_name,
            provider_occurrence_date=remote_occurrence_date,
        )
        assert_remote_matches(
            remote,
            expected.event,
            expected.expected_step_semantics,
        )
    except PublicationSafetyError:
        return False
    persisted_occurrence_date = provider_local_date(record.provider_start_date_local)
    return remote_occurrence_date == persisted_occurrence_date or training_week_bounds(
        remote_occurrence_date
    ) == training_week_bounds(record.occurrence_date)
