"""Retention of past publications while ambiguous updates remain monitored."""

from datetime import date

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.pending_retirement_recovery import (
    recover_exact_past_pending_update,
    restore_confirmed_past_publication,
)
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.publication_deletion_staging import (
    authority_candidate,
    stage_dual_publication_deletion,
)
from resilio.core.workout_publication.publication_deletions import (
    activate_publication_deletion_monitoring,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthorities,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationResult,
    PublishedWorkout,
)


def preserve_past_publication(
    repo: RepositoryIO,
    record: PublishedWorkout,
    pending: PendingWorkoutPublication | None,
    *,
    provider_occurrence_date: date,
    retained_authorities: RetainedPublicationAuthorities | None,
    authoritative_workout: AuthoritativeWorkout | None,
    provider_name: str | None,
) -> PublicationResult:
    """Keep a past remote event while monitoring an ambiguous newer update."""
    if pending is not None:
        deletion_operation = stage_dual_publication_deletion(
            repo,
            pending,
            record,
            retained_authorities=retained_authorities,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
            preserve_previous_publication=True,
        )
        activate_publication_deletion_monitoring(repo, deletion_operation)
    return PublicationResult(
        action="skipped_past",
        local_workout_id=record.workout_identity.local_workout_id,
        event_id=record.event_id,
        uid=record.uid,
        external_id=record.external_id,
        provider_occurrence_date=provider_occurrence_date,
    )


def resolve_past_existing_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    record: PublishedWorkout,
    pending: PendingWorkoutPublication | None,
    remote: EventDTO,
    *,
    provider_occurrence_date: date,
    restore_local: bool,
    retained_authorities: RetainedPublicationAuthorities | None,
    authoritative_workout: AuthoritativeWorkout | None,
    provider_name: str | None,
    expected_remote_target: tuple[int, str] | None,
) -> PublicationResult:
    """Recover an applied past update, otherwise preserve the prior event."""
    if restore_local:
        source_record = pending or record
        source_authority = authority_candidate(
            retained_authorities,
            pending=pending is not None,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
        )
        if source_authority is None or expected_remote_target is None:
            raise PublicationSafetyError("Confirmed past restore lacks exact retained authority")
        return restore_confirmed_past_publication(
            repo,
            client,
            source_record,
            source_authority,
            remote,
            expected_remote_target=expected_remote_target,
        )
    if pending is not None and not restore_local:
        pending_authority = authority_candidate(
            retained_authorities,
            pending=True,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
        )
        if pending_authority is not None:
            recovered_pending = recover_exact_past_pending_update(
                repo,
                client,
                pending,
                remote,
                pending_authority,
            )
            if recovered_pending is not None:
                return recovered_pending
    return preserve_past_publication(
        repo,
        record,
        pending,
        provider_occurrence_date=provider_occurrence_date,
        retained_authorities=retained_authorities,
        authoritative_workout=authoritative_workout,
        provider_name=provider_name,
    )
