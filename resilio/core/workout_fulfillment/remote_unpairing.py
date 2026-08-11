"""Crash-recoverable removal of athlete-revoked native activity/event pairs."""

from datetime import datetime, timezone
from typing import Protocol

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.pair_operation_evidence import (
    operation_proves_resilio_pair_request,
    unpair_operation_has_exact_authority,
    unpair_operation_id,
)
from resilio.core.workout_fulfillment.repository import (
    load_fulfillment_manifest,
    save_fulfillment_manifest,
)
from resilio.integrations.intervals_icu.activity_fingerprint import (
    performance_evidence_fingerprint,
)
from resilio.integrations.intervals_icu.activity_pairing import (
    activity_pairing_guard_sha256,
    activity_source_supports_pairing,
)
from resilio.integrations.intervals_icu.dto import ActivityDTO, ActivityPairingWriteDTO
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.publication import PublishedWorkout
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRevocation,
)
from resilio.schemas.workout_pairing import (
    RemotePairingOperationsReport,
    RemotePairingStatus,
    RemoteWorkoutPairingOperation,
    RemoteWorkoutPairingResult,
)


class ActivityUnpairingClient(Protocol):
    def get_activity(self, activity_id: str, *, intervals: bool = True) -> ActivityDTO: ...

    def update_activity_pairing(
        self,
        activity_id: str,
        pairing: ActivityPairingWriteDTO,
    ) -> ActivityDTO: ...


def actionable_unpair_operations(
    manifest: WorkoutFulfillmentManifest,
) -> list[RemoteWorkoutPairingOperation]:
    """Select latest nonterminal unpair obligations not superseded by new authority."""
    latest_by_association: dict[
        tuple[str, str, str, int, str], RemoteWorkoutPairingOperation
    ] = {}
    for operation in manifest.remote_pairing_operations.values():
        if operation.action != "unpair":
            continue
        identity = operation.workout_identity
        key = (
            operation.local_activity_id,
            identity.plan_id,
            identity.plan_revision_id,
            identity.week_number,
            identity.local_workout_id,
        )
        previous = latest_by_association.get(key)
        if previous is None or operation.requested_at_utc > previous.requested_at_utc:
            latest_by_association[key] = operation
    actionable: list[RemoteWorkoutPairingOperation] = []
    for operation in latest_by_association.values():
        active_fulfillment = manifest.fulfillments.get(operation.local_activity_id)
        explicitly_reauthorized = (
            active_fulfillment is not None
            and active_fulfillment.workout_identity == operation.workout_identity
            and active_fulfillment.athlete_confirmation is not None
            and active_fulfillment.athlete_confirmation.confirmed_at_utc
            > operation.requested_at_utc
        )
        if operation.state != "verified" and not explicitly_reauthorized:
            actionable.append(operation)
    return sorted(actionable, key=lambda operation: operation.requested_at_utc)


def stage_remote_unpairing(
    *,
    manifest: WorkoutFulfillmentManifest,
    publication: PublishedWorkout,
    revocation: WorkoutFulfillmentRevocation,
    activity: CanonicalActivity,
    pair_operation: RemoteWorkoutPairingOperation | None = None,
) -> RemoteWorkoutPairingOperation:
    """Add one exact unpair intent to a manifest before it is persisted."""
    fulfillment = revocation.fulfillment
    operation_proves_pair_request = pair_operation is not None and (
        pair_operation.action == "pair"
        and pair_operation.local_activity_id == fulfillment.local_activity_id
        and pair_operation.workout_identity == fulfillment.workout_identity
        and pair_operation.event_id == publication.event_id
        and operation_proves_resilio_pair_request(pair_operation)
    )
    if publication.workout_identity != fulfillment.workout_identity or not (
        fulfillment.provider_pair_supports_event(publication.event_id)
        or operation_proves_pair_request
    ):
        raise ValueError("Revoked fulfillment does not match the published native pair")
    external_activity_id = activity.origin.intervals_icu_activity_id
    if (
        external_activity_id is None
        or external_activity_id != revocation.intervals_icu_activity_id
    ):
        raise ValueError("Native unpairing requires an Intervals.icu activity identity")
    fulfillment_sha256 = canonical_data_sha256(fulfillment)
    operation = RemoteWorkoutPairingOperation(
        operation_id=unpair_operation_id(revocation, event_id=publication.event_id),
        action="unpair",
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
        fulfillment_record_sha256=fulfillment_sha256,
        revocation_id=revocation.revocation_id,
        expected_paired_event_id_before=publication.event_id,
        requested_at_utc=revocation.revoked_at_utc,
    )
    manifest.remote_pairing_operations[operation.operation_id] = operation
    return operation


