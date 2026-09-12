"""Project and reconcile native activity/event pairing for one applied week."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.remote_pairing import (
    WorkoutPairingReconciliationService,
)
from resilio.core.workout_fulfillment.remote_pairing_inspection import (
    validate_remote_performance_evidence,
)
from resilio.core.workout_fulfillment.remote_unpairing import (
    WorkoutUnpairingReconciliationService,
    actionable_unpair_operations,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.authority_matching import (
    publication_record_matches_current_workout_authority,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import (
    PublicationSafetyError,
    assert_remote_external_ownership,
)
from resilio.core.workout_publication.remote_event_read import get_exact_event
from resilio.integrations.intervals_icu.activity_pairing import (
    activity_source_supports_pairing,
)
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsNotFoundError
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    PendingWorkoutPublication,
    PublishedWorkout,
    RunWeekSynchronizationReport,
    WeekSynchronizationItem,
)
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)
from resilio.schemas.workout_pairing import (
    RemoteWorkoutPairingOperation,
    RemoteWorkoutPairingResult,
    restored_pair_operation_id,
)

WorkoutIdentityKey = tuple[str, str, int, str]


def confirmed_pairing_drift_retry_tokens(
    repo: RepositoryIO,
    pairing_status: RunWeekSynchronizationReport,
    supplied_tokens: set[str],
) -> set[str]:
    """Select supplied tokens persisted for current operation lineages."""
    current_operation_ids = {
        item.remote_pairing_operation_id
        for item in pairing_status.items
        if item.remote_pairing_operation_id is not None
    }
    confirmed_tokens: set[str] = set()
    for resolution in load_fulfillment_manifest(repo).remote_pairing_drift_resolutions:
        token_sha256 = resolution.pairing_drift_token_sha256
        if token_sha256 not in supplied_tokens:
            continue
        lineage_operation_ids = {
            resolution.pair_operation_snapshot.operation_id,
            restored_pair_operation_id(token_sha256),
        }
        if lineage_operation_ids & current_operation_ids:
            confirmed_tokens.add(token_sha256)
    return confirmed_tokens


def _identity_key(identity: PlanWorkoutIdentity) -> WorkoutIdentityKey:
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def _fulfillments_by_identity(
    manifest: WorkoutFulfillmentManifest,
) -> dict[WorkoutIdentityKey, WorkoutFulfillmentRecord]:
    return {
        _identity_key(record.workout_identity): record for record in manifest.fulfillments.values()
    }


def _publication_matches_pairing_authority(
    publication: PublishedWorkout | PendingWorkoutPublication,
    workout: AuthoritativeWorkout,
    fulfillment: WorkoutFulfillmentRecord,
) -> bool:
    """Return whether publication and fulfillment share exact current authority."""
    return (
        publication_record_matches_current_workout_authority(publication, workout)
        and workout.identity == fulfillment.workout_identity
        and publication.workout_prescription_sha256 == fulfillment.workout_prescription_sha256
        and publication.occurrence_date == fulfillment.scheduled_local_date
        and publication.schedule_timezone == fulfillment.schedule_timezone
    )


def _inspect_pending_pairing(
    pairing_service: WorkoutPairingReconciliationService,
    pending: PendingWorkoutPublication,
    fulfillment: WorkoutFulfillmentRecord,
    activity: CanonicalActivity,
) -> RemoteWorkoutPairingResult | None:
    """Verify live native pairing before a pending event can be recovered."""
    provider_pair = fulfillment.provider_pair
    external_activity_id = activity.origin.intervals_icu_activity_id
    if external_activity_id is None:
        raise ValueError("Native pairing requires an Intervals.icu activity identity")
    remote = pairing_service.client.get_activity(
        external_activity_id,
        intervals=True,
    )
    validate_remote_performance_evidence(
        remote,
        activity,
        expected_external_activity_id=external_activity_id,
    )
    expected_event_id = provider_pair.event_id if provider_pair is not None else None
    if provider_pair is None and remote.paired_event_id is not None:
        provider_client = cast(IntervalsIcuClient, pairing_service.client)
        try:
            paired_event = get_exact_event(provider_client, remote.paired_event_id)
            assert_remote_external_ownership(
                paired_event,
                external_id=pending.external_id,
            )
        except (IntervalsNotFoundError, PublicationSafetyError):
            pass
        else:
            expected_event_id = paired_event.id
    if expected_event_id is not None and remote.paired_event_id == expected_event_id:
        return RemoteWorkoutPairingResult(
            local_activity_id=fulfillment.local_activity_id,
            local_workout_id=fulfillment.workout_identity.local_workout_id,
            intervals_icu_activity_id=external_activity_id,
            event_id=expected_event_id,
            status="pairing_noop",
        )
    if remote.paired_event_id is not None:
        return RemoteWorkoutPairingResult(
            local_activity_id=fulfillment.local_activity_id,
            local_workout_id=fulfillment.workout_identity.local_workout_id,
            intervals_icu_activity_id=external_activity_id,
            event_id=expected_event_id or remote.paired_event_id,
            status="pairing_blocked",
            blocker_code="activity_paired_to_different_event",
            message="Intervals activity is already paired to a different event",
        )
    if provider_pair is not None and fulfillment.athlete_confirmation is None:
        blocker_code = (
            "provider_observed_pair_missing"
            if provider_pair.provenance == "provider_observed"
            else "resilio_requested_pair_removed"
        )
        return RemoteWorkoutPairingResult(
            local_activity_id=fulfillment.local_activity_id,
            local_workout_id=fulfillment.workout_identity.local_workout_id,
            intervals_icu_activity_id=external_activity_id,
            event_id=provider_pair.event_id,
            status="pairing_blocked",
            blocker_code=blocker_code,
            message="Intervals no longer reports the provider-paired fulfillment",
        )
    if not activity_source_supports_pairing(remote):
        return _immutable_source_pairing_blocker(
            fulfillment,
            external_activity_id=external_activity_id,
        )
    return None


def _immutable_source_pairing_blocker(
    fulfillment: WorkoutFulfillmentRecord,
    *,
    external_activity_id: str,
) -> RemoteWorkoutPairingResult:
    """Describe a required native pair that Intervals cannot mutate."""
    return RemoteWorkoutPairingResult(
        local_activity_id=fulfillment.local_activity_id,
        local_workout_id=fulfillment.workout_identity.local_workout_id,
        intervals_icu_activity_id=external_activity_id,
        event_id=(
            fulfillment.provider_pair.event_id if fulfillment.provider_pair is not None else None
        ),
        status="pairing_blocked",
        blocker_code="activity_source_is_not_mutable",
        message="Intervals does not allow pairing updates for this activity source",
    )


def _inspect_unpublished_pairing(
    pairing_service: WorkoutPairingReconciliationService,
    fulfillment: WorkoutFulfillmentRecord,
    activity: CanonicalActivity,
) -> RemoteWorkoutPairingResult | None:
    """Block an unrelated native pair before the first publication attempt."""
    external_activity_id = activity.origin.intervals_icu_activity_id
    if external_activity_id is None:
        raise ValueError("Native pairing requires an Intervals.icu activity identity")
    remote = pairing_service.client.get_activity(external_activity_id, intervals=True)
    validate_remote_performance_evidence(
        remote,
        activity,
        expected_external_activity_id=external_activity_id,
    )
    if remote.paired_event_id is None:
        if not activity_source_supports_pairing(remote):
            return _immutable_source_pairing_blocker(
                fulfillment,
                external_activity_id=external_activity_id,
            )
        return None
    return RemoteWorkoutPairingResult(
        local_activity_id=fulfillment.local_activity_id,
        local_workout_id=fulfillment.workout_identity.local_workout_id,
        intervals_icu_activity_id=external_activity_id,
        event_id=remote.paired_event_id,
        status="pairing_blocked",
        blocker_code="activity_paired_to_different_event",
        message="Intervals activity is already paired to a different event",
    )


def _latest_unpair_operations(
    manifest: WorkoutFulfillmentManifest,
    *,
    workout_identity_keys: set[WorkoutIdentityKey],
) -> dict[str, RemoteWorkoutPairingOperation]:
    operations_by_workout_id: dict[str, RemoteWorkoutPairingOperation] = {}
    for operation in actionable_unpair_operations(manifest):
        identity = operation.workout_identity
        if _identity_key(identity) not in workout_identity_keys:
            continue
        previous = operations_by_workout_id.get(identity.local_workout_id)
        if previous is None or operation.requested_at_utc > previous.requested_at_utc:
            operations_by_workout_id[identity.local_workout_id] = operation
    return operations_by_workout_id


def _pair_fulfilled_workouts(
    *,
    repo: RepositoryIO,
    pairing_service: WorkoutPairingReconciliationService,
    workouts: Iterable[AuthoritativeWorkout],
    fulfillments_by_identity: dict[WorkoutIdentityKey, WorkoutFulfillmentRecord],
    excluded_local_workout_ids: set[str],
    mutate: bool,
) -> tuple[dict[str, RemoteWorkoutPairingResult], dict[str, str]]:
    publication_manifest = load_manifest(repo)
    activities_by_id = {
        activity.local_activity_id: activity
        for activity in ActivityArchive(repo.resolve_path("data/activities")).load_all()
    }
    results: dict[str, RemoteWorkoutPairingResult] = {}
    failures: dict[str, str] = {}
    for workout in workouts:
        local_workout_id = workout.identity.local_workout_id
        if local_workout_id in excluded_local_workout_ids:
            continue
        fulfillment = fulfillments_by_identity.get(_identity_key(workout.identity))
        if fulfillment is None:
            continue
        activity = activities_by_id.get(fulfillment.local_activity_id)
        if activity is None:
            failures[local_workout_id] = "Canonical fulfillment activity is unavailable"
            continue
        publication = publication_manifest.workouts.get(local_workout_id)
        if publication is None:
            pending = publication_manifest.pending.get(local_workout_id)
            if pending is None:
                try:
                    unpublished_result = _inspect_unpublished_pairing(
                        pairing_service,
                        fulfillment,
                        activity,
                    )
                except Exception as exc:
                    failures[local_workout_id] = str(exc)
                else:
                    if unpublished_result is not None:
                        results[local_workout_id] = unpublished_result
                continue
            if not _publication_matches_pairing_authority(pending, workout, fulfillment):
                continue
            try:
                pending_result = _inspect_pending_pairing(
                    pairing_service,
                    pending,
                    fulfillment,
                    activity,
                )
            except Exception as exc:
                failures[local_workout_id] = str(exc)
            else:
                if pending_result is not None:
                    results[local_workout_id] = pending_result
            continue
        if not mutate and not _publication_matches_pairing_authority(
            publication,
            workout,
            fulfillment,
        ):
            # Publication reconciliation must first converge and read back the
            # owned event before it can be used as native-pair authority.
            continue
        try:
            result = (
                pairing_service.reconcile_pairing(
                    authority=workout,
                    publication=publication,
                    fulfillment=fulfillment,
                    activity=activity,
                )
                if mutate
                else pairing_service.inspect_pairing(
                    authority=workout,
                    publication=publication,
                    fulfillment=fulfillment,
                    activity=activity,
                )
            )
        except Exception as exc:
            failures[local_workout_id] = str(exc)
        else:
            results[local_workout_id] = result
    return results, failures


def _reconcile_unpair_operations(
    *,
    service: WorkoutUnpairingReconciliationService,
    operations: dict[str, RemoteWorkoutPairingOperation],
    mutate: bool,
) -> tuple[dict[str, RemoteWorkoutPairingResult], dict[str, str]]:
    results: dict[str, RemoteWorkoutPairingResult] = {}
    failures: dict[str, str] = {}
    for local_workout_id, operation in operations.items():
        try:
            result = service.reconcile(operation) if mutate else service.inspect(operation)
        except Exception as exc:
            failures[local_workout_id] = str(exc)
        else:
            results[local_workout_id] = result
    return results, failures


def _project_item(
    item: WeekSynchronizationItem,
    *,
    pairing: RemoteWorkoutPairingResult | None,
    failure_message: str | None,
) -> WeekSynchronizationItem:
    if failure_message is not None:
        return item.model_copy(
            update={
                "remote_pairing_status": "pairing_blocked",
                "remote_pairing_blocker_code": "pairing_reconciliation_failed",
                "message": failure_message,
            }
        )
    if pairing is None:
        return item
    return item.model_copy(
        update={
            "local_activity_id": pairing.local_activity_id,
            "remote_pairing_status": pairing.status,
            "remote_pairing_operation_id": pairing.operation_id,
            "remote_pairing_blocker_code": pairing.blocker_code,
            "pairing_drift_token_sha256": pairing.pairing_drift_token_sha256,
            "message": pairing.message or item.message,
        }
    )


def attach_remote_pairing_status(
    *,
    repo: RepositoryIO,
    pairing_service: WorkoutPairingReconciliationService,
    unpairing_service: WorkoutUnpairingReconciliationService,
    report: RunWeekSynchronizationReport,
    workouts: list[AuthoritativeWorkout],
    mutate: bool,
) -> RunWeekSynchronizationReport:
    """Attach fail-closed native pair or unpair outcomes to one week report."""
    fulfillment_manifest = load_fulfillment_manifest(repo)
    unpairings, unpairing_failures = _reconcile_unpair_operations(
        service=unpairing_service,
        operations=_latest_unpair_operations(
            fulfillment_manifest,
            workout_identity_keys={_identity_key(workout.identity) for workout in workouts},
        ),
        mutate=mutate,
    )
    unfinished_unpair_workout_ids = {
        local_workout_id
        for local_workout_id, result in unpairings.items()
        if result.status != "unpaired"
    } | set(unpairing_failures)
    pairings, pairing_failures = _pair_fulfilled_workouts(
        repo=repo,
        pairing_service=pairing_service,
        workouts=workouts,
        fulfillments_by_identity=_fulfillments_by_identity(fulfillment_manifest),
        excluded_local_workout_ids=unfinished_unpair_workout_ids,
        mutate=mutate,
    )
    unpairings.update(pairings)
    pairings = unpairings
    unpairing_failures.update(pairing_failures)
    pairing_failures = unpairing_failures
    pairing_blocked = bool(pairing_failures) or any(
        result.status == "pairing_blocked" for result in pairings.values()
    )
    items = [
        _project_item(
            item,
            pairing=pairings.get(item.local_workout_id),
            failure_message=pairing_failures.get(item.local_workout_id),
        )
        for item in report.items
    ]
    return report.model_copy(
        update={
            "items": items,
            "partial": report.partial or pairing_blocked,
            "reconciliation_safe": report.reconciliation_safe and not pairing_blocked,
        }
    )
