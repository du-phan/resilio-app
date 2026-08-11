"""Presentation-neutral athlete-confirmed workout fulfillment API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from resilio.core.activity_sync.archive import ActivityArchiveError
from resilio.core.locking import OperationLockError
from resilio.core.planning.errors import PlanOperationError
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.service import (
    WorkoutFulfillmentError,
    WorkoutFulfillmentService,
)
from resilio.schemas.workout_fulfillment import (
    WorkoutFulfillmentCandidate,
    WorkoutFulfillmentCandidateDismissal,
    WorkoutFulfillmentRecord,
    WorkoutFulfillmentRevocation,
    WorkoutFulfillmentWeekStatus,
)


@dataclass(frozen=True)
class FulfillmentError:
    error_type: str
    message: str


FULFILLMENT_API_ERRORS = (
    ActivityArchiveError,
    OperationLockError,
    PlanOperationError,
    WorkoutFulfillmentError,
    OSError,
    ValueError,
)


def get_workout_fulfillment_candidates(
    *,
    local_activity_id: str,
) -> list[WorkoutFulfillmentCandidate] | FulfillmentError:
    try:
        return WorkoutFulfillmentService(RepositoryIO()).candidates(
            local_activity_id=local_activity_id
        )
    except FULFILLMENT_API_ERRORS as exc:
        return FulfillmentError("validation", str(exc))


def confirm_workout_fulfillment(
    *,
    local_activity_id: str,
    local_workout_id: str,
    candidate_sha256: str,
    athlete_confirmation_reference: str,
    coaching_rationale: str,
) -> WorkoutFulfillmentRecord | FulfillmentError:
    try:
        return WorkoutFulfillmentService(RepositoryIO()).confirm(
            local_activity_id=local_activity_id,
            local_workout_id=local_workout_id,
            candidate_sha256=candidate_sha256,
            athlete_confirmation_reference=athlete_confirmation_reference,
            coaching_rationale=coaching_rationale,
        )
    except FULFILLMENT_API_ERRORS as exc:
        return FulfillmentError("validation", str(exc))


def dismiss_workout_fulfillment_candidate(
    *,
    local_activity_id: str,
    local_workout_id: str,
    candidate_sha256: str,
    athlete_response_reference: str,
) -> WorkoutFulfillmentCandidateDismissal | FulfillmentError:
    try:
        return WorkoutFulfillmentService(RepositoryIO()).dismiss_candidate(
            local_activity_id=local_activity_id,
            local_workout_id=local_workout_id,
            candidate_sha256=candidate_sha256,
            athlete_response_reference=athlete_response_reference,
        )
    except FULFILLMENT_API_ERRORS as exc:
        return FulfillmentError("validation", str(exc))


def revoke_workout_fulfillment(
    *,
    local_activity_id: str,
    local_workout_id: str,
    reason: Literal[
        "activity_deleted",
        "activity_reclassified",
        "association_incorrect",
    ],
    athlete_confirmation_reference: str,
    coaching_rationale: str,
) -> WorkoutFulfillmentRevocation | FulfillmentError:
    try:
        return WorkoutFulfillmentService(RepositoryIO()).revoke(
            local_activity_id=local_activity_id,
            local_workout_id=local_workout_id,
            reason=reason,
            athlete_confirmation_reference=athlete_confirmation_reference,
            coaching_rationale=coaching_rationale,
        )
    except FULFILLMENT_API_ERRORS as exc:
        return FulfillmentError("validation", str(exc))


def get_workout_fulfillment_week_status(
    *,
    week_number: int,
) -> WorkoutFulfillmentWeekStatus | FulfillmentError:
    try:
        return WorkoutFulfillmentService(RepositoryIO()).week_status(week_number=week_number)
    except FULFILLMENT_API_ERRORS as exc:
        return FulfillmentError("validation", str(exc))
