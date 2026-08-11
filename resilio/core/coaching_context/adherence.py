"""Planned-workout adherence from exact fulfillment identities."""

from __future__ import annotations

from datetime import date
from typing import Literal

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_authority_is_current,
    assert_fulfillment_is_usable,
    fulfillment_was_available_as_of,
)
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.coaching import AdherenceContext, PlannedWorkoutContext
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import PublicationManifest, PublishedWorkout
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)


def _fulfillment_status(
    fulfillment: WorkoutFulfillmentRecord | None,
) -> Literal[
    "unfulfilled",
    "fulfilled_early",
    "fulfilled_on_schedule",
    "fulfilled_late",
]:
    if fulfillment is None:
        return "unfulfilled"
    if fulfillment.schedule_offset_days < 0:
        return "fulfilled_early"
    if fulfillment.schedule_offset_days > 0:
        return "fulfilled_late"
    return "fulfilled_on_schedule"


def _identity_key(identity: PlanWorkoutIdentity) -> tuple[str, str, int, str]:
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def _planned_workout_context(
    authoritative_workout: AuthoritativeWorkout,
    *,
    as_of_date: date,
    fulfillment_match: tuple[str, WorkoutFulfillmentRecord] | None,
    publication: PublishedWorkout | None,
) -> PlannedWorkoutContext:
    workout = authoritative_workout.prescription
    identity = authoritative_workout.identity
    if publication is not None and publication.workout_identity != identity:
        publication = None
    matched_activity_id = fulfillment_match[0] if fulfillment_match is not None else None
    fulfillment = fulfillment_match[1] if fulfillment_match is not None else None
    return PlannedWorkoutContext(
        workout_identity=identity,
        local_workout_id=workout.id,
        occurrence_date=workout.date,
        sport=str(workout.sport),
        workout_type=str(workout.workout_type),
        planned_duration_seconds=workout.planned_duration_seconds,
        planned_distance_meters=workout.planned_distance_meters,
        is_due=workout.date <= as_of_date,
        is_outstanding=fulfillment is None,
        fulfillment_status=_fulfillment_status(fulfillment),
        fulfillment_basis=(fulfillment.fulfillment_basis if fulfillment is not None else None),
        execution_local_date=(
            fulfillment.execution_local_date if fulfillment is not None else None
        ),
        schedule_offset_days=(
            fulfillment.schedule_offset_days if fulfillment is not None else None
        ),
        matched_local_activity_id=matched_activity_id,
        provider_computed_aerobic_load_points=(
            publication.provider_computed_aerobic_load_points if publication is not None else None
        ),
        provider_relative_intensity_percent=(
            publication.provider_relative_intensity_percent if publication is not None else None
        ),
    )


def _published_evidence(
    manifest: PublicationManifest | None,
    authoritative_workout: AuthoritativeWorkout,
) -> PublishedWorkout | None:
    if manifest is None:
        return None
    local_workout_id = authoritative_workout.identity.local_workout_id
    active = manifest.workouts.get(local_workout_id)
    retired = manifest.retired.get(local_workout_id)
    candidates = [
        publication
        for publication in (
            active,
            (
                retired.publication
                if retired is not None and retired.reopened_at_utc is None
                else None
            ),
        )
        if publication is not None
        and publication.workout_identity == authoritative_workout.identity
    ]
    if len(candidates) > 1:
        raise ValueError("Workout has competing active and retired publication evidence")
    return candidates[0] if candidates else None


def _unavailable_adherence_context(
    *,
    status: Literal["no_plan", "unavailable"],
    reason: str | None,
) -> AdherenceContext:
    return AdherenceContext(
        status=status,
        reason=reason,
        planned_workout_count=0,
        due_workout_count=0,
        fulfilled_workout_count=0,
        due_fulfilled_workout_count=0,
        due_unfulfilled_workout_count=0,
        fulfilled_early_workout_count=0,
        fulfilled_late_workout_count=0,
        workouts=[],
        due_planned_low_intensity_duration_seconds=0,
        due_planned_moderate_intensity_duration_seconds=0,
        due_planned_high_intensity_duration_seconds=0,
    )


