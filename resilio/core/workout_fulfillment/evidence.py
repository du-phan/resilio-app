"""Freshness checks for immutable fulfillment evidence."""

from datetime import date
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.adherence_evidence import (
    AppliedWorkoutAuthority,
    AuthoritativeWorkout,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.schemas.activity import ActivityStatus, CanonicalActivity, is_running_sport
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)


def fulfillment_was_available_as_of(
    fulfillment: WorkoutFulfillmentRecord,
    *,
    as_of_date: date,
) -> bool:
    """Whether execution and recorded evidence both existed by athlete-local date."""
    recorded_local_date = fulfillment.recorded_at_utc.astimezone(
        ZoneInfo(fulfillment.schedule_timezone)
    ).date()
    return fulfillment.execution_local_date <= as_of_date and recorded_local_date <= as_of_date


def _current_authority_snapshot(
    authority: AuthoritativeWorkout,
) -> AppliedWorkoutAuthority:
    return AppliedWorkoutAuthority(
        applied_week_approval_id=authority.applied_week_approval_id,
        applied_running_workouts_sha256=authority.applied_running_workouts_sha256,
        workout_prescription_sha256=canonical_data_sha256(authority.prescription),
        schedule_timezone=authority.schedule_timezone,
        scheduled_local_date=authority.prescription.date,
    )


def assert_fulfillment_authority_is_current(
    fulfillment: WorkoutFulfillmentRecord,
    authority: AuthoritativeWorkout,
) -> None:
    """Prove original authority and unchanged current workout semantics."""
    current = _current_authority_snapshot(authority)
    if (
        fulfillment.workout_identity != authority.identity
        or fulfillment.workout_prescription_sha256 != current.workout_prescription_sha256
        or fulfillment.schedule_timezone != authority.schedule_timezone
        or fulfillment.scheduled_local_date != authority.prescription.date
    ):
        raise ValueError("Workout fulfillment authority does not match applied workout")
    authority_history = authority.applied_authority_history or (current,)
    if not any(
        fulfillment.applied_week_approval_id == historical.applied_week_approval_id
        and fulfillment.applied_running_workouts_sha256
        == historical.applied_running_workouts_sha256
        and fulfillment.workout_prescription_sha256 == historical.workout_prescription_sha256
        and fulfillment.schedule_timezone == historical.schedule_timezone
        and fulfillment.scheduled_local_date == historical.scheduled_local_date
        for historical in authority_history
    ):
        raise ValueError("Workout fulfillment has no retained applied-week authority")


def assert_fulfillment_activity_is_current(
    fulfillment: WorkoutFulfillmentRecord,
    activity: CanonicalActivity,
) -> None:
    """Require the exact active activity bytes bound by the fulfillment record."""
    if activity.local_activity_id != fulfillment.local_activity_id:
        raise ValueError("Fulfillment activity identity does not match canonical activity")
    if activity.status != ActivityStatus.ACTIVE:
        raise ValueError("Fulfillment activity is not active")
    if not is_running_sport(activity.sport):
        raise ValueError("Fulfillment activity is not a running activity")
    if (
        activity_performance_evidence_sha256(activity)
        != fulfillment.activity_performance_evidence_sha256
    ):
        raise ValueError("Fulfillment activity performance evidence changed")


def assert_fulfillment_is_usable(
    fulfillment: WorkoutFulfillmentRecord,
    activity: CanonicalActivity,
    manifest: WorkoutFulfillmentManifest,
) -> None:
    """Require current activity bytes with no unresolved provider contradiction."""
    assert_fulfillment_activity_is_current(fulfillment, activity)
    if fulfillment.local_activity_id in manifest.unresolved_fulfillment_conflicts:
        raise ValueError("Workout fulfillment has an unresolved synchronized conflict")
