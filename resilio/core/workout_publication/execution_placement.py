"""Resolve athlete-confirmed execution dates for remote calendar placement."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.evidence import (
    assert_fulfillment_authority_is_current,
    assert_fulfillment_is_usable,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.policy import PublicationSafetyError
from resilio.schemas.plan_history import PlanWorkoutIdentity

WorkoutIdentityKey = tuple[str, str, int, str]


def _identity_key(identity: PlanWorkoutIdentity) -> WorkoutIdentityKey:
    return (
        identity.plan_id,
        identity.plan_revision_id,
        identity.week_number,
        identity.local_workout_id,
    )


def confirmed_execution_placement_dates(
    repo: RepositoryIO,
    workouts: list[AuthoritativeWorkout],
) -> dict[str, date]:
    """Return exact provider dates authorized by current athlete confirmations."""
    manifest = load_fulfillment_manifest(repo)
    authorities_by_identity = {
        _identity_key(workout.identity): workout for workout in workouts
    }
    activities_by_id = {
        activity.local_activity_id: activity
        for activity in ActivityArchive(repo.resolve_path("data/activities")).load_all()
    }
    placements: dict[str, date] = {}
    for fulfillment in manifest.fulfillments.values():
        if fulfillment.athlete_confirmation is None:
            continue
        authority = authorities_by_identity.get(_identity_key(fulfillment.workout_identity))
        if authority is None:
            continue
        activity = activities_by_id.get(fulfillment.local_activity_id)
        if activity is None:
            raise PublicationSafetyError(
                "Athlete-confirmed fulfillment activity is unavailable for calendar placement"
            )
        try:
            assert_fulfillment_authority_is_current(fulfillment, authority)
            assert_fulfillment_is_usable(fulfillment, activity, manifest)
        except ValueError as exc:
            raise PublicationSafetyError(str(exc)) from exc
        execution_local_date = (
            activity.occurrence.start_time_utc.astimezone(
                ZoneInfo(fulfillment.schedule_timezone)
            ).date()
            if activity.occurrence.start_time_utc is not None
            else activity.occurrence.local_date
        )
        if execution_local_date != fulfillment.execution_local_date:
            raise PublicationSafetyError(
                "Fulfillment execution date does not match current canonical activity evidence"
            )
        placements[authority.identity.local_workout_id] = execution_local_date
    return placements
