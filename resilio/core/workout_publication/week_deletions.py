"""Reconcile ownership-proven future deletions for one applied week."""

from __future__ import annotations

from datetime import date
from typing import Callable

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import provider_local_date
from resilio.core.workout_publication.retirement_service import (
    WorkoutRetirementService,
)
from resilio.schemas.publication import WeekSynchronizationItem


def reconcile_owned_future_deletions(
    *,
    repo: RepositoryIO,
    retirement_service: WorkoutRetirementService,
    local_workout_ids: list[str],
    authoritative_workouts_by_local_id: dict[str, AuthoritativeWorkout],
    provider_names_by_local_workout_id: dict[str, str],
    as_of_date: date,
    restore_local: bool,
    confirmed_remote_targets: dict[str, tuple[int, str]] | None,
    error_type_for: Callable[[Exception], str],
) -> tuple[list[WeekSynchronizationItem], bool]:
    """Retire each exact desired-state deletion and retain per-item failures."""
    items: list[WeekSynchronizationItem] = []
    partial = False
    for local_workout_id in local_workout_ids:
        manifest = load_manifest(repo)
        record = manifest.workouts.get(local_workout_id)
        pending = manifest.pending.get(local_workout_id)
        occurrence_date = (
            record.occurrence_date
            if record is not None
            else pending.occurrence_date
            if pending is not None
            else as_of_date
        )
        event_id = record.event_id if record is not None else None
        provider_occurrence_date = provider_local_date(
            (
                record.provider_start_date_local
                if record is not None
                else pending.provider_start_date_local
                if pending is not None
                else occurrence_date.isoformat()
            )
        )
        expected_target = (
            confirmed_remote_targets.get(local_workout_id)
            if confirmed_remote_targets is not None
            else None
        )
        restore_confirmed_target = restore_local and expected_target is not None
        try:
            result = retirement_service.retire_published(
                local_workout_id,
                restore_local=restore_confirmed_target,
                expected_remote_target=expected_target,
                authoritative_workout=authoritative_workouts_by_local_id.get(
                    local_workout_id
                ),
                provider_name=provider_names_by_local_workout_id.get(
                    local_workout_id
                ),
            )
        except Exception as exc:
            partial = True
            items.append(
                WeekSynchronizationItem(
                    local_workout_id=local_workout_id,
                    occurrence_date=occurrence_date,
                    provider_occurrence_date=provider_occurrence_date,
                    status="error",
                    event_id=event_id,
                    error_type=error_type_for(exc),
                    message=str(exc),
                )
            )
        else:
            items.append(
                WeekSynchronizationItem(
                    local_workout_id=local_workout_id,
                    occurrence_date=occurrence_date,
                    provider_occurrence_date=provider_occurrence_date,
                    status=result.action,
                    event_id=result.event_id,
                )
            )
    return items, partial
