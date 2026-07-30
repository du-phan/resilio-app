"""Verified planned-workout adherence from owned completion identities."""

from __future__ import annotations

from datetime import date
from typing import Literal

from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.coaching import AdherenceContext, PlannedWorkoutContext
from resilio.schemas.plan import WorkoutPrescription
from resilio.schemas.publication import (
    PublicationManifest,
    WorkoutCompletionManifest,
)


def build_adherence_context(
    *,
    workouts: list[WorkoutPrescription],
    activities: list[CanonicalActivity],
    completion_manifest: WorkoutCompletionManifest,
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
        return AdherenceContext(
            status=status,
            reason=reason,
            planned_workout_count=0,
            due_workout_count=0,
            verified_completed_workout_count=0,
            due_unmatched_workout_count=0,
            workouts=[],
            due_planned_low_intensity_duration_seconds=0,
            due_planned_moderate_intensity_duration_seconds=0,
            due_planned_high_intensity_duration_seconds=0,
        )
    activities_by_id = {activity.local_activity_id: activity for activity in activities}
    activity_id_by_workout_id = {
        match.local_workout_id: local_activity_id
        for local_activity_id, match in completion_manifest.matches.items()
        if local_activity_id in activities_by_id
    }
    published = publication_manifest.workouts if publication_manifest is not None else {}

    contexts: list[PlannedWorkoutContext] = []
    due_count = 0
    verified_count = 0
    due_unmatched_count = 0
    due_low_duration_seconds = 0
    due_moderate_duration_seconds = 0
    due_high_duration_seconds = 0

    for workout in sorted(workouts, key=lambda item: (item.date, item.id)):
        is_due = workout.date <= as_of_date
        matched_activity_id = activity_id_by_workout_id.get(workout.id)
        if is_due:
            due_count += 1
            due_low_duration_seconds += workout.planned_low_intensity_duration_seconds
            due_moderate_duration_seconds += workout.planned_moderate_intensity_duration_seconds
            due_high_duration_seconds += workout.planned_high_intensity_duration_seconds
            if matched_activity_id is None:
                due_unmatched_count += 1
            else:
                verified_count += 1
        publication = published.get(workout.id)
        contexts.append(
            PlannedWorkoutContext(
                local_workout_id=workout.id,
                occurrence_date=workout.date,
                sport=str(workout.sport),
                workout_type=str(workout.workout_type),
                planned_duration_seconds=workout.planned_duration_seconds,
                planned_distance_meters=workout.planned_distance_meters,
                is_due=is_due,
                matched_local_activity_id=matched_activity_id,
                provider_computed_aerobic_load_points=(
                    publication.provider_computed_aerobic_load_points
                    if publication is not None
                    else None
                ),
                provider_relative_intensity_percent=(
                    publication.provider_relative_intensity_percent
                    if publication is not None
                    else None
                ),
            )
        )

    return AdherenceContext(
        status="available",
        reason=None,
        planned_workout_count=len(contexts),
        due_workout_count=due_count,
        verified_completed_workout_count=verified_count,
        due_unmatched_workout_count=due_unmatched_count,
        workouts=contexts,
        due_planned_low_intensity_duration_seconds=due_low_duration_seconds,
        due_planned_moderate_intensity_duration_seconds=(due_moderate_duration_seconds),
        due_planned_high_intensity_duration_seconds=due_high_duration_seconds,
    )
