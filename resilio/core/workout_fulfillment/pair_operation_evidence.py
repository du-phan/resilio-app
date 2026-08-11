"""Exact lineage checks for durable native pairing operations."""

from datetime import datetime

from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.workout_fulfillment import (
    ProviderPairProvenance,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
    WorkoutFulfillmentRevocation,
)
from resilio.schemas.workout_pairing import (
    RemoteWorkoutPairingOperation,
    native_pair_operation_id,
    native_unpair_operation_id,
)


def fulfillment_request_sha256(fulfillment: WorkoutFulfillmentRecord) -> str:
    """Fingerprint the association before native provider-pair evidence is added."""
    return canonical_data_sha256(
        fulfillment.model_copy(update={"provider_pair": None})
    )


def association_authorized_at_utc(fulfillment: WorkoutFulfillmentRecord) -> datetime:
    """Return the latest timestamp that established the mutable association."""
    athlete_confirmation = fulfillment.athlete_confirmation
    return max(
        fulfillment.recorded_at_utc,
        (
            athlete_confirmation.confirmed_at_utc
            if athlete_confirmation is not None
            else fulfillment.recorded_at_utc
        ),
    )


def operation_proves_resilio_pair_request(
    operation: RemoteWorkoutPairingOperation | None,
) -> bool:
    """Return whether an operation proves a Resilio write could have occurred."""
    return operation is not None and (
        operation.state in {"pending", "verified"}
        or operation.provider_write_submitted_at_utc is not None
    )


def provider_pair_provenance_for_operation(
    operation: RemoteWorkoutPairingOperation | None,
) -> ProviderPairProvenance:
    """Classify exact observed pairing without overstating request submission."""
    if operation is None:
        return "provider_observed"
    if operation.provider_write_submitted_at_utc is not None:
        return "resilio_requested"
    return "pair_origin_ambiguous"


def pair_operation_id(
    *,
    fulfillment: WorkoutFulfillmentRecord,
    intervals_icu_activity_id: str,
    event_id: int,
) -> str:
    """Derive the stable identifier for one exact native pair request."""
    return native_pair_operation_id(
        local_activity_id=fulfillment.local_activity_id,
        intervals_icu_activity_id=intervals_icu_activity_id,
        workout_identity=fulfillment.workout_identity,
        event_id=event_id,
        fulfillment_record_sha256=fulfillment_request_sha256(fulfillment),
    )


def unpair_operation_id(revocation: WorkoutFulfillmentRevocation, *, event_id: int) -> str:
    """Derive the stable identifier for one exact revoked native pair."""
    fulfillment = revocation.fulfillment
    return native_unpair_operation_id(
        local_activity_id=fulfillment.local_activity_id,
        event_id=event_id,
        revocation_id=revocation.revocation_id,
        fulfillment_record_sha256=canonical_data_sha256(fulfillment),
    )


def unpair_operation_has_exact_authority(
    manifest: WorkoutFulfillmentManifest,
    *,
    operation: RemoteWorkoutPairingOperation,
    revocation: WorkoutFulfillmentRevocation,
) -> bool:
    """Prove an unpair target from provider evidence or its originating write."""
    fulfillment = revocation.fulfillment
    if (
        operation.action != "unpair"
        or operation.operation_id
        != unpair_operation_id(revocation, event_id=operation.event_id)
        or operation.fulfillment_record_sha256 != canonical_data_sha256(fulfillment)
    ):
        return False
    if fulfillment.provider_pair is not None:
        return fulfillment.provider_pair.event_id == operation.event_id
    return any(
        pair_operation.action == "pair"
        and pair_operation.local_activity_id == operation.local_activity_id
        and pair_operation.intervals_icu_activity_id
        == operation.intervals_icu_activity_id
        and pair_operation.workout_identity == operation.workout_identity
        and pair_operation.event_id == operation.event_id
        and pair_operation.activity_performance_evidence_sha256
        == operation.activity_performance_evidence_sha256
        and pair_operation.publication_provider_event_fingerprint_sha256
        == operation.publication_provider_event_fingerprint_sha256
        and pair_operation.fulfillment_record_sha256
        == operation.fulfillment_record_sha256
        and operation_proves_resilio_pair_request(pair_operation)
        for pair_operation in manifest.remote_pairing_operations.values()
    )


def matching_resilio_pair_operation(
    manifest: WorkoutFulfillmentManifest,
    *,
    publication: PublishedWorkout,
    fulfillment: WorkoutFulfillmentRecord,
) -> RemoteWorkoutPairingOperation | None:
    """Return the latest non-revoked operation for the current association lineage."""
    request_sha256 = fulfillment_request_sha256(fulfillment)
    candidates = [
        operation
        for operation in manifest.remote_pairing_operations.values()
        if operation.action == "pair"
        and operation.local_activity_id == fulfillment.local_activity_id
        and operation.workout_identity == fulfillment.workout_identity
        and operation.event_id == publication.event_id
        and operation.requested_at_utc >= association_authorized_at_utc(fulfillment)
        and operation_proves_resilio_pair_request(operation)
        and (
            operation.state == "verified"
            or (
                operation.activity_performance_evidence_sha256
                == fulfillment.activity_performance_evidence_sha256
                and operation.publication_provider_event_fingerprint_sha256
                == publication.provider_event_fingerprint_sha256
                and operation.fulfillment_record_sha256 == request_sha256
            )
        )
    ]
    return max(candidates, key=lambda item: item.requested_at_utc) if candidates else None