class WorkoutUnpairingReconciliationService:
    """Reconcile exact native pairs withdrawn through fulfillment revocation."""

    def __init__(self, repo: RepositoryIO, client: ActivityUnpairingClient):
        self.repo = repo
        self.client = client

    @staticmethod
    def _result(
        operation: RemoteWorkoutPairingOperation,
        *,
        status: RemotePairingStatus,
        blocker_code: str | None = None,
        message: str | None = None,
    ) -> RemoteWorkoutPairingResult:
        return RemoteWorkoutPairingResult(
            local_activity_id=operation.local_activity_id,
            local_workout_id=operation.workout_identity.local_workout_id,
            intervals_icu_activity_id=operation.intervals_icu_activity_id,
            event_id=operation.event_id,
            status=status,
            operation_id=operation.operation_id,
            blocker_code=blocker_code,
            message=message,
        )

    def _save_operation(
        self,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
    ) -> None:
        manifest.remote_pairing_operations[operation.operation_id] = operation
        save_fulfillment_manifest(self.repo, manifest)

    @staticmethod
    def _absent_activity_guard_sha256(
        operation: RemoteWorkoutPairingOperation,
    ) -> str:
        return canonical_data_sha256(
            {
                "intervals_icu_activity_id": operation.intervals_icu_activity_id,
                "provider_state": "activity_not_found",
            }
        )

    def _assert_revocation_authority(
        self,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
    ) -> CanonicalActivity:
        revocation = next(
            (
                item
                for item in manifest.revoked_fulfillments
                if item.revocation_id == operation.revocation_id
            ),
            None,
        )
        if revocation is None:
            raise ValueError("Native unpair operation lacks athlete revocation authority")
        fulfillment = revocation.fulfillment
        activity = ActivityArchive(self.repo.resolve_path("data/activities")).load(
            fulfillment.local_activity_id
        )
        if (
            activity is None
            or activity.origin.intervals_icu_activity_id
            != operation.intervals_icu_activity_id
            or activity_performance_evidence_sha256(activity)
            != fulfillment.activity_performance_evidence_sha256
            or operation.local_activity_id != fulfillment.local_activity_id
            or operation.intervals_icu_activity_id
            != revocation.intervals_icu_activity_id
            or operation.workout_identity != fulfillment.workout_identity
            or operation.activity_performance_evidence_sha256
            != fulfillment.activity_performance_evidence_sha256
            or operation.fulfillment_record_sha256
            != canonical_data_sha256(fulfillment)
            or operation.requested_at_utc != revocation.revoked_at_utc
            or not unpair_operation_has_exact_authority(
                manifest,
                operation=operation,
                revocation=revocation,
            )
        ):
            raise ValueError("Native unpair operation changed from its exact revocation")
        return activity

    @staticmethod
    def _assert_remote_performance_is_current(
        remote: ActivityDTO,
        activity: CanonicalActivity,
    ) -> None:
        expected_sha256 = activity.audit.performance_evidence_sha256
        observed_sha256 = performance_evidence_fingerprint(
            remote,
            activity.occurrence.timezone,
        )
        if expected_sha256 is None or observed_sha256 != expected_sha256:
            raise ValueError(
                "Intervals activity performance changed after canonical synchronization"
            )

    def _blocked(
        self,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
        *,
        code: str,
        message: str,
        attempted_at_utc: datetime,
    ) -> RemoteWorkoutPairingResult:
        blocked = operation.model_copy(
            update={
                "state": "blocked",
                "last_attempted_at_utc": attempted_at_utc,
                "verified_at_utc": None,
                "provider_activity_guard_sha256": None,
                "blocker_code": code,
                "blocker_message": message,
            }
        )
        self._save_operation(manifest, blocked)
        return self._result(
            blocked,
            status="pairing_blocked",
            blocker_code=code,
            message=message,
        )

    def _verified(
        self,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
        *,
        guard_sha256: str,
        verified_at_utc: datetime,
    ) -> RemoteWorkoutPairingResult:
        verified = operation.model_copy(
            update={
                "state": "verified",
                "expected_provider_activity_guard_sha256_before": (
                    operation.expected_provider_activity_guard_sha256_before
                    or guard_sha256
                ),
                "last_attempted_at_utc": verified_at_utc,
                "verified_at_utc": verified_at_utc,
                "provider_activity_guard_sha256": guard_sha256,
                "blocker_code": None,
                "blocker_message": None,
            }
        )
        self._save_operation(manifest, verified)
        return self._result(verified, status="unpaired")

    @staticmethod
    def _provider_guard_changed(
        operation: RemoteWorkoutPairingOperation,
        remote: ActivityDTO,
    ) -> bool:
        expected_guard_sha256 = operation.expected_provider_activity_guard_sha256_before
        return (
            expected_guard_sha256 is not None
            and expected_guard_sha256 != activity_pairing_guard_sha256(remote)
        )

    def inspect(self, operation: RemoteWorkoutPairingOperation) -> RemoteWorkoutPairingResult:
        """Project an exact unpair operation without changing any state."""
        if operation.action != "unpair":
            raise ValueError("Unpair inspection requires an unpair operation")
        manifest = load_fulfillment_manifest(self.repo)
        if manifest.remote_pairing_operations.get(operation.operation_id) != operation:
            raise ValueError("Native unpair operation changed before inspection")
        activity = self._assert_revocation_authority(manifest, operation)
        try:
            remote = self.client.get_activity(
                operation.intervals_icu_activity_id,
                intervals=False,
            )
        except IntervalsNotFoundError:
            return self._result(operation, status="unpaired")
        if remote.id != operation.intervals_icu_activity_id:
            raise ValueError("Intervals unpair inspection returned a different activity")
        self._assert_remote_performance_is_current(remote, activity)
        if remote.paired_event_id is None:
            return self._result(operation, status="unpaired")
        if remote.paired_event_id != operation.event_id:
            return self._result(operation, status="unpaired")
        if not activity_source_supports_pairing(remote):
            return self._result(
                operation,
                status="pairing_blocked",
                blocker_code="activity_source_is_not_mutable",
                message="Intervals does not allow pairing updates for this activity source",
            )
        return self._result(operation, status="ready_to_unpair")

    def _perform_unpairing_mutation(
        self,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
        *,
        provider_activity_guard_sha256: str,
        reconciliation_time_utc: datetime,
    ) -> RemoteWorkoutPairingResult:
        pending = operation.model_copy(
            update={
                "state": "pending",
                "expected_provider_activity_guard_sha256_before": (
                    operation.expected_provider_activity_guard_sha256_before
                    or provider_activity_guard_sha256
                ),
                "last_attempted_at_utc": reconciliation_time_utc,
                "verified_at_utc": None,
                "provider_activity_guard_sha256": None,
                "blocker_code": None,
                "blocker_message": None,
            }
        )
        self._save_operation(manifest, pending)
        try:
            update_response = self.client.update_activity_pairing(
                operation.intervals_icu_activity_id,
                ActivityPairingWriteDTO(paired_event_id=None),
            )
        except IntervalsNotFoundError:
            return self._verified(
                manifest,
                pending,
                guard_sha256=self._absent_activity_guard_sha256(operation),
                verified_at_utc=reconciliation_time_utc,
            )
        except Exception:
            return self._result(
                pending,
                status="pairing_blocked",
                blocker_code="provider_unpairing_request_failed",
                message="Intervals unpairing request failed; the durable intent is retryable",
            )
        submitted = pending.model_copy(
            update={"provider_write_submitted_at_utc": reconciliation_time_utc}
        )
        self._save_operation(manifest, submitted)
        return self._verify_unpairing_readback(
            manifest,
            submitted,
            update_response=update_response,
            provider_activity_guard_sha256=provider_activity_guard_sha256,
            reconciliation_time_utc=reconciliation_time_utc,
        )

    def _verify_unpairing_readback(
        self,
        manifest: WorkoutFulfillmentManifest,
        operation: RemoteWorkoutPairingOperation,
        *,
        update_response: ActivityDTO,
        provider_activity_guard_sha256: str,
        reconciliation_time_utc: datetime,
    ) -> RemoteWorkoutPairingResult:
        try:
            remote_after = self.client.get_activity(
                operation.intervals_icu_activity_id,
                intervals=False,
            )
        except IntervalsNotFoundError:
            return self._verified(
                manifest,
                operation,
                guard_sha256=self._absent_activity_guard_sha256(operation),
                verified_at_utc=reconciliation_time_utc,
            )
        except Exception:
            return self._result(
                operation,
                status="pairing_blocked",
                blocker_code="provider_unpairing_readback_failed",
                message="Intervals unpairing readback failed; the durable intent is retryable",
            )
        if (
            update_response.id != operation.intervals_icu_activity_id
            or remote_after.id != operation.intervals_icu_activity_id
            or update_response.paired_event_id is not None
            or remote_after.paired_event_id is not None
        ):
            return self._blocked(
                manifest,
                operation,
                code="provider_unpairing_readback_mismatch",
                message="Intervals did not confirm removal of the exact native pair",
                attempted_at_utc=reconciliation_time_utc,
            )
        if (
            activity_pairing_guard_sha256(update_response)
            != provider_activity_guard_sha256
            or activity_pairing_guard_sha256(remote_after)
            != provider_activity_guard_sha256
        ):
            return self._blocked(
                manifest,
                operation,
                code="provider_activity_changed_during_unpairing",
                message="Intervals changed non-pairing fields during unpair reconciliation",
                attempted_at_utc=reconciliation_time_utc,
            )
        return self._verified(
            manifest,
            operation,
            guard_sha256=provider_activity_guard_sha256,
            verified_at_utc=reconciliation_time_utc,
        )

    def reconcile(
        self,
        operation: RemoteWorkoutPairingOperation,
        *,
        now_utc: datetime | None = None,
    ) -> RemoteWorkoutPairingResult:
        """Clear only the exact pair withdrawn by an athlete revocation."""
        reconciliation_time_utc = now_utc or datetime.now(timezone.utc)
        manifest = load_fulfillment_manifest(self.repo)
        if manifest.remote_pairing_operations.get(operation.operation_id) != operation:
            raise ValueError("Native unpair operation changed before reconciliation")
        activity = self._assert_revocation_authority(manifest, operation)
        try:
            remote_before = self.client.get_activity(
                operation.intervals_icu_activity_id,
                intervals=False,
            )
        except IntervalsNotFoundError:
            return self._verified(
                manifest,
                operation,
                guard_sha256=self._absent_activity_guard_sha256(operation),
                verified_at_utc=reconciliation_time_utc,
            )
        if remote_before.id != operation.intervals_icu_activity_id:
            raise ValueError("Intervals unpair readback returned a different activity")
        self._assert_remote_performance_is_current(remote_before, activity)
        guard_sha256 = activity_pairing_guard_sha256(remote_before)
        if remote_before.paired_event_id is None:
            return self._verified(
                manifest,
                operation,
                guard_sha256=guard_sha256,
                verified_at_utc=reconciliation_time_utc,
            )
        if remote_before.paired_event_id != operation.event_id:
            return self._verified(
                manifest,
                operation,
                guard_sha256=guard_sha256,
                verified_at_utc=reconciliation_time_utc,
            )
        if self._provider_guard_changed(operation, remote_before):
            operation = operation.model_copy(
                update={
                    "expected_provider_activity_guard_sha256_before": guard_sha256,
                    "blocker_code": None,
                    "blocker_message": None,
                }
            )
        if not activity_source_supports_pairing(remote_before):
            return self._blocked(
                manifest,
                operation,
                code="activity_source_is_not_mutable",
                message="Intervals does not allow pairing updates for this activity source",
                attempted_at_utc=reconciliation_time_utc,
            )
        return self._perform_unpairing_mutation(
            manifest,
            operation,
            provider_activity_guard_sha256=guard_sha256,
            reconciliation_time_utc=reconciliation_time_utc,
        )


def reconcile_actionable_unpair_operations(
    repo: RepositoryIO,
    client: ActivityUnpairingClient,
) -> RemotePairingOperationsReport:
    """Drain exact unpair obligations independently of active-plan authority."""
    manifest = load_fulfillment_manifest(repo)
    service = WorkoutUnpairingReconciliationService(repo, client)
    results: list[RemoteWorkoutPairingResult] = []
    for operation in actionable_unpair_operations(manifest):
        try:
            result = service.reconcile(operation)
        except Exception as exc:
            result = RemoteWorkoutPairingResult(
                local_activity_id=operation.local_activity_id,
                local_workout_id=operation.workout_identity.local_workout_id,
                intervals_icu_activity_id=operation.intervals_icu_activity_id,
                event_id=operation.event_id,
                status="pairing_blocked",
                operation_id=operation.operation_id,
                blocker_code="unpair_reconciliation_failed",
                message=str(exc),
            )
        results.append(result)
    return RemotePairingOperationsReport(
        results=results,
        partial=any(result.status == "pairing_blocked" for result in results),
    )
