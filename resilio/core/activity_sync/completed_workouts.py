"""Pure completed-activity to owned-workout reconciliation policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.publication import (
    PublishedWorkout,
    WorkoutCompletionMatch,
)


@dataclass(frozen=True)
class CompletionReconciliation:
    match: Optional[WorkoutCompletionMatch] = None
    candidate: Optional[dict[str, Any]] = None
    conflict: Optional[dict[str, Any]] = None


def _start_delta_seconds(
    activity: CanonicalActivity,
    start_date_local: str,
) -> Optional[float]:
    activity_start = activity.occurrence.start_time_local
    if activity_start is None:
        return None
    try:
        planned_start = datetime.fromisoformat(start_date_local)
    except ValueError:
        return None
    return abs(
        (activity_start.replace(tzinfo=None) - planned_start.replace(tzinfo=None)).total_seconds()
    )


def reconcile_workout_completion(
    *,
    activity: CanonicalActivity,
    paired_event_id: Optional[int],
    publications_by_event_id: dict[int, PublishedWorkout],
    publications: Iterable[PublishedWorkout],
    existing_match: Optional[WorkoutCompletionMatch],
    matched_at_utc: datetime,
) -> CompletionReconciliation:
    """Prefer exact owned event pairing; keep heuristic candidates report-only."""
    publication = (
        publications_by_event_id.get(paired_event_id) if paired_event_id is not None else None
    )
    if publication is not None:
        if publication.sport != str(activity.sport):
            return CompletionReconciliation(
                conflict={
                    "rule": "paired_event_sport_mismatch",
                    "local_activity_id": activity.local_activity_id,
                    "local_workout_id": publication.local_workout_id,
                }
            )
        if (
            existing_match is not None
            and existing_match.local_workout_id == publication.local_workout_id
        ):
            return CompletionReconciliation()
        return CompletionReconciliation(
            match=WorkoutCompletionMatch(
                local_activity_id=activity.local_activity_id,
                local_workout_id=publication.local_workout_id,
                match_method="paired_event_id",
                matched_at_utc=matched_at_utc,
            )
        )

    if paired_event_id is not None or existing_match is not None:
        return CompletionReconciliation()

    candidates = []
    for item in publications:
        if item.occurrence_date != activity.occurrence.local_date or item.sport != str(
            activity.sport
        ):
            continue
        start_delta = _start_delta_seconds(activity, item.start_date_local)
        if start_delta is not None and start_delta <= 10_800:
            candidates.append((item, start_delta))
    if len(candidates) != 1:
        return CompletionReconciliation()

    candidate, start_delta = candidates[0]
    return CompletionReconciliation(
        candidate={
            "local_activity_id": activity.local_activity_id,
            "local_workout_id": candidate.local_workout_id,
            "rule": "unique_date_sport_time_candidate",
            "start_delta_seconds": start_delta,
        }
    )
