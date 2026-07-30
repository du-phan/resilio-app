"""Canonical fingerprint of mutable evidence used by macro planning."""

from __future__ import annotations

from datetime import date, timedelta

from resilio.core.activity_sync.archive import (
    ActivityArchive,
    ActivityArchiveError,
)
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH
from resilio.core.locking import OperationLock, OperationLockError
from resilio.core.planning.artifacts import canonical_data_sha256
from resilio.core.planning.errors import PlanOperationError
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import load_wellness
from resilio.schemas.activity import ActivityStatus

DEFAULT_RECENT_EVIDENCE_WEEK_COUNT = 12


def _evidence_window_start(evidence_as_of_date: date) -> date:
    target_week_start = evidence_as_of_date - timedelta(days=evidence_as_of_date.weekday())
    return target_week_start - timedelta(weeks=DEFAULT_RECENT_EVIDENCE_WEEK_COUNT - 1)


def _coverage_evidence(
    repo: RepositoryIO,
    *,
    window_start: date,
    evidence_as_of_date: date,
) -> list[dict[str, object]]:
    from resilio.core.coaching_context.coverage import (
        build_sync_evidence_coverage,
    )

    target_week_start = evidence_as_of_date - timedelta(days=evidence_as_of_date.weekday())
    coverage = []
    week_start = window_start
    while week_start <= target_week_start:
        week_end = min(week_start + timedelta(days=6), evidence_as_of_date)
        coverage.append(
            build_sync_evidence_coverage(
                repo,
                requested_window_start=week_start,
                requested_window_end=week_end,
            ).model_dump(mode="json")
        )
        week_start += timedelta(weeks=1)
    return coverage


def coaching_evidence_source_sha256(
    repo: RepositoryIO,
    *,
    evidence_as_of_date: date,
    evidence_window_start: date | None = None,
) -> str:
    """Hash the exact mutable source slice represented by recent context."""
    from resilio.core.workout_publication.completions import (
        load_completion_manifest,
    )
    from resilio.core.workout_publication.manifest import load_manifest

    window_start = evidence_window_start or _evidence_window_start(evidence_as_of_date)
    if window_start.weekday() != 0 or window_start > evidence_as_of_date:
        raise PlanOperationError("Coaching evidence fingerprint requires a valid Monday window")
    lock_path = repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH)
    try:
        with OperationLock(lock_path, "fingerprint_macro_planning_evidence"):
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
            wellness = load_wellness(repo)
            completions = load_completion_manifest(repo)
            publications = load_manifest(repo)
            payload = {
                "activities": [activity.model_dump(mode="json") for activity in activities],
                "wellness": [
                    wellness[local_date].model_dump(mode="json")
                    for local_date in sorted(wellness)
                    if local_date <= evidence_as_of_date
                ],
                "source_coverage_by_week": _coverage_evidence(
                    repo,
                    window_start=window_start,
                    evidence_as_of_date=evidence_as_of_date,
                ),
                "completion_matches": {
                    local_activity_id: match.model_dump(mode="json")
                    for local_activity_id, match in sorted(completions.matches.items())
                    if local_activity_id in active_activity_ids
                },
                "published_workouts": {
                    local_workout_id: publication.model_dump(mode="json")
                    for local_workout_id, publication in sorted(publications.workouts.items())
                    if window_start <= publication.occurrence_date <= evidence_as_of_date
                },
            }
    except (
        ActivityArchiveError,
        OperationLockError,
        OSError,
        ValueError,
    ) as exc:
        raise PlanOperationError(
            "Macro-planning evidence sources are unavailable or invalid"
        ) from exc
    return canonical_data_sha256(payload)