def build_adherence_context(
    *,
    workouts: list[AuthoritativeWorkout],
    activities: list[CanonicalActivity],
    fulfillment_manifest: WorkoutFulfillmentManifest,
    as_of_date: date,
    publication_manifest: PublicationManifest | None = None,
    status: Literal["available", "no_plan", "unavailable"] = "available",
    reason: str | None = None,
) -> AdherenceContext:
    """Build adherence without heuristic date, sport, or duration matching."""
    if status not in {"available", "no_plan", "unavailable"}:
        raise ValueError(f"Unsupported adherence status: {status}")
    if status != "available":
        if workouts:
            raise ValueError("Unavailable adherence cannot contain unverified workouts")
        assert status in {"no_plan", "unavailable"}
        return _unavailable_adherence_context(
            status=status,
            reason=reason,
        )
    activities_by_id = {activity.local_activity_id: activity for activity in activities}
    authorities_by_identity = {_identity_key(workout.identity): workout for workout in workouts}
    fulfillment_by_workout_identity = {}
    for local_activity_id, record in fulfillment_manifest.fulfillments.items():
        if not fulfillment_was_available_as_of(record, as_of_date=as_of_date):
            continue
        identity = record.workout_identity
        identity_key = _identity_key(identity)
        authority = authorities_by_identity.get(identity_key)
        if authority is None:
            continue
        activity = activities_by_id.get(local_activity_id)
        if activity is None:
            raise ValueError("Fulfillment references an unavailable canonical activity")
        assert_fulfillment_authority_is_current(record, authority)
        assert_fulfillment_is_usable(record, activity, fulfillment_manifest)
        fulfillment_by_workout_identity[identity_key] = (local_activity_id, record)
    contexts: list[PlannedWorkoutContext] = []
    due_count = 0
    fulfilled_count = 0
    due_fulfilled_count = 0
    due_unfulfilled_count = 0
    fulfilled_early_count = 0
    fulfilled_late_count = 0
    due_low_duration_seconds = 0
    due_moderate_duration_seconds = 0
    due_high_duration_seconds = 0

    for authoritative_workout in sorted(
        workouts,
        key=lambda item: (
            item.prescription.date,
            item.identity.local_workout_id,
        ),
    ):
        workout = authoritative_workout.prescription
        workout_identity = authoritative_workout.identity
        is_due = workout.date <= as_of_date
        fulfillment_match = fulfillment_by_workout_identity.get(_identity_key(workout_identity))
        if is_due:
            due_count += 1
            due_low_duration_seconds += workout.planned_low_intensity_duration_seconds
            due_moderate_duration_seconds += workout.planned_moderate_intensity_duration_seconds
            due_high_duration_seconds += workout.planned_high_intensity_duration_seconds
            if fulfillment_match is None:
                due_unfulfilled_count += 1
            else:
                due_fulfilled_count += 1
        fulfillment = fulfillment_match[1] if fulfillment_match is not None else None
        if fulfillment is not None:
            fulfilled_count += 1
            if fulfillment.schedule_offset_days < 0:
                fulfilled_early_count += 1
            elif fulfillment.schedule_offset_days > 0:
                fulfilled_late_count += 1
        contexts.append(
            _planned_workout_context(
                authoritative_workout,
                as_of_date=as_of_date,
                fulfillment_match=fulfillment_match,
                publication=_published_evidence(
                    publication_manifest,
                    authoritative_workout,
                ),
            )
        )

    return AdherenceContext(
        status="available",
        reason=None,
        planned_workout_count=len(contexts),
        due_workout_count=due_count,
        fulfilled_workout_count=fulfilled_count,
        due_fulfilled_workout_count=due_fulfilled_count,
        due_unfulfilled_workout_count=due_unfulfilled_count,
        fulfilled_early_workout_count=fulfilled_early_count,
        fulfilled_late_workout_count=fulfilled_late_count,
        workouts=contexts,
        due_planned_low_intensity_duration_seconds=due_low_duration_seconds,
        due_planned_moderate_intensity_duration_seconds=(due_moderate_duration_seconds),
        due_planned_high_intensity_duration_seconds=due_high_duration_seconds,
    )
