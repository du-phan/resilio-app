"""Construction of semantically complete publication deletion obligations."""

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.publication_deletion_evidence import (
    authority_step_semantics_sha256,
)
from resilio.core.workout_publication.publication_deletions import (
    stage_pending_publication_deletion,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthorities,
    RetainedPublicationAuthority,
)
from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout
from resilio.schemas.publication_operations import PendingPublicationDeletionOperation


def authority_candidate(
    retained_authorities: RetainedPublicationAuthorities | None,
    *,
    pending: bool,
    authoritative_workout: AuthoritativeWorkout | None,
    provider_name: str | None,
) -> RetainedPublicationAuthority | None:
    """Select exact retained authority, with current authority as explicit fallback."""
    retained = (
        retained_authorities.pending
        if pending and retained_authorities is not None
        else retained_authorities.published
        if retained_authorities is not None
        else None
    )
    if retained is not None:
        return retained
    if authoritative_workout is None or provider_name is None:
        return None
    return RetainedPublicationAuthority(
        workout=authoritative_workout,
        provider_name=provider_name,
    )


def stage_dual_publication_deletion(
    repo: RepositoryIO,
    pending: PendingWorkoutPublication,
    previous: PublishedWorkout,
    *,
    retained_authorities: RetainedPublicationAuthorities | None,
    authoritative_workout: AuthoritativeWorkout | None,
    provider_name: str | None,
    preserve_previous_publication: bool = False,
) -> PendingPublicationDeletionOperation:
    """Stage a durable deletion with both exact parsed semantic authorities."""
    pending_authority = authority_candidate(
        retained_authorities,
        pending=True,
        authoritative_workout=authoritative_workout,
        provider_name=provider_name,
    )
    previous_authority = authority_candidate(
        retained_authorities,
        pending=False,
        authoritative_workout=authoritative_workout,
        provider_name=provider_name,
    )
    return stage_pending_publication_deletion(
        repo,
        pending,
        previous=previous,
        pending_step_semantics_sha256=authority_step_semantics_sha256(pending_authority),
        previous_step_semantics_sha256=authority_step_semantics_sha256(previous_authority),
        preserve_previous_publication=preserve_previous_publication,
    )
