"""Desired-state selection for one exact applied running week."""

from __future__ import annotations

from datetime import date
from typing import Literal

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import provider_local_date
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import WeekSynchronizationItem


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
    publication_manifest = load_manifest(repo)
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
        is_fulfilled = _identity_tuple(item.identity) in fulfilled
        owned_records = [
            record
            for record in (
                publication_manifest.workouts.get(workout.id),
                publication_manifest.pending.get(workout.id),
            )
            if record is not None and record.workout_identity == item.identity
        ]
        requires_schedule_restore = any(
            provider_local_date(record.provider_start_date_local) != workout.date
            for record in owned_records
        )
        pending = publication_manifest.pending.get(workout.id)
        has_unfinished_pending = (
            pending is not None and pending.workout_identity == item.identity
        )
        status: Literal["skipped_past"] | None = (
            "skipped_past"
            if workout.date < as_of_date
            and not is_fulfilled
            and not requires_schedule_restore
            and not has_unfinished_pending
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
    manifest = load_manifest(repo)
    stale_published_ids = {
        local_id
        for local_id, record in manifest.workouts.items()
        if record.workout_identity.plan_id == week_identity.plan_id
        and record.workout_identity.plan_revision_id == week_identity.plan_revision_id
        and record.workout_identity.week_number == week_identity.week_number
        and max(
            record.occurrence_date,
            provider_local_date(record.provider_start_date_local),
        )
        >= as_of_date
        and _identity_tuple(record.workout_identity) not in fulfilled
        and local_id not in current_run_ids
    }
    stale_pending_ids = {
        local_id
        for local_id, record in manifest.pending.items()
        if record.workout_identity.plan_id == week_identity.plan_id
        and record.workout_identity.plan_revision_id == week_identity.plan_revision_id
        and record.workout_identity.week_number == week_identity.week_number
        and _identity_tuple(record.workout_identity) not in fulfilled
        and local_id not in current_run_ids
    }
    return sorted(stale_published_ids | stale_pending_ids)
