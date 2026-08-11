"""Exact pre-cutover coaching-source fingerprint used to prove artifact freshness."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.source_state import source_coverage_evidence
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import load_wellness
from resilio.core.workout_fulfillment.legacy_contracts import (
    LegacyPublicationManifest,
    LegacyV7PublicationManifest,
    LegacyWorkoutCompletionManifest,
)
from resilio.core.workout_fulfillment.legacy_fulfillment_contracts import (
    LegacyV1WorkoutFulfillmentManifest,
)
from resilio.schemas.activity import ActivityStatus
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest


def _default_window_start(evidence_as_of_date: date) -> date:
    target_week_start = evidence_as_of_date - timedelta(days=evidence_as_of_date.weekday())
    return target_week_start - timedelta(weeks=11)


def legacy_coaching_evidence_source_sha256_unlocked(
    repo: RepositoryIO,
    *,
    evidence_as_of_date: date,
    evidence_window_start: date | None,
    legacy_completion_raw: dict[str, Any] | None,
    legacy_publication_raw: dict[str, Any] | None,
) -> str:
    """Reproduce the removed completion-era fingerprint from exact legacy bytes."""
    window_start = evidence_window_start or _default_window_start(evidence_as_of_date)
    if window_start.weekday() != 0 or window_start > evidence_as_of_date:
        raise PlanOperationError("Legacy evidence fingerprint requires a valid Monday window")
    activities = sorted(
        (
            activity
            for activity in ActivityArchive(repo.resolve_path("data/activities")).load_all()
            if activity.status == ActivityStatus.ACTIVE
            and window_start <= activity.occurrence.local_date <= evidence_as_of_date
        ),
        key=lambda activity: activity.local_activity_id,
    )
    active_activity_ids = {activity.local_activity_id for activity in activities}
    try:
        completion_matches = LegacyWorkoutCompletionManifest.model_validate(
            legacy_completion_raw or {}
        ).matches
        published_workouts = LegacyPublicationManifest.model_validate(
            legacy_publication_raw or {}
        ).workouts
    except ValueError as exc:
        raise PlanOperationError("Legacy completion or publication source is malformed") from exc
    relevant_publications: dict[str, Any] = {}
    for local_workout_id, publication in sorted(published_workouts.items()):
        if window_start <= publication.occurrence_date <= evidence_as_of_date:
            relevant_publications[local_workout_id] = publication.model_dump(mode="json")
    wellness = load_wellness(repo)
    payload = {
        "activities": [activity.model_dump(mode="json") for activity in activities],
        "wellness": [
            wellness[local_date].model_dump(mode="json")
            for local_date in sorted(wellness)
            if local_date <= evidence_as_of_date
        ],
        "source_coverage_by_week": source_coverage_evidence(
            repo,
            window_start=window_start,
            evidence_as_of_date=evidence_as_of_date,
        ),
        "completion_matches": {
            local_activity_id: match.model_dump(mode="json")
            for local_activity_id, match in sorted(completion_matches.items())
            if local_activity_id in active_activity_ids
        },
        "published_workouts": relevant_publications,
    }
    return canonical_data_sha256(payload)


def _add_v2_pair_provenance(value: Any, *, field_name: str | None = None) -> Any:
    if isinstance(value, list):
        return [_add_v2_pair_provenance(item) for item in value]
    if not isinstance(value, dict):
        return value
    translated = {
        key: _add_v2_pair_provenance(item, field_name=key)
        for key, item in value.items()
    }
    if field_name == "provider_pair" and translated.get("event_id") is not None:
        translated.setdefault("provenance", "provider_observed")
    return translated


def _without_pair_provenance(value: Any, *, field_name: str | None = None) -> Any:
    if isinstance(value, list):
        return [_without_pair_provenance(item) for item in value]
    if not isinstance(value, dict):
        return value
    translated = {
        key: _without_pair_provenance(item, field_name=key)
        for key, item in value.items()
        if not (field_name == "provider_pair" and key == "provenance")
    }
    return translated


def _validated_v1_fulfillment_manifest(
    raw: dict[str, Any] | None,
) -> WorkoutFulfillmentManifest:
    legacy = LegacyV1WorkoutFulfillmentManifest.model_validate(
        raw or {"schema_version": 1}
    )
    payload = _add_v2_pair_provenance(legacy.model_dump(mode="json"))
    payload["schema_version"] = 2
    payload["remote_pairing_operations"] = {}
    payload["remote_pairing_drift_resolutions"] = []
    return WorkoutFulfillmentManifest.model_validate(payload)


def v1_coaching_evidence_source_sha256_unlocked(
    repo: RepositoryIO,
    *,
    evidence_as_of_date: date,
    evidence_window_start: date | None,
    fulfillment_raw: dict[str, Any] | None,
    publication_raw: dict[str, Any] | None,
) -> str:
    """Reproduce the exact fulfillment-v1/publication-v7 source fingerprint."""
    from resilio.core.workout_fulfillment.evidence import fulfillment_was_available_as_of

    window_start = evidence_window_start or _default_window_start(evidence_as_of_date)
    if window_start.weekday() != 0 or window_start > evidence_as_of_date:
        raise PlanOperationError("V1 evidence fingerprint requires a valid Monday window")
    context_window_end = evidence_as_of_date + timedelta(
        days=6 - evidence_as_of_date.weekday()
    )
    archived_activities = ActivityArchive(repo.resolve_path("data/activities")).load_all()
    activities = sorted(
        (
            activity
            for activity in archived_activities
            if activity.status == ActivityStatus.ACTIVE
            and window_start <= activity.occurrence.local_date <= evidence_as_of_date
        ),
        key=lambda activity: activity.local_activity_id,
    )
    active_activity_ids = {activity.local_activity_id for activity in activities}
    fulfillments = _validated_v1_fulfillment_manifest(fulfillment_raw)
    publications = LegacyV7PublicationManifest.model_validate(
        publication_raw or {"schema_version": 7}
    )
    relevant_fulfillments = {
        activity_id: record
        for activity_id, record in fulfillments.fulfillments.items()
        if window_start <= record.scheduled_local_date <= context_window_end
        and fulfillment_was_available_as_of(record, as_of_date=evidence_as_of_date)
    }
    relevant_historical = {
        activity_id: record
        for activity_id, record in fulfillments.historical_legacy_fulfillments.items()
        if window_start <= record.scheduled_local_date <= context_window_end
        and record.execution_local_date <= evidence_as_of_date
    }
    linked_activity_ids = (set(relevant_fulfillments) | set(relevant_historical)).difference(
        active_activity_ids
    )
    linked_activities = sorted(
        (
            activity
            for activity in archived_activities
            if activity.local_activity_id in linked_activity_ids
        ),
        key=lambda activity: activity.local_activity_id,
    )
    relevant_conflicts = {
        activity_id: conflict
        for activity_id, conflict in fulfillments.unresolved_fulfillment_conflicts.items()
        if activity_id in relevant_fulfillments or activity_id in relevant_historical
    }
    wellness = load_wellness(repo)
    payload = {
        "activities": [activity.model_dump(mode="json") for activity in activities],
        "linked_fulfillment_activities": [
            activity.model_dump(mode="json") for activity in linked_activities
        ],
        "wellness": [
            wellness[local_date].model_dump(mode="json")
            for local_date in sorted(wellness)
            if local_date <= evidence_as_of_date
        ],
        "source_coverage_by_week": source_coverage_evidence(
            repo,
            window_start=window_start,
            evidence_as_of_date=evidence_as_of_date,
        ),
        "workout_fulfillments": {
            activity_id: _without_pair_provenance(record.model_dump(mode="json"))
            for activity_id, record in sorted(relevant_fulfillments.items())
        },
        "historical_workout_fulfillments": {
            activity_id: _without_pair_provenance(record.model_dump(mode="json"))
            for activity_id, record in sorted(relevant_historical.items())
        },
        "unresolved_fulfillment_conflicts": {
            activity_id: conflict.model_dump(mode="json")
            for activity_id, conflict in sorted(relevant_conflicts.items())
        },
        "published_workouts": {
            workout_id: publication.model_dump(mode="json")
            for workout_id, publication in sorted(publications.workouts.items())
            if window_start <= publication.occurrence_date <= context_window_end
        },
        "retired_workout_publications": {
            workout_id: retirement.model_dump(mode="json")
            for workout_id, retirement in sorted(publications.retired.items())
            if window_start <= retirement.publication.occurrence_date <= context_window_end
        },
        "workout_publication_retirement_history": [
            retirement.model_dump(mode="json")
            for retirement in publications.retirement_history
            if window_start <= retirement.publication.occurrence_date <= context_window_end
        ],
        "pending_workout_publication_retirement_history": [
            retirement.model_dump(mode="json")
            for retirement in publications.pending_retirement_history
            if window_start
            <= retirement.pending_publication.occurrence_date
            <= context_window_end
        ],
        "historical_workout_publications": {
            workout_id: publication.model_dump(mode="json")
            for workout_id, publication in sorted(
                publications.historical_legacy_workouts.items()
            )
            if window_start <= publication.occurrence_date <= context_window_end
        },
    }
    return canonical_data_sha256(payload)
