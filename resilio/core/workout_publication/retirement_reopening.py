"""Reopen an early-retired publication after explicit fulfillment revocation."""

from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.manifest import save_manifest
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRevocation


def _matching_revocation(
    manifest: PublicationManifest,
    *,
    local_workout_id: str,
    revocations: list[WorkoutFulfillmentRevocation],
) -> WorkoutFulfillmentRevocation | None:
    retired = manifest.retired.get(local_workout_id)
    retired_pending = manifest.retired_pending.get(local_workout_id)
    active_retirements = [
        record
        for record in (retired, retired_pending)
        if record is not None and record.reopened_at_utc is None
    ]
    matching = [
        revocation
        for revocation in revocations
        if revocation.fulfillment.workout_identity.local_workout_id == local_workout_id
        and any(
            revocation.fulfillment.local_activity_id == retirement.fulfilling_local_activity_id
            and canonical_data_sha256(revocation.fulfillment)
            == retirement.fulfillment_record_sha256_at_retirement
            and revocation.revoked_at_utc >= retirement.retired_at_utc
            for retirement in active_retirements
        )
    ]
    return matching[-1] if matching else None


def reopen_revoked_fulfillment_retirement(
    repo: RepositoryIO,
    manifest: PublicationManifest,
    *,
    local_workout_id: str,
) -> PublicationManifest:
    """Persist a recoverable reopening when exact revocation evidence exists."""
    revocation = _matching_revocation(
        manifest,
        local_workout_id=local_workout_id,
        revocations=load_fulfillment_manifest(repo).revoked_fulfillments,
    )
    if revocation is None:
        return manifest
    updated = manifest.model_copy(deep=True)
    reopening = {
        "reopened_by_fulfillment_revocation_id": revocation.revocation_id,
        "reopened_at_utc": revocation.revoked_at_utc,
    }
    retired = updated.retired.get(local_workout_id)
    if retired is not None and retired.reopened_at_utc is None:
        updated.retired[local_workout_id] = retired.model_copy(update=reopening)
    retired_pending = updated.retired_pending.get(local_workout_id)
    if retired_pending is not None and retired_pending.reopened_at_utc is None:
        updated.retired_pending[local_workout_id] = retired_pending.model_copy(update=reopening)
    save_manifest(repo, updated)
    return updated
