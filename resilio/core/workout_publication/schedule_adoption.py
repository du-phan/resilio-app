"""Recognize exact athlete calendar moves without adopting workout edits."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_matches,
    provider_local_date,
    training_week_bounds,
    validated_local_start,
)
from resilio.core.workout_publication.preparation import PreparedPublication
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import PublishedWorkout


def adoptable_same_week_occurrence_date(
    remote: EventDTO,
    prepared: PreparedPublication,
) -> date | None:
    """Return a remote date only when date is the sole owned-field change."""
    if remote.start_date_local is None:
        return None
    try:
        remote_occurrence_date = provider_local_date(remote.start_date_local)
    except PublicationSafetyError:
        return None
    if training_week_bounds(remote_occurrence_date) != training_week_bounds(prepared.workout.date):
        return None
    try:
        expected_start_date_local = validated_local_start(
            remote_occurrence_date,
            prepared.workout.start_time_local,
            prepared.schedule_timezone,
        )
    except PublicationSafetyError:
        return None
    if remote.start_date_local != expected_start_date_local:
        return None
    expected_moved_event = prepared.event.model_copy(
        update={"start_date_local": expected_start_date_local}
    )
    try:
        assert_remote_matches(
            remote,
            expected_moved_event,
            prepared.expected_step_semantics,
        )
    except PublicationSafetyError:
        return None
    return remote_occurrence_date


def record_independently_observed_same_week_date(
    prepared: PreparedPublication,
    previous: PublishedWorkout,
    remote: EventDTO,
) -> PreparedPublication:
    """Attach an independently verified provider date to the desired publication."""
    if remote.start_date_local is None:
        return prepared
    remote_occurrence_date = provider_local_date(remote.start_date_local)
    previous_occurrence_date = provider_local_date(previous.provider_start_date_local)
    if remote_occurrence_date == previous_occurrence_date or training_week_bounds(
        remote_occurrence_date
    ) != training_week_bounds(prepared.workout.date):
        return prepared
    placement = prepared.provider_occurrence_placement.model_copy(
        update={
            "calendar_source": "provider_calendar",
            "calendar_occurrence_date": remote_occurrence_date,
        }
    )
    return replace(prepared, provider_occurrence_placement=placement)
