"""Athlete authority for restoring one removed Resilio-authored native pair."""

from datetime import datetime, timezone
from typing import Protocol

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.pair_operation_evidence import (
    operation_proves_resilio_pair_request,
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
)
from resilio.integrations.intervals_icu.dto import ActivityDTO
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest
from resilio.schemas.workout_pairing import (
    RemotePairingDriftResolution,
    remote_pairing_drift_token_sha256,
)


class ActivityPairingInspectionClient(Protocol):
    def get_activity(self, activity_id: str, *, intervals: bool = True) -> ActivityDTO: ...


def confirm_remote_pairing_drift(
    repo: RepositoryIO,
    client: ActivityPairingInspectionClient,
    *,
    operation_id: str,
    supplied_pairing_drift_token_sha256: str,
    athlete_confirmation_reference: str,
    confirmed_at_utc: datetime | None = None,
) -> RemotePairingDriftResolution:
    """Persist authority for one exact removed pair or changed mutation guard."""
    return confirm_remote_pairing_drifts(
        repo,
        client,
        confirmations=[
            (
                operation_id,
                supplied_pairing_drift_token_sha256,
                athlete_confirmation_reference,
            )
        ],
        confirmed_at_utc=confirmed_at_utc,
    )[0]


def _prepare_pairing_drift_resolution(
    repo: RepositoryIO,
    client: ActivityPairingInspectionClient,
    manifest: WorkoutFulfillmentManifest,
    *,
    operation_id: str,
    supplied_pairing_drift_token_sha256: str,
    athlete_confirmation_reference: str,
    confirmation_time_utc: datetime,
) -> tuple[RemotePairingDriftResolution, bool]:
    confirmation = athlete_confirmation_reference.strip()
    if not confirmation:
        raise ValueError("Pairing drift resolution requires athlete confirmation")
    operation = manifest.remote_pairing_operations.get(operation_id)
    if (
        operation is None
        or operation.action != "pair"
        or not operation_proves_resilio_pair_request(operation)
    ):
        raise ValueError("Pairing drift resolution lacks an exact pair operation")
    remote = client.get_activity(operation.intervals_icu_activity_id, intervals=False)
    if operation.state == "verified":
        if remote.paired_event_id is not None:
            raise ValueError("Verified pairing drift may restore only a removed pair")
    elif remote.paired_event_id not in {None, operation.event_id}:
        raise ValueError("Pairing guard drift conflicts with another provider event")
    activity = ActivityArchive(repo.resolve_path("data/activities")).load(
        operation.local_activity_id
    )
    if (
        activity is None
        or activity.origin.intervals_icu_activity_id
        != operation.intervals_icu_activity_id
        or activity.audit.performance_evidence_sha256 is None
        or performance_evidence_fingerprint(remote, activity.occurrence.timezone)
        != activity.audit.performance_evidence_sha256
    ):
        raise ValueError("Pairing drift activity evidence changed after synchronization")
    provider_activity_guard_sha256 = activity_pairing_guard_sha256(remote)
    expected_token = remote_pairing_drift_token_sha256(
        operation,
        provider_activity_guard_sha256=provider_activity_guard_sha256,
    )
    if supplied_pairing_drift_token_sha256 != expected_token:
        raise ValueError("Pairing drift token is stale or does not match")
    authority_time_utc = operation.verified_at_utc or operation.requested_at_utc
    if confirmation_time_utc < authority_time_utc:
        raise ValueError("Pairing drift confirmation cannot predate its operation")
    existing = next(
        (
            resolution
            for resolution in manifest.remote_pairing_drift_resolutions
            if resolution.pairing_drift_token_sha256 == expected_token
        ),
        None,
    )
    if existing is not None:
        if existing.athlete_confirmation_reference != confirmation:
            raise ValueError("Pairing drift confirmation conflicts with prior authority")
        return existing, False
    resolution = RemotePairingDriftResolution(
        pairing_drift_token_sha256=expected_token,
        pair_operation_snapshot=operation,
        observed_provider_activity_guard_sha256=provider_activity_guard_sha256,
        athlete_confirmation_reference=confirmation,
        confirmed_at_utc=confirmation_time_utc,
    )
    return resolution, True


def confirm_remote_pairing_drifts(
    repo: RepositoryIO,
    client: ActivityPairingInspectionClient,
    *,
    confirmations: list[tuple[str, str, str]],
    confirmed_at_utc: datetime | None = None,
) -> list[RemotePairingDriftResolution]:
    """Validate an exact drift set, then persist every resolution atomically."""
    if not confirmations:
        raise ValueError("Pairing drift resolution set cannot be empty")
    confirmation_time_utc = confirmed_at_utc or datetime.now(timezone.utc)
    manifest = load_fulfillment_manifest(repo)
    resolutions: list[RemotePairingDriftResolution] = []
    changed = False
    for operation_id, token_sha256, confirmation_reference in confirmations:
        resolution, item_changed = _prepare_pairing_drift_resolution(
            repo,
            client,
            manifest,
            operation_id=operation_id,
            supplied_pairing_drift_token_sha256=token_sha256,
            athlete_confirmation_reference=confirmation_reference,
            confirmation_time_utc=confirmation_time_utc,
        )
        if item_changed:
            manifest.remote_pairing_drift_resolutions.append(resolution)
        resolutions.append(resolution)
        changed = changed or item_changed
    if changed:
        save_fulfillment_manifest(repo, manifest)
    return resolutions
