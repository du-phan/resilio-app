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
    LegacyWorkoutCompletionManifest,
)
from resilio.schemas.activity import ActivityStatus


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
