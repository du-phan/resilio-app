"""Semantic transforms for legacy completion-shaped planning evidence."""

from __future__ import annotations

from datetime import date
from typing import Any

from resilio.core.workout_fulfillment.evidence import fulfillment_was_available_as_of
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.workout_fulfillment import (
    HistoricalLegacyWorkoutFulfillment,
    WorkoutFulfillmentManifest,
    WorkoutFulfillmentRecord,
)


class PlanningEvidenceTransformError(ValueError):
    """Legacy planning evidence does not prove one exact fulfillment meaning."""


def contains_legacy_planning_contracts(value: Any) -> bool:
    """Whether one artifact still contains a removed persisted contract."""
    if isinstance(value, dict):
        if (
            "source_context_sha256" in value
            or "verified_completed_workout_count" in value
            or "due_unmatched_workout_count" in value
            or value.get("evidence_kind") == "owned_workout_completion"
        ):
            return True
        return any(contains_legacy_planning_contracts(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_legacy_planning_contracts(child) for child in value)
    return False


def _identity_key(identity: PlanWorkoutIdentity) -> tuple[str, str, int, str]:
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def fulfillment_index(
    manifest: WorkoutFulfillmentManifest,
) -> dict[tuple[str, str, int, str, str], tuple[str, Any]]:
    indexed: dict[tuple[str, str, int, str, str], tuple[str, Any]] = {}
    for record in manifest.fulfillments.values():
        indexed[(*_identity_key(record.workout_identity), record.local_activity_id)] = (
            record.fulfillment_basis,
            record,
        )
    for historical_record in manifest.historical_legacy_fulfillments.values():
        indexed[
            (
                *_identity_key(historical_record.workout_identity),
                historical_record.local_activity_id,
            )
        ] = (
            "provider_paired",
            historical_record,
        )
    return indexed


def _validated_legacy_counts(
    adherence: dict[str, Any],
    workouts: list[dict[str, Any]],
) -> None:
    due_count = sum(bool(item.get("is_due")) for item in workouts)
    due_matched_count = sum(
        bool(item.get("is_due") and item.get("matched_local_activity_id")) for item in workouts
    )
    expected = {
        "planned_workout_count": len(workouts),
        "due_workout_count": due_count,
        "verified_completed_workout_count": due_matched_count,
        "due_unmatched_workout_count": due_count - due_matched_count,
    }
    if any(adherence.get(name) != value for name, value in expected.items()):
        raise PlanningEvidenceTransformError(
            "Legacy adherence aggregate counts do not match workout evidence"
        )


def _migrated_workout(
    raw_workout: dict[str, Any],
    *,
    evidence_by_identity: dict[tuple[str, str, int, str, str], tuple[str, Any]],
    evidence_as_of_date: date,
) -> dict[str, Any]:
    workout = dict(raw_workout)
    identity = PlanWorkoutIdentity.model_validate(workout.get("workout_identity"))
    activity_id = workout.get("matched_local_activity_id")
    if activity_id is None:
        workout.update(
            is_outstanding=True,
            fulfillment_status="unfulfilled",
            fulfillment_basis=None,
            execution_local_date=None,
            schedule_offset_days=None,
        )
        return workout
    evidence = evidence_by_identity.get((*_identity_key(identity), str(activity_id)))
    if evidence is None:
        raise PlanningEvidenceTransformError(
            "Legacy matched workout lacks migrated exact fulfillment evidence"
        )
    fulfillment_basis, record = evidence
    evidence_was_available = (
        fulfillment_was_available_as_of(record, as_of_date=evidence_as_of_date)
        if isinstance(record, WorkoutFulfillmentRecord)
        else isinstance(record, HistoricalLegacyWorkoutFulfillment)
        and record.execution_local_date <= evidence_as_of_date
    )
    if not evidence_was_available:
        workout.update(
            matched_local_activity_id=None,
            is_outstanding=True,
            fulfillment_status="unfulfilled",
            fulfillment_basis=None,
            execution_local_date=None,
            schedule_offset_days=None,
        )
        return workout
    execution_local_date = record.execution_local_date
    try:
        execution_date = date.fromisoformat(str(execution_local_date))
        scheduled_date = date.fromisoformat(str(workout.get("occurrence_date")))
    except ValueError as exc:
        raise PlanningEvidenceTransformError("Legacy workout dates are invalid") from exc
    offset_days = (execution_date - scheduled_date).days
    status = (
        "fulfilled_early"
        if offset_days < 0
        else "fulfilled_late"
        if offset_days > 0
        else "fulfilled_on_schedule"
    )
    workout.update(
        is_outstanding=False,
        fulfillment_status=status,
        fulfillment_basis=fulfillment_basis,
        execution_local_date=execution_date.isoformat(),
        schedule_offset_days=offset_days,
    )
    return workout


def _migrate_legacy_adherence(
    weekly_context: dict[str, Any],
    *,
    evidence_by_identity: dict[tuple[str, str, int, str, str], tuple[str, Any]],
) -> None:
    adherence = weekly_context.get("adherence")
    if not isinstance(adherence, dict) or "verified_completed_workout_count" not in adherence:
        return
    activities = weekly_context.get("activities")
    if not isinstance(activities, list):
        raise PlanningEvidenceTransformError("Legacy weekly evidence lacks activities")
    workouts_raw = adherence.get("workouts")
    if not isinstance(workouts_raw, list) or any(
        not isinstance(item, dict) for item in workouts_raw
    ):
        raise PlanningEvidenceTransformError("Legacy adherence workouts are invalid")
    workouts = [dict(item) for item in workouts_raw]
    try:
        evidence_as_of_date = date.fromisoformat(str(weekly_context["as_of_date"]))
    except (KeyError, ValueError) as exc:
        raise PlanningEvidenceTransformError("Legacy weekly evidence cutoff is invalid") from exc
    _validated_legacy_counts(adherence, workouts)
    migrated_workouts = [
        _migrated_workout(
            workout,
            evidence_by_identity=evidence_by_identity,
            evidence_as_of_date=evidence_as_of_date,
        )
        for workout in workouts
    ]
    adherence.pop("verified_completed_workout_count")
    adherence.pop("due_unmatched_workout_count")
    adherence.update(
        schema_version=2,
        fulfilled_workout_count=sum(
            item["fulfillment_status"] != "unfulfilled" for item in migrated_workouts
        ),
        due_fulfilled_workout_count=sum(
            bool(item.get("is_due")) and item["fulfillment_status"] != "unfulfilled"
            for item in migrated_workouts
        ),
        due_unfulfilled_workout_count=sum(
            bool(item.get("is_due")) and item["fulfillment_status"] == "unfulfilled"
            for item in migrated_workouts
        ),
        fulfilled_early_workout_count=sum(
            item["fulfillment_status"] == "fulfilled_early" for item in migrated_workouts
        ),
        fulfilled_late_workout_count=sum(
            item["fulfillment_status"] == "fulfilled_late" for item in migrated_workouts
        ),
        workouts=migrated_workouts,
    )
    weekly_context["schema_version"] = 2


def migrate_embedded_planning_contracts(
    value: Any,
    *,
    evidence_by_identity: dict[tuple[str, str, int, str, str], tuple[str, Any]],
) -> None:
    """Rewrite embedded legacy week/totals objects in one raw artifact tree."""
    if isinstance(value, dict):
        if value.get("evidence_kind") == "owned_workout_completion":
            value["evidence_kind"] = "owned_workout_fulfillment"
        _migrate_legacy_adherence(
            value,
            evidence_by_identity=evidence_by_identity,
        )
        if "verified_completed_workout_count" in value:
            value["due_fulfilled_workout_count"] = value.pop("verified_completed_workout_count")
        if "due_unmatched_workout_count" in value:
            value["due_unfulfilled_workout_count"] = value.pop("due_unmatched_workout_count")
        for child in value.values():
            migrate_embedded_planning_contracts(
                child,
                evidence_by_identity=evidence_by_identity,
            )
    elif isinstance(value, list):
        for child in value:
            migrate_embedded_planning_contracts(
                child,
                evidence_by_identity=evidence_by_identity,
            )
