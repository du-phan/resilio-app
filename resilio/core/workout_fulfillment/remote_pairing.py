"""Crash-recoverable reconciliation of native Intervals activity/event pairs."""

from __future__ import annotations

from datetime import datetime, timezone

from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.pair_operation_evidence import (
    association_authorized_at_utc,
    matching_resilio_pair_operation,
    operation_proves_resilio_pair_request,
    provider_pair_provenance_for_operation,
)
from resilio.core.workout_fulfillment.remote_pairing_drift import (
    confirm_remote_pairing_drift,
    confirm_remote_pairing_drifts,
)
from resilio.core.workout_fulfillment.remote_pairing_inspection import (
    ActivityPairingClient,
    inspect_remote_pairing,
    matching_pairing_drift_resolution,
    pairing_guard_blocker,
    pending_pair_guard_changed,
    validate_local_pairing_evidence,
    validate_remote_performance_evidence,
)
from resilio.core.workout_fulfillment.remote_pairing_state import (
    new_pair_operation,
    pairing_result,
    restored_pair_operation,
    save_blocked_pair_operation,
    save_provider_observed_pair,
    save_verified_pair_operation,
)
from resilio.core.workout_fulfillment.repository import (
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.integrations.intervals_icu.activity_pairing import (
    activity_pairing_guard_sha256,
    activity_source_supports_pairing,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO, ActivityPairingWriteDTO
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


class WorkoutPairingReconciliationService:
    """Reconcile one athlete-confirmed fulfillment through native pairing."""

    def __init__(self, repo: RepositoryIO, client: ActivityPairingClient):
        self.repo = repo
        self.client = client

    def inspect_pairing(
        self,
        *,
        authority: AuthoritativeWorkout,
        publication: PublishedWorkout,
        fulfillment: WorkoutFulfillmentRecord,
        activity: CanonicalActivity,
        now_utc: datetime | None = None,
    ) -> RemoteWorkoutPairingResult:
        return inspect_remote_pairing(
            self.repo,
            self.client,
            authority=authority,
            publication=publication,
            fulfillment=fulfillment,
            activity=activity,
            now_utc=now_utc,
        )

    def confirm_pairing_drift(
        self,
        *,
        operation_id: str,
        supplied_pairing_drift_token_sha256: str,
        athlete_confirmation_reference: str,
        confirmed_at_utc: datetime | None = None,
    ) -> RemotePairingDriftResolution:
        """Persist authority to restore one exact removed verified pair."""
        return confirm_remote_pairing_drift(
            self.repo,
            self.client,
            operation_id=operation_id,
            supplied_pairing_drift_token_sha256=(
                supplied_pairing_drift_token_sha256
            ),
            athlete_confirmation_reference=athlete_confirmation_reference,
            confirmed_at_utc=confirmed_at_utc,
        )

    def confirm_pairing_drifts(
        self,
        confirmations: list[tuple[str, str, str]],
        *,
        confirmed_at_utc: datetime | None = None,
    ) -> list[RemotePairingDriftResolution]:
        """Persist one fully validated pairing-drift authority set atomically."""
        return confirm_remote_pairing_drifts(
            self.repo,
            self.client,
            confirmations=confirmations,
            confirmed_at_utc=confirmed_at_utc,
        )

    def _perform_pairing_mutation(
        self,
        *,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
        fulfillment: WorkoutFulfillmentRecord,
        external_activity_id: str,
        event_id: int,
        provider_activity_guard_sha256: str,
        attempted_at_utc: datetime,
    ) -> RemoteWorkoutPairingResult:
        pending = operation.model_copy(
            update={
                "state": "pending",
                "expected_provider_activity_guard_sha256_before": (
                    operation.expected_provider_activity_guard_sha256_before
                    or provider_activity_guard_sha256
                ),
                "last_attempted_at_utc": attempted_at_utc,
                "verified_at_utc": None,
                "provider_activity_guard_sha256": None,
                "blocker_code": None,
                "blocker_message": None,
            }
        )
        manifest.remote_pairing_operations[pending.operation_id] = pending
        save_fulfillment_manifest(self.repo, manifest)
        try:
            update_response = self.client.update_activity_pairing(
                external_activity_id,
                ActivityPairingWriteDTO(paired_event_id=event_id),
            )
        except Exception:
            return pairing_result(
                pending,
                status="pairing_blocked",
                blocker_code="provider_pairing_request_failed",
                message="Intervals pairing request failed; the durable intent is retryable",
            )
        submitted = pending.model_copy(
            update={"provider_write_submitted_at_utc": attempted_at_utc}
        )
        manifest.remote_pairing_operations[submitted.operation_id] = submitted
        save_fulfillment_manifest(self.repo, manifest)
        try:
            remote_after = self.client.get_activity(external_activity_id, intervals=True)
        except Exception:
            return pairing_result(
                submitted,
                status="pairing_blocked",
                blocker_code="provider_pairing_readback_failed",
                message="Intervals pairing readback failed; the durable intent is retryable",
            )
        if (
            update_response.id != external_activity_id
            or remote_after.id != external_activity_id
            or update_response.paired_event_id != event_id
            or remote_after.paired_event_id != event_id
        ):
            return save_blocked_pair_operation(
                self.repo,
                manifest,
                submitted,
                blocker_code="provider_pairing_readback_mismatch",
                message="Intervals did not confirm the requested activity/event pair",
                attempted_at_utc=attempted_at_utc,
                provider_write_submitted_at_utc=attempted_at_utc,
            )
        if activity_pairing_guard_sha256(remote_after) != provider_activity_guard_sha256:
            return save_blocked_pair_operation(
                self.repo,
                manifest,
                submitted,
                blocker_code="provider_activity_changed_during_pairing",
                message="Intervals changed non-pairing activity fields during reconciliation",
                attempted_at_utc=attempted_at_utc,
                provider_write_submitted_at_utc=attempted_at_utc,
            )
        return save_verified_pair_operation(
            self.repo,
            manifest,
            submitted,
            fulfillment,
            provider_activity_guard_sha256=provider_activity_guard_sha256,
            verified_at_utc=attempted_at_utc,
            provenance="resilio_requested",
            status="paired",
        )

    def _resolve_pending_guard_drift(
        self,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
        *,
        observed_guard_sha256: str,
        requested_at_utc: datetime,
    ) -> tuple[RemoteWorkoutPairingOperation, RemoteWorkoutPairingResult | None]:
        if not pending_pair_guard_changed(
            operation,
            observed_guard_sha256=observed_guard_sha256,
        ):
            return operation, None
        resolution = matching_pairing_drift_resolution(
            manifest,
            operation,
            observed_guard_sha256=observed_guard_sha256,
        )
        if resolution is None:
            return operation, pairing_guard_blocker(
                operation,
                observed_guard_sha256=observed_guard_sha256,
            )
        return (
            restored_pair_operation(
                operation,
                resolution,
                requested_at_utc=requested_at_utc,
            ),
            None,
        )

    def _reconcile_exact_pair(
        self,
        *,
        manifest: WorkoutFulfillmentManifest,
        existing_operation: RemoteWorkoutPairingOperation | None,
        operation: RemoteWorkoutPairingOperation,
        fulfillment: WorkoutFulfillmentRecord,
        publication: PublishedWorkout,
        external_activity_id: str,
        provider_activity_guard_sha256: str,
        reconciliation_time_utc: datetime,
    ) -> RemoteWorkoutPairingResult:
        operation, guard_blocker = self._resolve_pending_guard_drift(
            manifest,
            operation,
            observed_guard_sha256=provider_activity_guard_sha256,
            requested_at_utc=reconciliation_time_utc,
        )
        if guard_blocker is not None:
            return guard_blocker
        if not operation_proves_resilio_pair_request(existing_operation):
            provider_pair = fulfillment.provider_pair
            if provider_pair is not None:
                if (
                    provider_pair.event_id != publication.event_id
                    or provider_pair.provenance != "provider_observed"
                ):
                    raise ValueError(
                        "Local provider-pair evidence conflicts with exact Intervals state"
                    )
                return RemoteWorkoutPairingResult(
                    local_activity_id=fulfillment.local_activity_id,
                    local_workout_id=fulfillment.workout_identity.local_workout_id,
                    intervals_icu_activity_id=external_activity_id,
                    event_id=publication.event_id,
                    status="pairing_noop",
                )
            return save_provider_observed_pair(
                self.repo,
                manifest,
                fulfillment,
                event_id=publication.event_id,
                observed_at_utc=reconciliation_time_utc,
                external_activity_id=external_activity_id,
            )
        if existing_operation is not None and existing_operation.state == "verified":
            provider_pair = fulfillment.provider_pair
            if (
                provider_pair is None
                or provider_pair.event_id != publication.event_id
                or provider_pair.provenance
                not in {"resilio_requested", "pair_origin_ambiguous"}
            ):
                raise ValueError(
                    "Local provider-pair evidence conflicts with its Resilio operation"
                )
            return pairing_result(existing_operation, status="pairing_noop")
        return save_verified_pair_operation(
            self.repo,
            manifest,
            operation,
            fulfillment,
            provider_activity_guard_sha256=provider_activity_guard_sha256,
            verified_at_utc=reconciliation_time_utc,
            provenance=provider_pair_provenance_for_operation(operation),
            status="pairing_noop",
        )

    def _reconcile_unpaired(
        self,
        *,
        manifest: WorkoutFulfillmentManifest,
        existing_operation: RemoteWorkoutPairingOperation | None,
        operation: RemoteWorkoutPairingOperation,
        fulfillment: WorkoutFulfillmentRecord,
        publication: PublishedWorkout,
        remote_before: ActivityDTO,
        reconciliation_time_utc: datetime,
    ) -> RemoteWorkoutPairingResult:
        provider_activity_guard_sha256 = activity_pairing_guard_sha256(remote_before)
        if existing_operation is not None and existing_operation.state == "verified":
            drift_token = remote_pairing_drift_token_sha256(
                existing_operation,
                provider_activity_guard_sha256=provider_activity_guard_sha256,
            )
            resolution = next(
                (
                    item
                    for item in manifest.remote_pairing_drift_resolutions
                    if item.pairing_drift_token_sha256 == drift_token
                    and item.pair_operation_snapshot == existing_operation
                    and item.observed_provider_activity_guard_sha256
                    == provider_activity_guard_sha256
                ),
                None,
            )
            if (
                fulfillment.provider_pair is not None
                and fulfillment.provider_pair.provenance != "resilio_requested"
                and resolution is None
            ):
                return pairing_result(
                    existing_operation,
                    status="pairing_blocked",
                    blocker_code="ambiguous_pair_removed",
                    message=(
                        "The removed ambiguous pair requires exact athlete confirmation"
                    ),
                    pairing_drift_token_sha256=drift_token,
                )
            if resolution is None:
                return pairing_result(
                    existing_operation,
                    status="pairing_blocked",
                    blocker_code="resilio_requested_pair_removed",
                    message="Intervals no longer reports the confirmed native pair",
                    pairing_drift_token_sha256=drift_token,
                )
            operation = restored_pair_operation(
                existing_operation,
                resolution,
                requested_at_utc=reconciliation_time_utc,
            )
        operation, guard_blocker = self._resolve_pending_guard_drift(
            manifest,
            operation,
            observed_guard_sha256=provider_activity_guard_sha256,
            requested_at_utc=reconciliation_time_utc,
        )
        if guard_blocker is not None:
            return guard_blocker
        if not activity_source_supports_pairing(remote_before):
            return save_blocked_pair_operation(
                self.repo,
                manifest,
                operation,
                blocker_code="activity_source_is_not_mutable",
                message="Intervals does not allow pairing updates for this activity source",
                attempted_at_utc=reconciliation_time_utc,
            )
        return self._perform_pairing_mutation(
            manifest=manifest,
            operation=operation,
            fulfillment=fulfillment,
            external_activity_id=operation.intervals_icu_activity_id,
            event_id=publication.event_id,
            provider_activity_guard_sha256=provider_activity_guard_sha256,
            attempted_at_utc=reconciliation_time_utc,
        )

    def reconcile_pairing(
        self,
        *,
        authority: AuthoritativeWorkout,
        publication: PublishedWorkout,
        fulfillment: WorkoutFulfillmentRecord,
        activity: CanonicalActivity,
        now_utc: datetime | None = None,
    ) -> RemoteWorkoutPairingResult:
        """Pair one exact activity, persisting intent before remote mutation."""
        reconciliation_time_utc = now_utc or datetime.now(timezone.utc)
        if reconciliation_time_utc < association_authorized_at_utc(fulfillment):
            raise ValueError("Native pairing cannot predate fulfillment authority")
        manifest = load_fulfillment_manifest(self.repo)
        if manifest.fulfillments.get(fulfillment.local_activity_id) != fulfillment:
            raise ValueError("Native pairing fulfillment changed before reconciliation")
        external_activity_id = validate_local_pairing_evidence(
            authority=authority,
            publication=publication,
            fulfillment=fulfillment,
            activity=activity,
            manifest=manifest,
        )
        if (
            activity_performance_evidence_sha256(activity)
            != fulfillment.activity_performance_evidence_sha256
        ):
            raise ValueError("Native pairing activity performance evidence changed")
        remote_before = self.client.get_activity(external_activity_id, intervals=True)
        if remote_before.id != external_activity_id:
            raise ValueError("Intervals activity readback identity changed")
        validate_remote_performance_evidence(remote_before, activity)
        existing_operation = matching_resilio_pair_operation(
            manifest,
            fulfillment=fulfillment,
            publication=publication,
        )
        operation = existing_operation or new_pair_operation(
            publication=publication,
            fulfillment=fulfillment,
            external_activity_id=external_activity_id,
            requested_at_utc=reconciliation_time_utc,
        )
        if remote_before.paired_event_id == publication.event_id:
            return self._reconcile_exact_pair(
                manifest=manifest,
                existing_operation=existing_operation,
                operation=operation,
                fulfillment=fulfillment,
                publication=publication,
                external_activity_id=external_activity_id,
                provider_activity_guard_sha256=(
                    activity_pairing_guard_sha256(remote_before)
                ),
                reconciliation_time_utc=reconciliation_time_utc,
            )
        if remote_before.paired_event_id is not None:
            if existing_operation is not None and existing_operation.state == "verified":
                return pairing_result(
                    existing_operation,
                    status="pairing_blocked",
                    blocker_code="activity_paired_to_different_event",
                    message="Intervals activity is already paired to a different event",
                )
            return save_blocked_pair_operation(
                self.repo,
                manifest,
                operation,
                blocker_code="activity_paired_to_different_event",
                message="Intervals activity is already paired to a different event",
                attempted_at_utc=reconciliation_time_utc,
            )
        return self._reconcile_unpaired(
            manifest=manifest,
            existing_operation=existing_operation,
            operation=operation,
            fulfillment=fulfillment,
            publication=publication,
            remote_before=remote_before,
            reconciliation_time_utc=reconciliation_time_utc,
        )
