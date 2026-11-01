"""Protect elapsed and fulfilled prescriptions across exact weekly revisions."""

from datetime import datetime

from resilio.canonical import canonical_data_sha256
from resilio.core.planning.adherence_evidence import (
    AuthoritativeWorkout,
    applied_workout_authority_history,
    resolve_approved_workouts_for_date_range,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.schedule import schedule_authority_deadline_utc
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.evidence import assert_fulfillment_authority_is_current
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.schemas.approvals import PlanningState
from resilio.schemas.planning.applications import WeekApplication


def assert_historical_prescriptions_unchanged(
    repo: RepositoryIO,
    state: PlanningState,
    application: WeekApplication,
    *,
    timestamp: datetime,
) -> None:
    """Reprove history even when a macro amendment retired the prior week.

    Authority at each elapsed deadline selects the relevant snapshot; an older
    prescription replaced while still upcoming must not freeze the newer one.
    Fulfillments also protect early execution before its scheduled deadline.
    """
    active = state.active_plan
    assert active is not None
    week = next(w for w in active.plan.weeks if w.week_number == application.week_number)
    proposed = {workout.id: workout for workout in application.running_workouts}
    protected_ids: set[str] = set()
    history = resolve_approved_workouts_for_date_range(
        state, window_start=week.start_date, window_end=week.end_date
    )
    if history.status == "unavailable" and history.reason != (
        "no_applied_workouts_cover_requested_window"
    ):
        raise PlanOperationError(f"Historical workout authority is unavailable: {history.reason}")

    for fulfillment in load_fulfillment_manifest(repo).fulfillments.values():
        identity = fulfillment.workout_identity
        if (
            identity.plan_id != active.plan.id
            or identity.plan_revision_id != active.plan.plan_revision_id
            or identity.week_number != week.week_number
        ):
            continue
        workout = proposed.get(identity.local_workout_id)
        if workout is None or canonical_data_sha256(workout) != (
            fulfillment.workout_prescription_sha256
        ):
            raise PlanOperationError(
                "A weekly replacement cannot remove or alter a fulfilled workout"
            )
        authority = AuthoritativeWorkout(
            identity=identity,
            prescription=workout,
            applied_week_approval_id=fulfillment.applied_week_approval_id,
            applied_running_workouts_sha256=fulfillment.applied_running_workouts_sha256,
            schedule_timezone=active.plan.constraints_snapshot.training_timezone,
            applied_authority_history=applied_workout_authority_history(
                active.applied_week_revisions,
                week_number=week.week_number,
                local_workout_id=workout.id,
            ),
        )
        # Only retained snapshots prove authority; the proposed prescription is
        # not yet applied and cannot supply a self-asserted fulfillment match.
        if not any(
            item.applied_week_approval_id == fulfillment.applied_week_approval_id
            and item.applied_running_workouts_sha256 == fulfillment.applied_running_workouts_sha256
            and item.workout_prescription_sha256 == fulfillment.workout_prescription_sha256
            and item.schedule_timezone == fulfillment.schedule_timezone
            and item.scheduled_local_date == fulfillment.scheduled_local_date
            for item in authority.applied_authority_history
        ):
            raise PlanOperationError("Fulfilled workout has no retained applied-week authority")
        try:
            assert_fulfillment_authority_is_current(fulfillment, authority)
        except ValueError as exc:
            raise PlanOperationError(str(exc)) from exc
        protected_ids.add(workout.id)

    for authority in history.workouts:
        workout = authority.prescription
        if (
            schedule_authority_deadline_utc(workout, training_timezone=authority.schedule_timezone)
            > timestamp
        ):
            continue
        candidate = proposed.get(workout.id)
        if candidate is None or canonical_data_sha256(candidate) != canonical_data_sha256(workout):
            raise PlanOperationError(
                "A weekly replacement cannot remove or alter an elapsed workout"
            )
        protected_ids.add(workout.id)

    for workout in application.running_workouts:
        if (
            schedule_authority_deadline_utc(
                workout, training_timezone=active.plan.constraints_snapshot.training_timezone
            )
            <= timestamp
            and workout.id not in protected_ids
        ):
            raise PlanOperationError("A weekly replacement cannot add a backdated workout")
