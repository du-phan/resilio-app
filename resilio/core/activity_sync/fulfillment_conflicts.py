"""Quarantine and durable-state helpers for workout pairing conflicts."""

import hashlib
from datetime import datetime
from typing import Any

from resilio.core.activity_sync.provider_fulfillment import (
    ProviderFulfillmentReconciliation,
)
from resilio.schemas.sync import SyncReport
from resilio.schemas.workout_fulfillment import (
    UnresolvedFulfillmentConflict,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)


def record_fulfillment_conflict(
    *,
    report: SyncReport,
    decisions: list[dict[str, Any]],
    external_activity_id_sha256: str,
    conflict: dict[str, str],
) -> None:
    report.quarantined_rows += 1
    report.partial = True
    decisions.append(
        {
            "action": "quarantine",
            "external_activity_id_sha256": external_activity_id_sha256,
            **conflict,
        }
    )


def persist_unresolved_fulfillment_conflict(
    manifest: WorkoutFulfillmentManifest,
    *,
    local_activity_id: str,
    conflict_rule: str,
    paired_event_id: int | None,
    observed_at_utc: datetime,
) -> None:
    if not conflict_rule.startswith(("paired_event_", "fulfilled_activity_")):
        return
    manifest.unresolved_fulfillment_conflicts[local_activity_id] = UnresolvedFulfillmentConflict(
        local_activity_id=local_activity_id,
        rule=conflict_rule,
        provider_event_id_sha256=(
            hashlib.sha256(str(paired_event_id).encode()).hexdigest()
            if paired_event_id is not None
            else None
        ),
        observed_at_utc=observed_at_utc,
    )


def apply_provider_fulfillment_reconciliation(
    *,
    manifest: WorkoutFulfillmentManifest,
    report: SyncReport,
    decisions: list[dict[str, Any]],
    local_activity_id: str,
    external_activity_id_sha256: str,
    paired_event_id: int | None,
    existing_fulfillment: WorkoutFulfillmentRecord | None,
    reconciliation: ProviderFulfillmentReconciliation,
    observed_at_utc: datetime,
) -> None:
    """Persist one pure pairing result without violating workout uniqueness."""
    if reconciliation.conflict is not None:
        persist_unresolved_fulfillment_conflict(
            manifest,
            local_activity_id=local_activity_id,
            conflict_rule=reconciliation.conflict.get("rule", ""),
            paired_event_id=paired_event_id,
            observed_at_utc=observed_at_utc,
        )
        record_fulfillment_conflict(
            report=report,
            decisions=decisions,
            external_activity_id_sha256=external_activity_id_sha256,
            conflict=reconciliation.conflict,
        )
        return
    manifest.unresolved_fulfillment_conflicts.pop(local_activity_id, None)
    fulfillment = reconciliation.fulfillment
    if fulfillment is None:
        return
    conflicting_owner = next(
        (
            owner_activity_id
            for owner_activity_id, record in manifest.fulfillments.items()
            if owner_activity_id != local_activity_id
            and record.workout_identity == fulfillment.workout_identity
        ),
        None,
    )
    if conflicting_owner is not None:
        persist_unresolved_fulfillment_conflict(
            manifest,
            local_activity_id=local_activity_id,
            conflict_rule="paired_event_workout_already_fulfilled",
            paired_event_id=paired_event_id,
            observed_at_utc=observed_at_utc,
        )
        record_fulfillment_conflict(
            report=report,
            decisions=decisions,
            external_activity_id_sha256=external_activity_id_sha256,
            conflict={
                "rule": "paired_event_workout_already_fulfilled",
                "local_activity_id": local_activity_id,
                "local_workout_id": fulfillment.workout_identity.local_workout_id,
            },
        )
        return
    manifest.fulfillments[local_activity_id] = fulfillment
    if existing_fulfillment is None:
        report.workout_fulfillments_linked += 1
        return
    added_revision_count = len(fulfillment.activity_evidence_revisions) - len(
        existing_fulfillment.activity_evidence_revisions
    )
    report.workout_fulfillment_evidence_revisions += max(added_revision_count, 0)
    if existing_fulfillment.provider_pair is not None and fulfillment.provider_pair is None:
        report.workout_provider_pairs_withdrawn += 1
