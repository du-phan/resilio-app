"""Weekly coaching-context application service."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.coaching_context.adherence import build_adherence_context
from resilio.core.coaching_context.coverage import build_sync_evidence_coverage
from resilio.core.coaching_context.exposure import (
    activity_context,
    intensity_context,
    other_sport_exposure,
    run_exposure,
)
from resilio.core.coaching_context.recovery import (
    build_recovery_context,
    latest_wellness,
    training_state,
)
from resilio.core.planning.adherence_evidence import AuthoritativeWorkout
from resilio.core.planning.integrity import (
    plan_skeleton_sha256,
    target_week_skeleton_sha256,
)
from resilio.core.planning.service import (
    ApprovedWorkoutWindow,
    load_approved_workouts_for_date_range,
    load_planning_aggregate,
    load_publishable_workouts,
)
from resilio.core.planning.source_state import coaching_evidence_source_sha256
from resilio.core.repository import RepositoryIO
from resilio.core.training_state_repository import load_wellness
from resilio.core.workout_fulfillment.evidence import fulfillment_was_available_as_of
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.manifest import load_manifest
from resilio.schemas.activity import ActivityStatus, CanonicalActivity
from resilio.schemas.coaching import (
    ApprovedVDOTContext,
    CoachHistoryContext,
    CoachingDataQuality,
    TargetWeekSkeletonContext,
    WeeklyCoachContext,
    WeekPlanningContext,
)
from resilio.schemas.planning.plans import BaselineAssessmentPlan, RaceMacroPlan
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest


def _planned_workouts_for_week(
    repo: RepositoryIO,
    *,
    week_start: date,
    week_end: date,
) -> ApprovedWorkoutWindow:
    return load_approved_workouts_for_date_range(
        repo,
        window_start=week_start,
        window_end=week_end,
    )


def _coaching_data_quality(
    activities: list[CanonicalActivity],
    *,
    source_zone_activity_ids: set[str],
    wellness_days_available: int,
) -> CoachingDataQuality:
    return CoachingDataQuality(
        activity_count=len(activities),
        activities_with_native_aerobic_load=sum(
            activity.aerobic_load is not None for activity in activities
        ),
        activities_with_zone_evidence=len(source_zone_activity_ids),
        activities_with_native_analysis=sum(
            activity.native_analysis is not None for activity in activities
        ),
        activities_with_polarization_observation=sum(
            activity.native_analysis is not None
            and activity.native_analysis.polarization is not None
            for activity in activities
        ),
        activities_with_linked_polarization_evidence=sum(
            activity.native_analysis is not None
            and activity.native_analysis.polarization is not None
            and activity.native_analysis.polarization.evidence_status
            == "linked_to_primary_zone_evidence"
            for activity in activities
        ),
        activities_with_decoupling_observation=sum(
            activity.native_analysis is not None
            and activity.native_analysis.aerobic_decoupling is not None
            for activity in activities
        ),
        activities_with_known_decoupling_basis=sum(
            activity.native_analysis is not None
            and activity.native_analysis.aerobic_decoupling is not None
            and (activity.native_analysis.aerobic_decoupling.coupling_basis != "provider_unknown")
            for activity in activities
        ),
        wellness_days_available=wellness_days_available,
    )


def _adherence_activities(
    *,
    archive: ActivityArchive,
    exposed_activities: list[CanonicalActivity],
    planned_workouts: list[AuthoritativeWorkout],
    fulfillment_manifest: WorkoutFulfillmentManifest,
    as_of_date: date,
) -> list[CanonicalActivity]:
    activities = list(exposed_activities)
    loaded_activity_ids = {activity.local_activity_id for activity in activities}
    planned_identity_keys = {
        (
            workout.identity.plan_id,
            workout.identity.plan_revision_id,
            workout.identity.week_number,
            workout.identity.local_workout_id,
        )
        for workout in planned_workouts
    }
    for fulfillment in fulfillment_manifest.fulfillments.values():
        if (
            not fulfillment_was_available_as_of(
                fulfillment,
                as_of_date=as_of_date,
            )
            or (
                fulfillment.workout_identity.plan_id,
                fulfillment.workout_identity.plan_revision_id,
                fulfillment.workout_identity.week_number,
                fulfillment.workout_identity.local_workout_id,
            )
            not in planned_identity_keys
            or fulfillment.local_activity_id in loaded_activity_ids
        ):
            continue
        activity = archive.load(fulfillment.local_activity_id)
        if activity is not None:
            activities.append(activity)
            loaded_activity_ids.add(activity.local_activity_id)
    return activities


def build_weekly_coach_context(
    repo: RepositoryIO,
    *,
    week_start: date,
    as_of_date: date,
) -> WeeklyCoachContext:
    """Build a read-only Monday-Sunday context without future-data leakage."""
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    if as_of_date < week_start:
        raise ValueError("as_of_date cannot precede week start")
    week_end = week_start + timedelta(days=6)
    exposure_end_date = min(as_of_date, week_end)
    archive = ActivityArchive(repo.resolve_path("data/activities"))
    activities = sorted(
        (
            activity
            for activity in archive.load_all()
            if activity.status == ActivityStatus.ACTIVE
            and week_start <= activity.occurrence.local_date <= exposure_end_date
        ),
        key=lambda activity: (
            activity.occurrence.local_date,
            activity.occurrence.start_time_local
            or activity.occurrence.start_time_utc
            or activity.audit.imported_at_utc,
            activity.local_activity_id,
        ),
    )
    wellness = load_wellness(repo)
    latest = latest_wellness(wellness, exposure_end_date)
    recovery = build_recovery_context(
        wellness,
        as_of_date=exposure_end_date,
    )
    planned_workouts = _planned_workouts_for_week(
        repo,
        week_start=week_start,
        week_end=week_end,
    )
    fulfillment_manifest = load_fulfillment_manifest(repo)
    adherence_activities = _adherence_activities(
        archive=archive,
        exposed_activities=activities,
        planned_workouts=planned_workouts.workouts,
        fulfillment_manifest=fulfillment_manifest,
        as_of_date=as_of_date,
    )
    adherence = build_adherence_context(
        workouts=planned_workouts.workouts,
        activities=adherence_activities,
        fulfillment_manifest=fulfillment_manifest,
        as_of_date=as_of_date,
        publication_manifest=load_manifest(repo),
        status=planned_workouts.status,
        reason=planned_workouts.reason,
    )
    intensity = intensity_context(
        activities,
        due_planned_low_intensity_duration_seconds=(
            adherence.due_planned_low_intensity_duration_seconds
        ),
        due_planned_moderate_intensity_duration_seconds=(
            adherence.due_planned_moderate_intensity_duration_seconds
        ),
        due_planned_high_intensity_duration_seconds=(
            adherence.due_planned_high_intensity_duration_seconds
        ),
    )
    return WeeklyCoachContext(
        week_start=week_start,
        week_end=week_end,
        as_of_date=as_of_date,
        training_state=training_state(latest),
        recovery=recovery,
        activities=[activity_context(activity) for activity in activities],
        run_exposure=run_exposure(activities),
        other_sport_exposure_by_sport=other_sport_exposure(activities),
        adherence=adherence,
        intensity=intensity,
        data_quality=_coaching_data_quality(
            activities,
            source_zone_activity_ids={
                item.local_activity_id for item in intensity.source_zone_evidence
            },
            wellness_days_available=recovery.wellness_days_available,
        ),
        source_evidence_coverage=build_sync_evidence_coverage(
            repo,
            requested_window_start=week_start,
            requested_window_end=exposure_end_date,
        ),
    )


def build_coach_history(
    repo: RepositoryIO,
    *,
    as_of_date: date,
    week_count: int,
) -> CoachHistoryContext:
    """Build contiguous weekly evidence ending in the as-of target week."""
    if week_count < 1 or week_count > 52:
        raise ValueError("week_count must be between 1 and 52")
    target_week_start = as_of_date - timedelta(days=as_of_date.weekday())
    evidence_window_start = target_week_start - timedelta(weeks=week_count - 1)
    weeks = [
        build_weekly_coach_context(
            repo,
            week_start=evidence_window_start + timedelta(weeks=index),
            as_of_date=as_of_date,
        )
        for index in range(week_count)
    ]
    return CoachHistoryContext(
        as_of_date=as_of_date,
        target_week_start=target_week_start,
        target_week_end=target_week_start + timedelta(days=6),
        evidence_window_start=evidence_window_start,
        evidence_window_end=as_of_date,
        requested_week_count=week_count,
        weeks=weeks,
    )


def build_week_planning_context(
    repo: RepositoryIO,
    *,
    week_number: int,
    evidence_as_of_date: date,
    history_week_count: int,
    current_local_date: date | None = None,
    generated_at_utc: datetime | None = None,
) -> WeekPlanningContext:
    """Build future planning inputs without pretending the target week occurred."""
    today = current_local_date or date.today()
    if evidence_as_of_date > today:
        raise ValueError("evidence_as_of_date cannot be in the future")
    generation_timestamp = generated_at_utc or datetime.now(timezone.utc)
    if generation_timestamp.tzinfo is None or generation_timestamp.utcoffset() is None:
        raise ValueError("generated_at_utc must be timezone-aware")
    generation_timestamp = generation_timestamp.astimezone(timezone.utc)
    evidence_window_start = (
        evidence_as_of_date - timedelta(days=evidence_as_of_date.weekday())
    ) - timedelta(weeks=history_week_count - 1)
    source_state_sha256 = coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=evidence_as_of_date,
        evidence_window_start=evidence_window_start,
    )
    load_publishable_workouts(repo)
    state = load_planning_aggregate(repo)
    if state is None or state.active_plan is None or state.active_plan.plan_approval is None:
        raise ValueError("An approved current plan is required")
    matching = [week for week in state.active_plan.plan.weeks if week.week_number == week_number]
    if len(matching) != 1:
        raise ValueError(f"Week {week_number} does not exist in the current plan")
    target = matching[0]
    plan = state.active_plan.plan
    context = WeekPlanningContext(
        generated_at_utc=generation_timestamp,
        source_state_sha256=source_state_sha256,
        evidence_as_of_date=evidence_as_of_date,
        target_week=TargetWeekSkeletonContext(
            plan_kind=plan.kind,
            plan_id=plan.id,
            plan_revision_id=plan.plan_revision_id,
            plan_skeleton_sha256=plan_skeleton_sha256(plan),
            target_week_skeleton_sha256=target_week_skeleton_sha256(target),
            week_number=target.week_number,
            phase=str(target.phase),
            start_date=target.start_date,
            end_date=target.end_date,
            target_run_volume_meters=target.target_run_volume_meters,
            workout_structure_hints=target.workout_structure_hints,
            is_recovery_week=target.is_recovery_week,
        ),
        recent_history=build_coach_history(
            repo,
            as_of_date=evidence_as_of_date,
            week_count=history_week_count,
        ),
        approved_vdot=(
            ApprovedVDOTContext(
                approval_id=state.active_vdot_approval.approval_id,
                approved_vdot=state.active_vdot_approval.approved_vdot,
                evidence_type=str(state.active_vdot_approval.evidence_type),
            )
            if isinstance(plan, RaceMacroPlan) and state.active_vdot_approval is not None
            else None
        ),
        methodology=(plan.methodology if isinstance(plan, RaceMacroPlan) else None),
        assessment_reasons=(
            plan.assessment_reasons if isinstance(plan, BaselineAssessmentPlan) else []
        ),
        benchmark_intent=(
            plan.benchmark_intent if isinstance(plan, BaselineAssessmentPlan) else None
        ),
        temporary_schedule_constraints=(
            plan.temporary_schedule_constraints if isinstance(plan, BaselineAssessmentPlan) else []
        ),
        constraints=plan.constraints_snapshot,
    )
    if (
        coaching_evidence_source_sha256(
            repo,
            evidence_as_of_date=evidence_as_of_date,
            evidence_window_start=evidence_window_start,
        )
        != source_state_sha256
    ):
        raise ValueError("Training evidence changed while weekly context was built")
    if load_planning_aggregate(repo) != state:
        raise ValueError("Planning state changed while weekly context was built")
    return context
