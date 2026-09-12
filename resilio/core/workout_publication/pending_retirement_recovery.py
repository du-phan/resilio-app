"""Recovery and confirmed restoration of exact past publication events."""

from dataclasses import replace
from datetime import date, datetime, timezone

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.authority_matching import (
    publication_record_has_retained_workout_authority,
)
from resilio.core.workout_publication.manifest import load_manifest, save_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    assert_remote_matches,
    provider_event_state_fingerprint,
    provider_local_date,
    publication_fingerprint,
    published_record,
    training_week_bounds,
    uid_for,
)
from resilio.core.workout_publication.preparation import (
    RetainedPublicationVerification,
    prepare_retained_publication_replacement,
    prepare_retained_publication_verification,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthority,
)
from resilio.core.workout_publication.semantics import workout_semantics_sha256
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationAction,
    PublicationResult,
    PublishedWorkout,
)
from resilio.schemas.publication_placement import ProviderOccurrencePlacement

PublicationRecord = PublishedWorkout | PendingWorkoutPublication


def restored_provider_occurrence_date(
    record: PublicationRecord,
    observed_provider_occurrence_date: date,
) -> date:
    """Retain a valid same-week drag; otherwise restore the approved local date."""
    if training_week_bounds(observed_provider_occurrence_date) == training_week_bounds(
        record.occurrence_date
    ):
        return observed_provider_occurrence_date
    return record.occurrence_date


def _restoration_garmin_eligibility(record: PublicationRecord) -> bool | None:
    if isinstance(record, PendingWorkoutPublication):
        return record.garmin_forwarding_eligible
    if record.garmin_forwarding_status == "eligible_unverified":
        return True
    if record.garmin_forwarding_status == "not_configured":
        return False
    return None


def _restoration_pending(
    record: PublicationRecord,
    verification: RetainedPublicationVerification,
) -> PendingWorkoutPublication:
    return PendingWorkoutPublication(
        workout_identity=record.workout_identity,
        applied_week_approval_id=record.applied_week_approval_id,
        applied_running_workouts_sha256=record.applied_running_workouts_sha256,
        workout_prescription_sha256=record.workout_prescription_sha256,
        schedule_timezone=record.schedule_timezone,
        uid=record.uid,
        external_id=record.external_id,
        publication_fingerprint_sha256=publication_fingerprint(
            verification.event,
            record.sport_settings_version_sha256,
        ),
        rendered_workout_sha256=verification.rendered_workout_sha256,
        sport_settings_version_sha256=record.sport_settings_version_sha256,
        sport="run",
        occurrence_date=record.occurrence_date,
        approved_start_time_local=record.approved_start_time_local,
        provider_start_date_local=verification.event.start_date_local,
        garmin_forwarding_eligible=_restoration_garmin_eligibility(record),
        prepared_at_utc=datetime.now(timezone.utc),
    )


def restore_confirmed_past_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    record: PublicationRecord,
    authority: RetainedPublicationAuthority,
    observed: EventDTO,
    *,
    expected_remote_target: tuple[int, str],
    renderer_representation_superseded: bool = False,
) -> PublicationResult:
    """Restore confirmed drift under durable intent and retain its exact readback."""
    if observed.start_date_local is None:
        raise PublicationSafetyError(
            "Confirmed past publication lacks a provider occurrence timestamp"
        )
    provider_occurrence_date = restored_provider_occurrence_date(
        record,
        provider_local_date(observed.start_date_local),
    )
    if renderer_representation_superseded:
        if not publication_record_has_retained_workout_authority(record, authority.workout):
            raise PublicationSafetyError(
                "Renderer-superseded restoration lacks retained workout authority"
            )
        verification = prepare_retained_publication_replacement(
            authority.workout,
            record,
            athlete_id=client.get_athlete().id,
            provider_name=authority.provider_name,
            provider_occurrence_date=provider_occurrence_date,
        )
    else:
        verification = prepare_retained_publication_verification(
            authority.workout,
            record,
            athlete_id=client.get_athlete().id,
            provider_name=authority.provider_name,
            provider_occurrence_date=provider_occurrence_date,
        )
    pending = _restoration_pending(record, verification)
    local_workout_id = record.workout_identity.local_workout_id
    manifest = load_manifest(repo)
    active_record = manifest.pending.get(local_workout_id) or manifest.workouts.get(
        local_workout_id
    )
    if active_record != record:
        raise PublicationSafetyError("Past publication authority changed before restore staging")
    manifest.pending[local_workout_id] = pending
    manifest.pending_provider_occurrence_placements[local_workout_id] = ProviderOccurrencePlacement(
        calendar_source=(
            "approved_schedule"
            if provider_occurrence_date == record.occurrence_date
            else "provider_calendar"
        ),
        calendar_occurrence_date=provider_occurrence_date,
    )
    save_manifest(repo, manifest)
    fresh = get_exact_event(
        client,
        observed.id,
        athlete_id=verification.athlete_id,
    )
    observed_target = (observed.id, provider_event_state_fingerprint(observed))
    fresh_target = (fresh.id, provider_event_state_fingerprint(fresh))
    if fresh_target != observed_target or fresh_target != expected_remote_target:
        raise RemoteWorkoutDriftError(
            "Past publication changed immediately before confirmed restore"
        )
    remote_uid = assert_remote_external_ownership(
        fresh,
        external_id=record.external_id,
    )
    verification = replace(
        verification,
        event=verification.event.model_copy(update={"uid": remote_uid}),
    )
    response = client.upsert_event(
        verification.event,
        athlete_id=verification.athlete_id,
    )
    if response.id != observed.id:
        raise PublicationSafetyError("Confirmed past restore created a different provider event")
    read_back = get_exact_event(
        client,
        response.id,
        athlete_id=verification.athlete_id,
    )
    if read_back.id != observed.id:
        raise PublicationSafetyError("Confirmed past restore read back a different provider event")
    assert_remote_external_ownership(read_back, external_id=record.external_id)
    assert_remote_matches(
        read_back,
        verification.event,
        verification.expected_step_semantics,
    )
    return preserve_exact_past_pending_publication(
        repo,
        client,
        pending,
        verification,
        read_back,
        action="updated",
    )


