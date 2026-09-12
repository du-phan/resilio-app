"""Durable, freshly guarded mutation of one prepared workout publication."""

from datetime import datetime, timezone

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.execution_placement import (
    assert_fulfillment_pair_matches_remote_placement,
)
from resilio.core.workout_publication.manifest import save_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_external_ownership,
    assert_remote_matches,
    publication_fingerprint,
)
from resilio.core.workout_publication.preparation import PreparedPublication
from resilio.core.workout_publication.publication_records import (
    persist_prepared_publication,
    publication_result,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.core.workout_publication.upsert_mutation_guard import (
    assert_upsert_target_still_fresh,
    observe_existing_upsert_target,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO, EventWriteDTO
from resilio.integrations.intervals_icu.errors import (
    IntervalsIcuError,
    IntervalsRequestNotSubmittedError,
)
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublicationResult,
    PublishedWorkout,
)


def _clear_definitively_rejected_intent(
    repo: RepositoryIO,
    manifest: PublicationManifest,
    local_workout_id: str,
) -> None:
    del manifest.pending[local_workout_id]
    del manifest.pending_provider_occurrence_placements[local_workout_id]
    save_manifest(repo, manifest)


def _outbound_event(
    prepared: PreparedPublication,
    fresh_target: EventDTO | None,
) -> EventWriteDTO:
    return (
        prepared.event
        if fresh_target is None
        else prepared.event.model_copy(update={"uid": fresh_target.uid})
    )


def upsert_prepared_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    prepared: PreparedPublication,
    manifest: PublicationManifest,
    previous: PublishedWorkout | None,
    *,
    remote_identity_exists: bool = False,
    expected_existing_target: tuple[int, str] | None = None,
) -> PublicationResult:
    """Stage exact intent, recheck mutable authority, mutate, and persist readback."""
    observed_existing_target = observe_existing_upsert_target(
        client,
        prepared,
        previous,
        confirmed_or_classified_target=expected_existing_target,
    )
    workout = prepared.workout
    manifest.pending[workout.id] = PendingWorkoutPublication(
        workout_identity=prepared.workout_identity,
        applied_week_approval_id=prepared.applied_week_approval_id,
        applied_running_workouts_sha256=prepared.applied_running_workouts_sha256,
        workout_prescription_sha256=prepared.workout_prescription_sha256,
        schedule_timezone=prepared.schedule_timezone,
        uid=prepared.event.uid,
        external_id=prepared.external_id,
        publication_fingerprint_sha256=prepared.publication_fingerprint_sha256,
        rendered_workout_sha256=prepared.rendered_workout_sha256,
        sport_settings_version_sha256=prepared.settings_version_sha256,
        sport="run",
        occurrence_date=workout.date,
        approved_start_time_local=workout.start_time_local,
        provider_start_date_local=prepared.provider_start_date_local,
        garmin_forwarding_eligible=prepared.garmin_forwarding_eligible,
        prepared_at_utc=datetime.now(timezone.utc),
    )
    manifest.pending_provider_occurrence_placements[
        workout.id
    ] = prepared.provider_occurrence_placement
    save_manifest(repo, manifest)
    fresh_target = assert_upsert_target_still_fresh(
        client,
        prepared,
        observed_existing_target,
    )
    assert_fulfillment_pair_matches_remote_placement(
        repo,
        client,
        prepared.provider_occurrence_placement,
        fresh_target,
    )
    fresh_target = assert_upsert_target_still_fresh(
        client,
        prepared,
        observed_existing_target,
    )
    outbound_event = _outbound_event(prepared, fresh_target)
    try:
        response = client.upsert_event(outbound_event, athlete_id=prepared.athlete_id)
    except IntervalsRequestNotSubmittedError:
        _clear_definitively_rejected_intent(repo, manifest, workout.id)
        raise
    except IntervalsIcuError as exc:
        if exc.status_code is not None and 400 <= exc.status_code < 500 and exc.status_code != 408:
            _clear_definitively_rejected_intent(repo, manifest, workout.id)
        raise
    if observed_existing_target is not None and response.id != observed_existing_target[0]:
        raise PublicationSafetyError("Provider upsert changed the existing event identity")
    read_back = get_exact_event(
        client,
        response.id,
        athlete_id=prepared.athlete_id,
    )
    remote_uid = assert_remote_external_ownership(
        read_back,
        external_id=prepared.external_id,
    )
    assert_remote_matches(
        read_back,
        outbound_event,
        prepared.expected_step_semantics,
    )
    persisted_event = outbound_event.model_copy(update={"uid": remote_uid})
    persisted_fingerprint = publication_fingerprint(
        persisted_event,
        prepared.settings_version_sha256,
    )
    persist_prepared_publication(
        manifest,
        prepared,
        read_back,
        uid=remote_uid,
        fingerprint_sha256=persisted_fingerprint,
    )
    save_manifest(repo, manifest)
    return publication_result(
        prepared,
        read_back,
        action=(
            "updated"
            if previous is not None
            or remote_identity_exists
            or observed_existing_target is not None
            else "created"
        ),
        uid=remote_uid,
        fingerprint_sha256=persisted_fingerprint,
    )
