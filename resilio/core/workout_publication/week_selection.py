"""Desired-state selection for one exact applied running week."""

from __future__ import annotations

from datetime import date
from typing import Literal

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.retirement import fulfillment_retirements
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import WeekSynchronizationItem
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRecord


def _identity_tuple(identity: PlanWorkoutIdentity) -> tuple[str, str, int, str]:
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def _fulfilled_identities(repo: RepositoryIO) -> set[tuple[str, str, int, str]]:
    return {
        _identity_tuple(record.workout_identity)
        for record in load_fulfillment_manifest(repo).fulfillments.values()
    }


def select_run_week_items(
    repo: RepositoryIO,
    *,
    workouts: list[AuthoritativeWorkout],
    as_of_date: date,
) -> tuple[
    list[AuthoritativeWorkout],
    list[WeekSynchronizationItem],
    set[str],
    PlanWorkoutIdentity,
]:
    fulfilled = _fulfilled_identities(repo)
    selected: list[AuthoritativeWorkout] = []
    skipped: list[WeekSynchronizationItem] = []
    for item in sorted(
        workouts,
        key=lambda candidate: (
            candidate.prescription.date,
            candidate.identity.local_workout_id,
        ),
    ):
        workout = item.prescription
        status: Literal["skipped_fulfilled", "skipped_past"] | None = (
            "skipped_fulfilled"
            if _identity_tuple(item.identity) in fulfilled
            else "skipped_past"
            if workout.date < as_of_date
            else None
        )
        if status is None:
            selected.append(item)
        else:
            skipped.append(
                WeekSynchronizationItem(
                    local_workout_id=workout.id,
                    occurrence_date=workout.date,
                    status=status,
                )
            )
    return (
        selected,
        skipped,
        {item.identity.local_workout_id for item in workouts},
        workouts[0].identity,
    )


def stale_future_owned_run_ids(
    repo: RepositoryIO,
    *,
    week_identity: PlanWorkoutIdentity,
    current_run_ids: set[str],
    as_of_date: date,
) -> list[str]:
    fulfilled = _fulfilled_identities(repo)
    return sorted(
        local_id
        for local_id, record in load_manifest(repo).workouts.items()
        if record.workout_identity.plan_id == week_identity.plan_id
        and record.workout_identity.plan_revision_id == week_identity.plan_revision_id
        and record.workout_identity.week_number == week_identity.week_number
        and record.occurrence_date >= as_of_date
        and _identity_tuple(record.workout_identity) not in fulfilled
        and local_id not in current_run_ids
    )


def week_fulfillment_retirements(
    repo: RepositoryIO,
    *,
    workouts: list[AuthoritativeWorkout],
    as_of_date: date,
) -> dict[str, WorkoutFulfillmentRecord]:
    retirements = fulfillment_retirements(
        publication_manifest=load_manifest(repo),
        fulfillment_manifest=load_fulfillment_manifest(repo),
        workout_authorities_by_identity={
            (
                workout.identity.plan_id,
                workout.identity.plan_revision_id,
                workout.identity.week_number,
                workout.identity.local_workout_id,
            ): workout
            for workout in workouts
        },
        canonical_activities_by_id={
            activity.local_activity_id: activity
            for activity in ActivityArchive(repo.resolve_path("data/activities")).load_all()
        },
        as_of_date=as_of_date,
    )
    return retirements
