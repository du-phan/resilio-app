"""Stable identity for one accepted workout-to-activity association."""

from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.workout_fulfillment.legacy_fulfillment_contracts import (
    legacy_v1_fulfillment_sha256,
)
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRecord


def fulfillment_association_sha256(
    fulfillment: WorkoutFulfillmentRecord,
) -> str:
    """Hash immutable association lineage across provider evidence corrections."""
    first_revision = (
        fulfillment.activity_evidence_revisions[0]
        if fulfillment.activity_evidence_revisions
        else None
    )
    return canonical_data_sha256(
        {
            "local_activity_id": fulfillment.local_activity_id,
            "workout_identity": fulfillment.workout_identity.model_dump(mode="json"),
            "applied_week_approval_id": fulfillment.applied_week_approval_id,
            "applied_running_workouts_sha256": (fulfillment.applied_running_workouts_sha256),
            "workout_prescription_sha256": (fulfillment.workout_prescription_sha256),
            "schedule_timezone": fulfillment.schedule_timezone,
            "scheduled_local_date": fulfillment.scheduled_local_date.isoformat(),
            "original_activity_performance_evidence_sha256": (
                first_revision.previous_activity_performance_evidence_sha256
                if first_revision is not None
                else fulfillment.activity_performance_evidence_sha256
            ),
            "original_execution_local_date": (
                first_revision.previous_execution_local_date
                if first_revision is not None
                else fulfillment.execution_local_date
            ).isoformat(),
            "recorded_at_utc": fulfillment.recorded_at_utc.isoformat(),
        }
    )


def fulfillment_record_sha256_lineage(
    fulfillment: WorkoutFulfillmentRecord,
) -> set[str]:
    """Hash every record snapshot proven by the activity-revision chain."""
    snapshots = [fulfillment]
    revisions = fulfillment.activity_evidence_revisions
    for revision_index in range(len(revisions) - 1, -1, -1):
        revision = revisions[revision_index]
        snapshots.append(
            fulfillment.model_copy(
                update={
                    "activity_performance_evidence_sha256": (
                        revision.previous_activity_performance_evidence_sha256
                    ),
                    "execution_local_date": revision.previous_execution_local_date,
                    "schedule_offset_days": (
                        revision.previous_execution_local_date - fulfillment.scheduled_local_date
                    ).days,
                    "activity_evidence_revisions": revisions[:revision_index],
                }
            )
        )
    return {
        digest
        for snapshot in snapshots
        for digest in (
            canonical_data_sha256(snapshot),
            legacy_v1_fulfillment_sha256(snapshot),
        )
    }
