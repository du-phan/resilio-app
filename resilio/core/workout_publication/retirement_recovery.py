"""Local recovery after a published provider event is confirmed absent."""

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import save_manifest
from resilio.core.workout_publication.policy import provider_local_date
from resilio.core.workout_publication.publication_deletion_staging import (
    stage_dual_publication_deletion,
)
from resilio.core.workout_publication.publication_deletions import (
    activate_publication_deletion_monitoring,
)
from resilio.core.workout_publication.retained_authority import (
    RetainedPublicationAuthorities,
)
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublicationManifest,
    PublicationResult,
    PublishedWorkout,
)


def recover_absent_existing_publication(
    repo: RepositoryIO,
    local_workout_id: str,
    *,
    manifest: PublicationManifest,
    record: PublishedWorkout,
    pending: PendingWorkoutPublication | None,
    retained_authorities: RetainedPublicationAuthorities | None,
    authoritative_workout: AuthoritativeWorkout | None,
    provider_name: str | None,
) -> PublicationResult:
    """Retire local ownership while preserving any ambiguous update obligation."""
    deletion_operation = (
        stage_dual_publication_deletion(
            repo,
            pending,
            record,
            retained_authorities=retained_authorities,
            authoritative_workout=authoritative_workout,
            provider_name=provider_name,
        )
        if pending is not None
        else None
    )
    if deletion_operation is not None:
        activate_publication_deletion_monitoring(repo, deletion_operation)
    else:
        manifest.pending.pop(local_workout_id, None)
    del manifest.workouts[local_workout_id]
    del manifest.workout_provider_occurrence_placements[local_workout_id]
    save_manifest(repo, manifest)
    return PublicationResult(
        action="recovered_deleted",
        local_workout_id=local_workout_id,
        event_id=record.event_id,
        uid=record.uid,
        external_id=record.external_id,
        provider_occurrence_date=provider_local_date(record.provider_start_date_local),
    )
