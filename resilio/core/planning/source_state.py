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
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest

DEFAULT_RECENT_EVIDENCE_WEEK_COUNT = 12


def _evidence_window_start(evidence_as_of_date: date) -> date:
    target_week_start = evidence_as_of_date - timedelta(days=evidence_as_of_date.weekday())
    return target_week_start - timedelta(weeks=DEFAULT_RECENT_EVIDENCE_WEEK_COUNT - 1)


def source_coverage_evidence(
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


def coaching_evidence_source_sha256_unlocked(
    repo: RepositoryIO,
    *,
    evidence_as_of_date: date,
    evidence_window_start: date | None = None,
    fulfillment_manifest: WorkoutFulfillmentManifest | None = None,
    publication_manifest: PublicationManifest | None = None,
) -> str:
    """Hash one exact source slice while the caller owns the activity lock."""
    from resilio.core.workout_fulfillment.evidence import fulfillment_was_available_as_of
    from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
    from resilio.core.workout_publication.manifest import load_manifest

    window_start = evidence_window_start or _evidence_window_start(evidence_as_of_date)
    if window_start.weekday() != 0 or window_start > evidence_as_of_date:
        raise PlanOperationError("Coaching evidence fingerprint requires a valid Monday window")
    context_window_end = evidence_as_of_date + timedelta(days=6 - evidence_as_of_date.weekday())
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
    wellness = load_wellness(repo)
    fulfillments = fulfillment_manifest or load_fulfillment_manifest(repo)
    publications = publication_manifest or load_manifest(repo)
    relevant_fulfillments = {
        local_activity_id: record
        for local_activity_id, record in fulfillments.fulfillments.items()
        if window_start <= record.scheduled_local_date <= context_window_end
        and fulfillment_was_available_as_of(
            record,
            as_of_date=evidence_as_of_date,
        )
    }
    relevant_historical_fulfillments = {
        local_activity_id: record
        for local_activity_id, record in fulfillments.historical_legacy_fulfillments.items()
        if window_start <= record.scheduled_local_date <= context_window_end
        and record.execution_local_date <= evidence_as_of_date
    }
    linked_activity_ids = (
        set(relevant_fulfillments) | set(relevant_historical_fulfillments)
    ).difference(active_activity_ids)
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
        if activity_id in relevant_fulfillments or activity_id in relevant_historical_fulfillments
    }
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
            local_activity_id: record.model_dump(mode="json")
            for local_activity_id, record in sorted(relevant_fulfillments.items())
        },
        "historical_workout_fulfillments": {
            local_activity_id: record.model_dump(mode="json")
            for local_activity_id, record in sorted(relevant_historical_fulfillments.items())
        },
        "unresolved_fulfillment_conflicts": {
            local_activity_id: conflict.model_dump(mode="json")
            for local_activity_id, conflict in sorted(relevant_conflicts.items())
        },
        "published_workouts": {
            local_workout_id: publication.model_dump(mode="json")
            for local_workout_id, publication in sorted(publications.workouts.items())
            if window_start <= publication.occurrence_date <= context_window_end
        },
        "historical_fulfillment_event_retirements": [
            retirement.model_dump(mode="json")
            for retirement in publications.historical_fulfillment_event_retirements
            if window_start <= retirement.publication.occurrence_date <= context_window_end
        ],
        "historical_fulfillment_pending_retirements": [
            retirement.model_dump(mode="json")
            for retirement in publications.historical_fulfillment_pending_retirements
            if window_start <= retirement.pending_publication.occurrence_date <= context_window_end
        ],
        "historical_workout_publications": {
            local_workout_id: publication.model_dump(mode="json")
            for local_workout_id, publication in sorted(
                publications.historical_legacy_workouts.items()
            )
            if window_start <= publication.occurrence_date <= context_window_end
        },
    }
    return canonical_data_sha256(payload)


def coaching_evidence_source_sha256(
    repo: RepositoryIO,
    *,
    evidence_as_of_date: date,
    evidence_window_start: date | None = None,
) -> str:
    """Hash the exact mutable source slice represented by recent context."""
    lock_path = repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH)
    try:
        with OperationLock(lock_path, "fingerprint_macro_planning_evidence"):
            return coaching_evidence_source_sha256_unlocked(
                repo,
                evidence_as_of_date=evidence_as_of_date,
                evidence_window_start=evidence_window_start,
            )
    except (
        ActivityArchiveError,
        OperationLockError,
        OSError,
        ValueError,
    ) as exc:
        raise PlanOperationError(
            "Macro-planning evidence sources are unavailable or invalid"
        ) from exc
