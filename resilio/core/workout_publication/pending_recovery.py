"""Classify remote state for a superseded durable publication intent."""

from typing import Literal

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_matches,
    assert_remote_unchanged,
    provider_local_date,
)
from resilio.core.workout_publication.preparation import (
    PreparedPublication,
    prepare_retained_publication_verification,
)
from resilio.core.workout_publication.retained_authority import (
    retained_publication_authority,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import PublishedWorkout

SupersededPendingAction = Literal["persist_current", "upsert_current"]


def _matches_current(remote: EventDTO, prepared: PreparedPublication) -> bool:
    try:
        assert_remote_matches(
            remote,
            prepared.event,
            prepared.expected_step_semantics,
        )
    except PublicationSafetyError:
        return False
    return True


def remote_matches_previous_at_desired_date(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    remote: EventDTO,
    previous: PublishedWorkout,
    prepared: PreparedPublication,
) -> bool:
    if remote.start_date_local is None:
        return False
    try:
        remote_occurrence_date = provider_local_date(remote.start_date_local)
        if remote_occurrence_date != prepared.provider_occurrence_date:
            return False
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
        return False
    return True


def superseded_pending_action(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    remote: EventDTO,
    prepared: PreparedPublication,
    pending_prepared: PreparedPublication | None,
    previous: PublishedWorkout | None,
    *,
    adopt_remote_schedule: bool,
    current_settings_changed: bool,
) -> SupersededPendingAction:
    """Require mutation-time proof before recovering or replacing a pending intent."""
    if _matches_current(remote, prepared):
        return "upsert_current" if current_settings_changed else "persist_current"
    if adopt_remote_schedule:
        if previous is not None and remote_matches_previous_at_desired_date(
            repo,
            client,
            remote,
            previous,
            prepared,
        ):
            return "upsert_current"
        raise RemoteWorkoutDriftError("Remote schedule changed after date-only move verification")
    if previous is not None:
        try:
            assert_remote_unchanged(remote, previous)
        except PublicationSafetyError:
            pass
        else:
            return "upsert_current"
    if pending_prepared is None:
        raise RemoteWorkoutDriftError(
            "Remote event differs from the current workout after its pending "
            "representation was superseded"
        )
    try:
        assert_remote_matches(
            remote,
            pending_prepared.event,
            pending_prepared.expected_step_semantics,
        )
    except PublicationSafetyError as exc:
        raise RemoteWorkoutDriftError(
            "Remote event differs from its superseded pending intent"
        ) from exc
    return "upsert_current"
