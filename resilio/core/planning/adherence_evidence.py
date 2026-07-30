"""Resolve exact historical workout authority for adherence analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from resilio.core.planning.integrity import (
    applied_workout_sha256,
    macro_skeleton_sha256,
    target_week_skeleton_sha256,
)
from resilio.core.planning.schedule import WorkoutScheduleError, scheduled_start_utc
from resilio.schemas.approvals import (
    AppliedWeekRevision,
    MacroApproval,
    PlanningState,
)
from resilio.schemas.plan import MasterPlan, WorkoutPrescription


@dataclass(frozen=True)
class ApprovedWorkoutWindow:
    status: Literal["available", "no_plan", "unavailable"]
    workouts: list[WorkoutPrescription]
    reason: str | None = None


@dataclass(frozen=True)
class _RevisionAuthority:
    plan: MasterPlan
    macro_approval: MacroApproval | None
    applied_week_revisions: list[AppliedWeekRevision]
    retired_at_utc: datetime | None


@dataclass(frozen=True)
class _RevisionResolution:
    overlaps: bool
    workouts_by_date: dict[date, tuple[str, list[WorkoutPrescription]]]
    unresolved_reason: str | None = None
    invalid_reason: str | None = None


def _unavailable(reason: str) -> ApprovedWorkoutWindow:
    return ApprovedWorkoutWindow(
        status="unavailable",
        workouts=[],
        reason=reason,
    )


def _macro_approval_invalid_reason(
    plan: MasterPlan,
    macro_approval: MacroApproval,
) -> str | None:
    if (
        macro_approval.plan_id != plan.id
        or macro_approval.macro_revision_id != plan.macro_revision_id
        or macro_approval.vdot_approval_id != plan.vdot_approval_id
        or macro_approval.macro_skeleton_sha256 != macro_skeleton_sha256(plan)
    ):
        return "approved_macro_skeleton_changed"
    return None


def _collect_authoritative_workouts(
    revision: _RevisionAuthority,
    *,
    applied_revisions: list[AppliedWeekRevision],
    window_start: date,
    window_end: date,
) -> _RevisionResolution:
    plan = revision.plan
    macro_approval = revision.macro_approval
    assert macro_approval is not None
    plan_weeks = {week.week_number: week for week in plan.weeks}
    workouts_by_date: dict[date, tuple[str, list[WorkoutPrescription]]] = {}
    for applied_revision in applied_revisions:
        week = applied_revision.applied_week_snapshot
        plan_week = plan_weeks.get(applied_revision.week_number)
        if plan_week is None or target_week_skeleton_sha256(
            week
        ) != target_week_skeleton_sha256(plan_week):
            return _RevisionResolution(
                True,
                {},
                invalid_reason=(
                    f"week_{applied_revision.week_number}_skeleton_changed"
                ),
            )
        if (
            applied_revision.plan_id != plan.id
            or applied_revision.macro_revision_id != plan.macro_revision_id
            or applied_revision.applied_workout_sha256
            != applied_workout_sha256(week)
        ):
            return _RevisionResolution(
                True,
                {},
                invalid_reason=(
                    f"week_{applied_revision.week_number}_changed_after_application"
                ),
            )
        authority_id = (
            f"{plan.id}:{plan.macro_revision_id}:"
            f"{applied_revision.approval_id}"
        )
        for workout in week.workouts:
            if not window_start <= workout.date <= window_end:
                continue
            try:
                scheduled_at_utc = scheduled_start_utc(
                    workout,
                    training_timezone=applied_revision.schedule_timezone,
                )
            except WorkoutScheduleError:
                return _RevisionResolution(
                    True,
                    {},
                    invalid_reason=(
                        f"week_{applied_revision.week_number}_schedule_is_invalid"
                    ),
                )
            if macro_approval.approved_at_utc > scheduled_at_utc:
                continue
            if applied_revision.weekly_approved_at_utc > scheduled_at_utc:
                continue
            if applied_revision.applied_at_utc > scheduled_at_utc:
                continue
            if (
                applied_revision.invalidated_at_utc is not None
                and applied_revision.invalidated_at_utc <= scheduled_at_utc
            ):
                continue
            if (
                revision.retired_at_utc is not None
                and revision.retired_at_utc <= scheduled_at_utc
            ):
                continue
            existing = workouts_by_date.setdefault(
                workout.date,
                (authority_id, []),
            )
            existing[1].append(workout)
    return _RevisionResolution(True, workouts_by_date)


def _resolve_revision(
    revision: _RevisionAuthority,
    *,
    window_start: date,
    window_end: date,
) -> _RevisionResolution:
    plan = revision.plan
    if plan.end_date < window_start or plan.start_date > window_end:
        return _RevisionResolution(False, {})
    overlapping_populated_weeks = [
        week
        for week in plan.weeks
        if week.workouts and week.end_date >= window_start and week.start_date <= window_end
    ]
    overlapping_applied_revisions = [
        applied_revision
        for applied_revision in revision.applied_week_revisions
        if applied_revision.applied_week_snapshot.end_date >= window_start
        and applied_revision.applied_week_snapshot.start_date <= window_end
    ]
    macro_approval = revision.macro_approval
    if macro_approval is None:
        reason = "overlapping_macro_plan_is_not_approved"
        return _RevisionResolution(
            True,
            {},
            unresolved_reason=(
                reason
                if not overlapping_populated_weeks and not overlapping_applied_revisions
                else None
            ),
            invalid_reason=(
                reason
                if overlapping_populated_weeks or overlapping_applied_revisions
                else None
            ),
        )
    if invalid_reason := _macro_approval_invalid_reason(plan, macro_approval):
        return _RevisionResolution(
            True,
            {},
            invalid_reason=invalid_reason,
        )
    revision_week_numbers = {
        applied_revision.week_number
        for applied_revision in overlapping_applied_revisions
    }
    for week in overlapping_populated_weeks:
        if week.week_number not in revision_week_numbers:
            return _RevisionResolution(
                True,
                {},
                invalid_reason=(f"week_{week.week_number}_approval_is_missing"),
            )
    return _collect_authoritative_workouts(
        revision,
        applied_revisions=overlapping_applied_revisions,
        window_start=window_start,
        window_end=window_end,
    )


def resolve_approved_workouts_for_date_range(
    state: PlanningState,
    *,
    window_start: date,
    window_end: date,
) -> ApprovedWorkoutWindow:
    """Select exact, temporally applicable approval authority by workout date."""
    revisions = [
        *[
            _RevisionAuthority(
                plan=retired.plan,
                macro_approval=retired.macro_approval,
                applied_week_revisions=retired.applied_week_revisions,
                retired_at_utc=retired.retired_at_utc,
            )
            for retired in state.retired_plan_revisions
        ],
        *(
            [
                _RevisionAuthority(
                    plan=state.current_plan,
                    macro_approval=state.macro_approval,
                    applied_week_revisions=state.applied_week_revisions,
                    retired_at_utc=None,
                )
            ]
            if state.current_plan is not None
            else []
        ),
    ]
    overlapping_plan_found = False
    unresolved_reasons: list[str] = []
    workouts_by_date: dict[date, tuple[str, list[WorkoutPrescription]]] = {}
    for revision in revisions:
        resolution = _resolve_revision(
            revision,
            window_start=window_start,
            window_end=window_end,
        )
        if not resolution.overlaps:
            continue
        overlapping_plan_found = True
        if resolution.invalid_reason is not None:
            return _unavailable(resolution.invalid_reason)
        if resolution.unresolved_reason is not None:
            unresolved_reasons.append(resolution.unresolved_reason)
        for workout_date, authority in resolution.workouts_by_date.items():
            existing = workouts_by_date.get(workout_date)
            if existing is not None and existing[0] != authority[0]:
                return _unavailable("competing_approved_plan_authorities")
            if existing is None:
                workouts_by_date[workout_date] = authority
            else:
                existing[1].extend(authority[1])
    if not overlapping_plan_found:
        return ApprovedWorkoutWindow(
            status="no_plan",
            workouts=[],
            reason="no_plan_covers_requested_window",
        )
    workouts = [
        workout for _, date_workouts in workouts_by_date.values() for workout in date_workouts
    ]
    if workouts:
        workout_ids = [workout.id for workout in workouts]
        if len(workout_ids) != len(set(workout_ids)):
            return _unavailable("approved_workout_identity_conflict")
        return ApprovedWorkoutWindow(
            status="available",
            workouts=sorted(
                workouts,
                key=lambda workout: (workout.date, workout.id),
            ),
        )
    return _unavailable(
        unresolved_reasons[0]
        if unresolved_reasons
        else "no_applied_workouts_cover_requested_window"
    )