def preserve_exact_past_pending_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    pending: PendingWorkoutPublication,
    verification: RetainedPublicationVerification,
    observed: EventDTO,
    *,
    action: PublicationAction = "skipped_past",
) -> PublicationResult:
    """Close an ambiguous create by retaining its exact past remote readback."""
    fresh = get_exact_event(
        client,
        observed.id,
        athlete_id=verification.athlete_id,
    )
    if provider_event_state_fingerprint(fresh) != provider_event_state_fingerprint(observed):
        raise RemoteWorkoutDriftError("Past pending event changed immediately before recovery")
    assert_remote_matches(
        fresh,
        verification.event,
        verification.expected_step_semantics,
    )
    remote_uid = assert_remote_external_ownership(
        fresh,
        external_id=pending.external_id,
    )
    verified_event = verification.event.model_copy(update={"uid": remote_uid})
    manifest = load_manifest(repo)
    local_workout_id = pending.workout_identity.local_workout_id
    coexisting_published = manifest.workouts.get(local_workout_id)
    requested_uid = (
        coexisting_published.requested_uid
        if coexisting_published is not None
        and coexisting_published.workout_identity == pending.workout_identity
        else uid_for(local_workout_id)
    )
    placement = manifest.pending_provider_occurrence_placements[local_workout_id]
    if placement.effective_occurrence_date != verification.provider_occurrence_date:
        placement = ProviderOccurrencePlacement(
            calendar_source="provider_calendar",
            calendar_occurrence_date=verification.provider_occurrence_date,
        )
    record = published_record(
        workout=verification.workout,
        workout_identity=pending.workout_identity,
        applied_week_approval_id=pending.applied_week_approval_id,
        applied_running_workouts_sha256=pending.applied_running_workouts_sha256,
        workout_prescription_sha256=pending.workout_prescription_sha256,
        schedule_timezone=pending.schedule_timezone,
        event_id=fresh.id,
        requested_uid=requested_uid,
        uid=remote_uid,
        external_id=pending.external_id,
        fingerprint=publication_fingerprint(
            verified_event,
            pending.sport_settings_version_sha256,
        ),
        rendered_hash=pending.rendered_workout_sha256,
        settings_version=pending.sport_settings_version_sha256,
        step_semantics_sha256=workout_semantics_sha256(verification.expected_step_semantics),
        provider_start_local=verification.event.start_date_local,
        garmin_eligible=pending.garmin_forwarding_eligible,
        remote=fresh,
    )
    manifest.workouts[local_workout_id] = record
    manifest.workout_provider_occurrence_placements[local_workout_id] = placement
    del manifest.pending[local_workout_id]
    del manifest.pending_provider_occurrence_placements[local_workout_id]
    save_manifest(repo, manifest)
    return PublicationResult(
        action=action,
        local_workout_id=local_workout_id,
        event_id=fresh.id,
        uid=remote_uid,
        external_id=pending.external_id,
        fingerprint_sha256=record.publication_fingerprint_sha256,
        provider_occurrence_date=verification.provider_occurrence_date,
        garmin_forwarding_status=record.garmin_forwarding_status,
        provider_push_errors=record.provider_push_errors,
    )


def recover_exact_past_pending_update(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    pending: PendingWorkoutPublication,
    remote: EventDTO,
    authority: RetainedPublicationAuthority,
) -> PublicationResult | None:
    """Resolve a dual-state update when its exact remote outcome is already past."""
    if remote.start_date_local is None:
        return None
    verification = prepare_retained_publication_verification(
        authority.workout,
        pending,
        athlete_id=client.get_athlete().id,
        provider_name=authority.provider_name,
        provider_occurrence_date=provider_local_date(remote.start_date_local),
    )
    try:
        assert_remote_matches(
            remote,
            verification.event,
            verification.expected_step_semantics,
        )
    except PublicationSafetyError:
        return None
    return preserve_exact_past_pending_publication(
        repo,
        client,
        pending,
        verification,
        remote,
    )
