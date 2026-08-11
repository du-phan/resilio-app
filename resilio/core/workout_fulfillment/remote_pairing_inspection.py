"""Read-only evidence validation and inspection for native activity pairing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_authority_is_current,
    assert_fulfillment_is_usable,
)
from resilio.core.workout_fulfillment.pair_operation_evidence import (
    matching_resilio_pair_operation,
    operation_proves_resilio_pair_request,
)
from resilio.core.workout_fulfillment.remote_pairing_state import (
    new_pair_operation,
    pairing_result,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.integrations.intervals_icu.activity_fingerprint import (
    performance_evidence_fingerprint,
)
from resilio.integrations.intervals_icu.activity_pairing import (
    activity_pairing_guard_sha256,
    activity_source_supports_pairing,
)
from resilio.integrations.intervals_icu.dto import (
    ActivityDTO,
    ActivityPairingWriteDTO,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from resilio.schemas.workout_pairing import (
    RemotePairingDriftResolution,
    RemoteWorkoutPairingOperation,
    RemoteWorkoutPairingResult,
    remote_pairing_drift_token_sha256,
)


class ActivityPairingClient(Protocol):
    def get_activity(self, activity_id: str, *, intervals: bool = True) -> ActivityDTO: ...

    def update_activity_pairing(
        self,
        activity_id: str,
        pairing: ActivityPairingWriteDTO,
    ) -> ActivityDTO: ...


def validate_remote_performance_evidence(
    remote: ActivityDTO,
    activity: CanonicalActivity,
) -> None:
    """Require the remote activity to match its synchronized canonical evidence."""
    expected_sha256 = activity.audit.performance_evidence_sha256
    observed_sha256 = performance_evidence_fingerprint(
        remote,
        activity.occurrence.timezone,
    )
    if expected_sha256 is None or observed_sha256 != expected_sha256:
        raise ValueError(
            "Intervals activity performance changed after canonical synchronization"
        )


def validate_local_pairing_evidence(
    *,
    authority: AuthoritativeWorkout,
    publication: PublishedWorkout,
    fulfillment: WorkoutFulfillmentRecord,
    activity: CanonicalActivity,
    manifest: WorkoutFulfillmentManifest,
) -> str:
    """Prove exact local authority and return the external activity identity."""
    assert_fulfillment_authority_is_current(fulfillment, authority)
    assert_fulfillment_is_usable(fulfillment, activity, manifest)
    if fulfillment.athlete_confirmation is None:
        raise ValueError("Native pairing mutation requires athlete-confirmed fulfillment")
    if publication.workout_identity != fulfillment.workout_identity:
        raise ValueError("Native pairing publication identity does not match fulfillment")
    if (
        publication.workout_prescription_sha256
        != fulfillment.workout_prescription_sha256
        or publication.occurrence_date != fulfillment.scheduled_local_date
        or publication.schedule_timezone != fulfillment.schedule_timezone
    ):
        raise ValueError("Native pairing publication authority does not match fulfillment")
    external_activity_id = activity.origin.intervals_icu_activity_id
    if external_activity_id is None:
        raise ValueError("Native pairing requires an Intervals.icu activity identity")
    return external_activity_id


def pending_pair_guard_changed(
    operation: RemoteWorkoutPairingOperation,
    *,
    observed_guard_sha256: str,
) -> bool:
    """Return whether a nonterminal operation observed different remote attributes."""
    expected_guard_sha256 = operation.expected_provider_activity_guard_sha256_before
    return (
        operation.state != "verified"
        and expected_guard_sha256 is not None
        and expected_guard_sha256 != observed_guard_sha256
    )


def matching_pairing_drift_resolution(
    manifest: WorkoutFulfillmentManifest,
    operation: RemoteWorkoutPairingOperation,
    *,
    observed_guard_sha256: str,
) -> RemotePairingDriftResolution | None:
    """Resolve athlete authority for one exact operation and observed remote guard."""
    drift_token = remote_pairing_drift_token_sha256(
        operation,
        provider_activity_guard_sha256=observed_guard_sha256,
    )
    return next(
        (
            resolution
            for resolution in manifest.remote_pairing_drift_resolutions
            if resolution.pairing_drift_token_sha256 == drift_token
            and resolution.pair_operation_snapshot == operation
            and resolution.observed_provider_activity_guard_sha256
            == observed_guard_sha256
        ),
        None,
    )


def pairing_guard_blocker(
    operation: RemoteWorkoutPairingOperation,
    *,
    observed_guard_sha256: str,
) -> RemoteWorkoutPairingResult:
    """Describe a changed remote guard without altering durable operation evidence."""
    drift_token = remote_pairing_drift_token_sha256(
        operation,
        provider_activity_guard_sha256=observed_guard_sha256,
    )
    return pairing_result(
        operation,
        status="pairing_blocked",
        blocker_code="provider_activity_changed_during_pairing",
        message="Intervals non-pairing fields changed after the pair request",
        pairing_drift_token_sha256=drift_token,
    )


def inspect_remote_pairing(
    repo: RepositoryIO,
    client: ActivityPairingClient,
    *,
    authority: AuthoritativeWorkout,
    publication: PublishedWorkout,
    fulfillment: WorkoutFulfillmentRecord,
    activity: CanonicalActivity,
    now_utc: datetime | None = None,
) -> RemoteWorkoutPairingResult:
    """Project one exact pairing without changing local or remote state."""
    inspection_time_utc = now_utc or datetime.now(timezone.utc)
    manifest = load_fulfillment_manifest(repo)
    external_activity_id = validate_local_pairing_evidence(
        authority=authority,
        publication=publication,
        fulfillment=fulfillment,
        activity=activity,
        manifest=manifest,
    )
    remote = client.get_activity(external_activity_id, intervals=False)
    validate_remote_performance_evidence(remote, activity)
    existing_operation = matching_resilio_pair_operation(
        manifest,
        fulfillment=fulfillment,
        publication=publication,
    )
    operation = existing_operation or new_pair_operation(
        publication=publication,
        fulfillment=fulfillment,
        external_activity_id=external_activity_id,
        requested_at_utc=inspection_time_utc,
    )
    observed_guard_sha256 = activity_pairing_guard_sha256(remote)
    guard_changed = pending_pair_guard_changed(
        operation,
        observed_guard_sha256=observed_guard_sha256,
    )
    resolution = matching_pairing_drift_resolution(
        manifest,
        operation,
        observed_guard_sha256=observed_guard_sha256,
    )
    if remote.paired_event_id == publication.event_id:
        if guard_changed and resolution is None:
            return pairing_guard_blocker(
                operation,
                observed_guard_sha256=observed_guard_sha256,
            )
        if not operation_proves_resilio_pair_request(existing_operation):
            return RemoteWorkoutPairingResult(
                local_activity_id=fulfillment.local_activity_id,
                local_workout_id=fulfillment.workout_identity.local_workout_id,
                intervals_icu_activity_id=external_activity_id,
                event_id=publication.event_id,
                status="pairing_noop",
            )
        return pairing_result(operation, status="pairing_noop")
    if remote.paired_event_id is not None:
        return pairing_result(
            operation,
            status="pairing_blocked",
            blocker_code="activity_paired_to_different_event",
            message="Intervals activity is already paired to a different event",
        )
    if operation.state == "verified":
        if (
            fulfillment.provider_pair is not None
            and fulfillment.provider_pair.provenance != "resilio_requested"
        ):
            return pairing_result(
                operation,
                status="pairing_blocked",
                blocker_code="ambiguous_pair_removed",
                message="The removed pair was not proven to originate from a Resilio write",
            )
        drift_token = remote_pairing_drift_token_sha256(
            operation,
            provider_activity_guard_sha256=observed_guard_sha256,
        )
        if resolution is None:
            return pairing_result(
                operation,
                status="pairing_blocked",
                blocker_code="resilio_requested_pair_removed",
                message="Intervals no longer reports the confirmed native pair",
                pairing_drift_token_sha256=drift_token,
            )
    if guard_changed and resolution is None:
        return pairing_guard_blocker(
            operation,
            observed_guard_sha256=observed_guard_sha256,
        )
    if not activity_source_supports_pairing(remote):
        return pairing_result(
            operation,
            status="pairing_blocked",
            blocker_code="activity_source_is_not_mutable",
            message="Intervals does not allow pairing updates for this activity source",
        )
    return pairing_result(operation, status="ready_to_pair")
