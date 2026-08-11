"""Local state transitions for durable native pairing reconciliation."""

from datetime import datetime

from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.pair_operation_evidence import (
    fulfillment_request_sha256,
    pair_operation_id,
)
from resilio.core.workout_fulfillment.repository import save_fulfillment_manifest
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.workout_fulfillment import (
    ProviderPairedFulfillmentEvidence,
    ProviderPairProvenance,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from resilio.schemas.workout_pairing import (
    RemotePairingDriftResolution,
    RemotePairingStatus,
    RemoteWorkoutPairingOperation,
    RemoteWorkoutPairingResult,
    restored_pair_operation_id,
)


def new_pair_operation(
    *,
    publication: PublishedWorkout,
    fulfillment: WorkoutFulfillmentRecord,
    external_activity_id: str,
    requested_at_utc: datetime,
) -> RemoteWorkoutPairingOperation:
    """Build the stable initial intent for one exact native pair."""
    return RemoteWorkoutPairingOperation(
        operation_id=pair_operation_id(
            fulfillment=fulfillment,
            intervals_icu_activity_id=external_activity_id,
            event_id=publication.event_id,
        ),
        action="pair",
        state="pending",
        local_activity_id=fulfillment.local_activity_id,
        intervals_icu_activity_id=external_activity_id,
        workout_identity=fulfillment.workout_identity,
        event_id=publication.event_id,
        activity_performance_evidence_sha256=(
            fulfillment.activity_performance_evidence_sha256
        ),
        publication_provider_event_fingerprint_sha256=(
            publication.provider_event_fingerprint_sha256
        ),
        fulfillment_record_sha256=fulfillment_request_sha256(fulfillment),
        expected_paired_event_id_before=None,
        requested_at_utc=requested_at_utc,
    )


def restored_pair_operation(
    operation: RemoteWorkoutPairingOperation,
    resolution: RemotePairingDriftResolution,
    *,
    requested_at_utc: datetime,
) -> RemoteWorkoutPairingOperation:
    """Create an immutable descendant for an athlete-authorized restoration."""
    return operation.model_copy(
        update={
            "operation_id": restored_pair_operation_id(
                resolution.pairing_drift_token_sha256
            ),
            "state": "pending",
            "requested_at_utc": requested_at_utc,
            "expected_provider_activity_guard_sha256_before": None,
            "provider_write_submitted_at_utc": None,
            "last_attempted_at_utc": None,
            "verified_at_utc": None,
            "provider_activity_guard_sha256": None,
            "blocker_code": None,
            "blocker_message": None,
        }
    )


def pairing_result(
    operation: RemoteWorkoutPairingOperation,
    *,
    status: RemotePairingStatus,
    blocker_code: str | None = None,
    message: str | None = None,
    pairing_drift_token_sha256: str | None = None,
) -> RemoteWorkoutPairingResult:
    """Project one operation as a presentation-neutral result."""
    return RemoteWorkoutPairingResult(
        local_activity_id=operation.local_activity_id,
        local_workout_id=operation.workout_identity.local_workout_id,
        intervals_icu_activity_id=operation.intervals_icu_activity_id,
        event_id=operation.event_id,
        status=status,
        operation_id=operation.operation_id,
        blocker_code=blocker_code,
        message=message,
        pairing_drift_token_sha256=pairing_drift_token_sha256,
    )


def save_blocked_pair_operation(
    repo: RepositoryIO,
    manifest: WorkoutFulfillmentManifest,
    operation: RemoteWorkoutPairingOperation,
    *,
    blocker_code: str,
    message: str,
    attempted_at_utc: datetime,
    provider_write_submitted_at_utc: datetime | None = None,
) -> RemoteWorkoutPairingResult:
    """Persist one retryable provider pairing blocker."""
    blocked = operation.model_copy(
        update={
            "state": "blocked",
            "provider_write_submitted_at_utc": (
                provider_write_submitted_at_utc
                or operation.provider_write_submitted_at_utc
            ),
            "last_attempted_at_utc": attempted_at_utc,
            "verified_at_utc": None,
            "provider_activity_guard_sha256": None,
            "blocker_code": blocker_code,
            "blocker_message": message,
        }
    )
    manifest.remote_pairing_operations[blocked.operation_id] = blocked
    save_fulfillment_manifest(repo, manifest)
    return pairing_result(
        blocked,
        status="pairing_blocked",
        blocker_code=blocker_code,
        message=message,
    )


def save_provider_observed_pair(
    repo: RepositoryIO,
    manifest: WorkoutFulfillmentManifest,
    fulfillment: WorkoutFulfillmentRecord,
    *,
    event_id: int,
    observed_at_utc: datetime,
    external_activity_id: str,
) -> RemoteWorkoutPairingResult:
    """Add independently observed provider-pair evidence once."""
    enriched = fulfillment.model_copy(
        update={
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=event_id,
                provenance="provider_observed",
                observed_at_utc=observed_at_utc,
            )
        }
    )
    manifest.fulfillments[fulfillment.local_activity_id] = enriched
    save_fulfillment_manifest(repo, manifest)
    return RemoteWorkoutPairingResult(
        local_activity_id=fulfillment.local_activity_id,
        local_workout_id=fulfillment.workout_identity.local_workout_id,
        intervals_icu_activity_id=external_activity_id,
        event_id=event_id,
        status="pairing_noop",
    )


def save_verified_pair_operation(
    repo: RepositoryIO,
    manifest: WorkoutFulfillmentManifest,
    operation: RemoteWorkoutPairingOperation,
    fulfillment: WorkoutFulfillmentRecord,
    *,
    provider_activity_guard_sha256: str,
    verified_at_utc: datetime,
    provenance: ProviderPairProvenance,
    status: RemotePairingStatus,
) -> RemoteWorkoutPairingResult:
    """Atomically persist verified operation and fulfillment evidence."""
    verified = operation.model_copy(
        update={
            "state": "verified",
            "expected_provider_activity_guard_sha256_before": (
                operation.expected_provider_activity_guard_sha256_before
                or provider_activity_guard_sha256
            ),
            "last_attempted_at_utc": verified_at_utc,
            "verified_at_utc": verified_at_utc,
            "provider_activity_guard_sha256": provider_activity_guard_sha256,
            "blocker_code": None,
            "blocker_message": None,
        }
    )
    enriched = fulfillment.model_copy(
        update={
            "provider_pair": ProviderPairedFulfillmentEvidence(
                event_id=operation.event_id,
                provenance=provenance,
                observed_at_utc=verified_at_utc,
            )
        }
    )
    manifest.remote_pairing_operations[verified.operation_id] = verified
    manifest.fulfillments[fulfillment.local_activity_id] = enriched
    save_fulfillment_manifest(repo, manifest)
    return pairing_result(verified, status=status)
