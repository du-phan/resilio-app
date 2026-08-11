"""Reconcile ownership-proven future deletions for one applied week."""

from __future__ import annotations

from datetime import date
from typing import Callable

from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.core.workout_publication.retirement_service import (
    WorkoutRetirementService,
)
from resilio.schemas.publication import WeekSynchronizationItem
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentRecord


def reconcile_owned_future_deletions(
    *,
    repo: RepositoryIO,
    retirement_service: WorkoutRetirementService,
    local_workout_ids: list[str],
    fulfillments_by_local_workout_id: dict[str, WorkoutFulfillmentRecord],
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
        fulfillment = fulfillments_by_local_workout_id.get(local_workout_id)
        expected_target = (
            confirmed_remote_targets.get(local_workout_id)
            if confirmed_remote_targets is not None
            else None
        )
        restore_confirmed_target = restore_local and expected_target is not None
        try:
            if record is None and fulfillment is not None:
                authoritative_workout = authoritative_workouts_by_local_id.get(local_workout_id)
                provider_name = provider_names_by_local_workout_id.get(local_workout_id)
                if authoritative_workout is None or provider_name is None:
                    raise PublicationSafetyError(
                        "Pending retirement lacks applied workout authority"
                    )
                result = retirement_service.retire_pending(
                    authoritative_workout,
                    fulfillment=fulfillment,
                    restore_local=restore_confirmed_target,
                    provider_name=provider_name,
                    expected_remote_target=expected_target,
                )
            else:
                result = retirement_service.retire_published(
                    local_workout_id,
                    restore_local=restore_confirmed_target,
                    fulfillment=fulfillment,
                    expected_remote_target=expected_target,
                )
        except Exception as exc:
            partial = True
            items.append(
                WeekSynchronizationItem(
                    local_workout_id=local_workout_id,
                    occurrence_date=occurrence_date,
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
                    status=result.action,
                    event_id=result.event_id,
                )
            )
    return items, partial
