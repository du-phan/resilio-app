"""Build publication records and results from exact provider readback."""

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import save_manifest
from resilio.core.workout_publication.policy import (
    assert_remote_external_ownership,
    garmin_forwarding_status,
    provider_push_errors,
    publication_fingerprint,
    published_record,
)
from resilio.core.workout_publication.preparation import PreparedPublication
from resilio.core.workout_publication.semantics import workout_semantics_sha256
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import (
    PublicationAction,
    PublicationManifest,
    PublicationResult,
    PublishedWorkout,
)


def prepared_published_record(
    prepared: PreparedPublication,
    remote: EventDTO,
    *,
    uid: str | None = None,
    fingerprint_sha256: str | None = None,
) -> PublishedWorkout:
    return published_record(
        workout=prepared.workout,
        workout_identity=prepared.workout_identity,
        applied_week_approval_id=prepared.applied_week_approval_id,
        applied_running_workouts_sha256=prepared.applied_running_workouts_sha256,
        workout_prescription_sha256=prepared.workout_prescription_sha256,
        schedule_timezone=prepared.schedule_timezone,
        event_id=remote.id,
        requested_uid=prepared.requested_uid,
        uid=uid if uid is not None else prepared.event.uid,
        external_id=prepared.external_id,
        fingerprint=(
            fingerprint_sha256
            if fingerprint_sha256 is not None
            else prepared.publication_fingerprint_sha256
        ),
        rendered_hash=prepared.rendered_workout_sha256,
        settings_version=prepared.settings_version_sha256,
        step_semantics_sha256=workout_semantics_sha256(prepared.expected_step_semantics),
        provider_start_local=prepared.provider_start_date_local,
        garmin_eligible=prepared.garmin_forwarding_eligible,
        remote=remote,
    )


def publication_result(
    prepared: PreparedPublication,
    remote: EventDTO,
    *,
    action: PublicationAction,
    uid: str | None = None,
    fingerprint_sha256: str | None = None,
) -> PublicationResult:
    return PublicationResult(
        action=action,
        local_workout_id=prepared.workout.id,
        event_id=remote.id,
        uid=uid if uid is not None else prepared.event.uid,
        external_id=prepared.external_id,
        fingerprint_sha256=(
            fingerprint_sha256
            if fingerprint_sha256 is not None
            else prepared.publication_fingerprint_sha256
        ),
        provider_occurrence_date=prepared.provider_occurrence_date,
        garmin_forwarding_status=garmin_forwarding_status(
            eligible=prepared.garmin_forwarding_eligible,
            remote=remote,
        ),
        provider_push_errors=provider_push_errors(remote),
    )


def persist_prepared_publication(
    manifest: PublicationManifest,
    prepared: PreparedPublication,
    remote: EventDTO,
    *,
    uid: str | None = None,
    fingerprint_sha256: str | None = None,
) -> PublishedWorkout:
    """Persist one readback and its placement provenance in the aggregate."""
    local_workout_id = prepared.workout.id
    record = prepared_published_record(
        prepared,
        remote,
        uid=uid,
        fingerprint_sha256=fingerprint_sha256,
    )
    manifest.workouts[local_workout_id] = record
    manifest.workout_provider_occurrence_placements[
        local_workout_id
    ] = prepared.provider_occurrence_placement
    manifest.pending.pop(local_workout_id, None)
    manifest.pending_provider_occurrence_placements.pop(local_workout_id, None)
    return record


def persist_recovered_publication(
    repo: RepositoryIO,
    manifest: PublicationManifest,
    prepared: PreparedPublication,
    remote: EventDTO,
) -> PublicationResult:
    """Commit an exact owned provider identity recovered after an interrupted write."""
    remote_uid = assert_remote_external_ownership(
        remote,
        external_id=prepared.external_id,
    )
    recovered_event = prepared.event.model_copy(update={"uid": remote_uid})
    recovered_fingerprint = publication_fingerprint(
        recovered_event,
        prepared.settings_version_sha256,
    )
    persist_prepared_publication(
        manifest,
        prepared,
        remote,
        uid=remote_uid,
        fingerprint_sha256=recovered_fingerprint,
    )
    save_manifest(repo, manifest)
    return publication_result(
        prepared,
        remote,
        action="recovered",
        uid=remote_uid,
        fingerprint_sha256=recovered_fingerprint,
    )
