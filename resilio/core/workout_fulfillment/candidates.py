"""Factual candidate construction without inferred workout matching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.schemas.activity import ActivityStatus, CanonicalActivity, is_running_sport
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.planning.workouts import RunningWorkoutPrescription, WorkoutType
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentCandidate,
    WorkoutFulfillmentManifest,
)


@dataclass(frozen=True)
class FulfillmentWorkoutAuthority:
    identity: PlanWorkoutIdentity
    prescription: RunningWorkoutPrescription
    applied_week_approval_id: str
    applied_running_workouts_sha256: str
    schedule_timezone: str


def _execution_local_date(
    activity: CanonicalActivity,
    *,
    schedule_timezone: str,
) -> date | None:
    if activity.occurrence.start_time_utc is not None:
        return activity.occurrence.start_time_utc.astimezone(ZoneInfo(schedule_timezone)).date()
    if activity.occurrence.timezone == schedule_timezone:
        return activity.occurrence.local_date
    return None


def _same_training_week(left: date, right: date) -> bool:
    return left.toordinal() - left.weekday() == right.toordinal() - right.weekday()


def _timing(schedule_offset_days: int) -> str:
    if schedule_offset_days < 0:
        return "early"
    if schedule_offset_days > 0:
        return "late"
    return "on_schedule"


def _candidate_payload(
    *,
    activity: CanonicalActivity,
    authority: FulfillmentWorkoutAuthority,
    execution_local_date: date,
) -> dict[str, object]:
    workout = authority.prescription
    schedule_offset_days = (execution_local_date - workout.date).days
    return {
        "local_activity_id": activity.local_activity_id,
        "workout_identity": authority.identity.model_dump(mode="json"),
        "applied_week_approval_id": authority.applied_week_approval_id,
        "applied_running_workouts_sha256": authority.applied_running_workouts_sha256,
        "workout_prescription_sha256": canonical_data_sha256(workout),
        "activity_performance_evidence_sha256": (activity_performance_evidence_sha256(activity)),
        "schedule_timezone": authority.schedule_timezone,
        "scheduled_local_date": workout.date,
        "execution_local_date": execution_local_date,
        "schedule_offset_days": schedule_offset_days,
        "timing": _timing(schedule_offset_days),
        "workout_type": str(workout.workout_type),
        "workout_purpose": workout.purpose,
        "planned_distance_meters": workout.planned_distance_meters,
        "planned_duration_seconds": workout.planned_duration_seconds,
        "activity_distance_meters": activity.distance_meters,
        "activity_elapsed_duration_seconds": activity.duration.elapsed_seconds,
        "activity_moving_duration_seconds": activity.duration.moving_seconds,
    }


def build_fulfillment_candidates(
    *,
    activity: CanonicalActivity,
    workout_authorities: list[FulfillmentWorkoutAuthority],
    manifest: WorkoutFulfillmentManifest,
) -> list[WorkoutFulfillmentCandidate]:
    """Return every eligible applied workout; never choose one for the athlete."""
    if activity.status != ActivityStatus.ACTIVE or not is_running_sport(activity.sport):
        return []
    existing_fulfillment = manifest.fulfillments.get(activity.local_activity_id)
    if activity.local_activity_id in manifest.historical_legacy_fulfillments:
        return []
    if activity.local_activity_id in manifest.unresolved_fulfillment_conflicts:
        return []
    if existing_fulfillment is not None and (
        existing_fulfillment.provider_pair is None
        or existing_fulfillment.athlete_confirmation is not None
    ):
        return []
    fulfilled_identities = {
        (
            record.workout_identity.plan_id,
            record.workout_identity.plan_revision_id,
            record.workout_identity.week_number,
            record.workout_identity.local_workout_id,
        )
        for local_activity_id, record in manifest.fulfillments.items()
        if local_activity_id != activity.local_activity_id
    }
    fulfilled_identities.update(
        (
            record.workout_identity.plan_id,
            record.workout_identity.plan_revision_id,
            record.workout_identity.week_number,
            record.workout_identity.local_workout_id,
        )
        for record in manifest.historical_legacy_fulfillments.values()
    )
    candidates: list[WorkoutFulfillmentCandidate] = []
    for authority in sorted(
        workout_authorities,
        key=lambda item: (item.prescription.date, item.identity.local_workout_id),
    ):
        workout = authority.prescription
        identity_key = (
            authority.identity.plan_id,
            authority.identity.plan_revision_id,
            authority.identity.week_number,
            authority.identity.local_workout_id,
        )
        if (
            existing_fulfillment is not None
            and authority.identity != existing_fulfillment.workout_identity
        ):
            continue
        if identity_key in fulfilled_identities:
            continue
        if workout.workout_type in {WorkoutType.RACE.value, WorkoutType.BENCHMARK.value}:
            continue
        execution_local_date = _execution_local_date(
            activity,
            schedule_timezone=authority.schedule_timezone,
        )
        if execution_local_date is None or not _same_training_week(
            execution_local_date,
            workout.date,
        ):
            continue
        payload = _candidate_payload(
            activity=activity,
            authority=authority,
            execution_local_date=execution_local_date,
        )
        candidate_sha256 = canonical_data_sha256(
            {
                **payload,
                "scheduled_local_date": workout.date.isoformat(),
                "execution_local_date": execution_local_date.isoformat(),
            }
        )
        revoked_exact_association = any(
            revocation.fulfillment.local_activity_id == activity.local_activity_id
            and revocation.fulfillment.workout_identity == authority.identity
            and revocation.fulfillment.workout_prescription_sha256
            == payload["workout_prescription_sha256"]
            and revocation.fulfillment.activity_performance_evidence_sha256
            == payload["activity_performance_evidence_sha256"]
            for revocation in manifest.revoked_fulfillments
        )
        if candidate_sha256 in manifest.dismissed_candidates or revoked_exact_association:
            continue
        candidates.append(
            WorkoutFulfillmentCandidate.model_validate(
                {"candidate_sha256": candidate_sha256, **payload}
            )
        )
    return candidates
