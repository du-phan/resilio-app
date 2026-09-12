"""Ownership-safe retirement of a pending-only workout publication."""

from datetime import date

from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.pending_retirement_recovery import (
    preserve_exact_past_pending_publication,
    restore_confirmed_past_publication,
    restored_provider_occurrence_date,
)
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    RemoteWorkoutDriftError,
    assert_remote_external_ownership,
    provider_local_date,
)
from resilio.core.workout_publication.preparation import (
    RetainedPublicationVerification,
    prepare_retained_publication_verification,
)
from resilio.core.workout_publication.publication_deletions import (
    activate_publication_deletion_monitoring,
    stage_pending_publication_deletion,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthority,
)
from resilio.core.workout_publication.retained_publication_semantics import (
    remote_matches_retained_record,
)
from resilio.core.workout_publication.retirement_mutation import (
    assert_expected_remote_target,
    delete_remote_if_fresh,
)
from resilio.core.workout_publication.semantics import workout_semantics_sha256
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventDTO
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationResult,
)


def _past_provider_occurrence_date(
    pending: PendingWorkoutPublication,
    remote: EventDTO,
    *,
    restore_local: bool,
) -> date | None:
    if remote.start_date_local is None:
        return None
    observed_date = provider_local_date(remote.start_date_local)
    return (
        restored_provider_occurrence_date(pending, observed_date)
        if restore_local
        else observed_date
    )


def retire_pending_publication(
    repo: RepositoryIO,
    client: IntervalsIcuClient,
    pending: PendingWorkoutPublication,
    prepared: RetainedPublicationVerification,
    remote: EventDTO | None,
    authority: RetainedPublicationAuthority,
    *,
    restore_local: bool,
    expected_remote_target: tuple[int, str] | None,
    as_of_date: date | None,
) -> PublicationResult:
    """Retire one pending-only intent after exact ownership verification."""
    local_workout_id = pending.workout_identity.local_workout_id
    result_uid = pending.uid
    provider_occurrence_date = (
        _past_provider_occurrence_date(
            pending,
            remote,
            restore_local=restore_local,
        )
        if remote is not None
        else None
    )
    if remote is not None:
        remote_uid = assert_remote_external_ownership(
            remote,
            external_id=pending.external_id,
        )
        result_uid = remote_uid
        assert_expected_remote_target(
            remote,
            expected_remote_target,
            message="Remote event changed after athlete deletion confirmation",
        )
        if not restore_local and not remote_matches_retained_record(
            client,
            remote,
            pending,
            authority,
        ):
            raise RemoteWorkoutDriftError("Pending owned event differs from its prepared workout")
        if (
            as_of_date is not None
            and provider_occurrence_date is not None
            and provider_occurrence_date < as_of_date
        ):
            if restore_local:
                if expected_remote_target is None:
                    raise PublicationSafetyError(
                        "Confirmed past restore lacks its exact remote target"
                    )
                return restore_confirmed_past_publication(
                    repo,
                    client,
                    pending,
                    authority,
                    remote,
                    expected_remote_target=expected_remote_target,
                )
            retained_at_remote_date = prepare_retained_publication_verification(
                authority.workout,
                pending,
                athlete_id=prepared.athlete_id,
                provider_name=authority.provider_name,
                provider_occurrence_date=provider_occurrence_date,
            )
            return preserve_exact_past_pending_publication(
                repo,
                client,
                pending,
                retained_at_remote_date,
                remote,
            )
    deletion_operation = stage_pending_publication_deletion(
        repo,
        pending,
        pending_step_semantics_sha256=workout_semantics_sha256(prepared.expected_step_semantics),
    )
    if remote is not None:
        verify_semantics = (
            None
            if restore_local
            else lambda fresh: _assert_pending_remote_semantics(
                client,
                fresh,
                pending,
                authority,
            )
        )
        delete_remote_if_fresh(
            client,
            remote,
            athlete_id=client.get_athlete().id,
            expected_uid=remote_uid,
            expected_external_id=pending.external_id,
            expected_remote_target=expected_remote_target,
            verify_semantics=verify_semantics,
        )
    activate_publication_deletion_monitoring(repo, deletion_operation)
    return PublicationResult(
        action="deleted" if remote is not None else "deletion_monitoring",
        local_workout_id=local_workout_id,
        event_id=remote.id if remote is not None else None,
        uid=result_uid,
        external_id=pending.external_id,
        provider_occurrence_date=(
            provider_occurrence_date or provider_local_date(pending.provider_start_date_local)
        ),
    )


def _assert_pending_remote_semantics(
    client: IntervalsIcuClient,
    remote: EventDTO,
    pending: PendingWorkoutPublication,
    authority: RetainedPublicationAuthority,
) -> None:
    if not remote_matches_retained_record(client, remote, pending, authority):
        raise RemoteWorkoutDriftError("Pending owned event differs from its prepared workout")
