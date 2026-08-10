"""Coverage-aware retrospective evidence for closing one training plan."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.activity_sync.evidence_identity import (
    activity_performance_evidence_sha256,
)
from resilio.core.coaching_context.exposure import activity_context
from resilio.core.coaching_context.service import build_coach_history
from resilio.core.planning.artifacts import (
    canonical_data_sha256,
    import_evidence_artifact,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.source_state import (
    coaching_evidence_source_sha256,
)
from resilio.core.planning.state_repository import load_planning_aggregate
from resilio.core.repository import RepositoryIO
from resilio.core.workout_publication.completions import (
    load_completion_manifest,
)
from resilio.schemas.activity import (
    RUNNING_SPORT_VALUES,
    ActivityStatus,
    CanonicalActivity,
)
from resilio.schemas.coaching import WeeklyCoachContext
from resilio.schemas.plan_history import (
    AthleteConfirmedGoalActivityEvidence,
    EvidenceArtifactReference,
    GoalOutcome,
    OwnedCompletionGoalEvidence,
)
from resilio.schemas.planning.plans import RaceMacroPlan
from resilio.schemas.planning_evidence import (
    CompactTrainingWeek,
    PlanCycleReview,
    PlanCycleTotals,
)

MAX_COMPACT_REVIEW_WEEKS = 52
MAX_DETAILED_REVIEW_WEEKS = 12
CONFIRMED_GOAL_STATUSES = {
    "completed",
    "did_not_start",
    "did_not_finish",
    "cancelled",
    "deferred",
    "not_applicable",
}


def _validated_timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("Cycle-review timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def _activity_by_id(
    repo: RepositoryIO,
    local_activity_id: str,
) -> CanonicalActivity:
    matches = [
        activity
        for activity in ActivityArchive(repo.resolve_path("data/activities")).load_all()
        if activity.status == ActivityStatus.ACTIVE
        and activity.local_activity_id == local_activity_id
    ]
    if len(matches) != 1:
        raise PlanOperationError(
            "Goal outcome evidence does not identify one active canonical activity"
        )
    return matches[0]


def _validate_goal_outcome(
    repo: RepositoryIO,
    outcome: GoalOutcome,
) -> CanonicalActivity | None:
    evidence = outcome.evidence
    if not isinstance(
        evidence,
        (
            OwnedCompletionGoalEvidence,
            AthleteConfirmedGoalActivityEvidence,
        ),
    ):
        return None
    activity = _activity_by_id(repo, evidence.local_activity_id)
    if activity_performance_evidence_sha256(activity) != evidence.performance_evidence_sha256:
        raise PlanOperationError(
            "Goal activity performance evidence changed after athlete confirmation"
        )
    if isinstance(evidence, OwnedCompletionGoalEvidence):
        completion = load_completion_manifest(repo).matches.get(evidence.local_activity_id)
        if completion is None or completion.workout_identity != evidence.workout_identity:
            raise PlanOperationError(
                "Owned goal evidence is not present in the completion manifest"
            )
    return activity


def confirmed_goal_outcome(
    repo: RepositoryIO,
    *,
    status: str,
    local_activity_id: str | None,
    athlete_confirmation_reference: str,
    notes: str | None = None,
) -> GoalOutcome:
    """Bind athlete-confirmed goal facts to exact canonical evidence."""
    if status not in CONFIRMED_GOAL_STATUSES:
        raise PlanOperationError(f"Unsupported confirmed goal status: {status}")
    activity_evidence_statuses = {"completed", "did_not_finish"}
    if status == "completed" and local_activity_id is None:
        raise PlanOperationError("Completed goal outcome requires one canonical activity ID")
    if status not in activity_evidence_statuses and local_activity_id is not None:
        raise PlanOperationError(
            "Only completed or did-not-finish outcomes may identify an activity"
        )
    if local_activity_id is None:
        return GoalOutcome.model_validate(
            {
                "status": status,
                "athlete_confirmation_reference": athlete_confirmation_reference,
                "notes": notes,
            }
        )
    activity = _activity_by_id(repo, local_activity_id)
    completion = load_completion_manifest(repo).matches.get(local_activity_id)
    evidence = (
        OwnedCompletionGoalEvidence(
            workout_identity=completion.workout_identity,
            local_activity_id=local_activity_id,
            performance_evidence_sha256=activity_performance_evidence_sha256(activity),
        )
        if completion is not None
        else AthleteConfirmedGoalActivityEvidence(
            local_activity_id=local_activity_id,
            performance_evidence_sha256=activity_performance_evidence_sha256(activity),
            athlete_confirmation_reference=(athlete_confirmation_reference),
        )
    )
    return GoalOutcome.model_validate(
        {
            "status": status,
            "evidence": evidence.model_dump(mode="json"),
            "athlete_confirmation_reference": athlete_confirmation_reference,
            "notes": notes,
        }
    )


def _compact_week(context: WeeklyCoachContext) -> CompactTrainingWeek:
    coverage = context.source_evidence_coverage
    limitation = context.adherence.reason
    if coverage.status in {"incomplete", "unavailable"}:
        limitation = coverage.reason or "Source activity coverage is not complete."
    return CompactTrainingWeek(
        week_start=context.week_start,
        week_end=context.week_end,
        evidence_as_of_date=context.as_of_date,
        adherence_status=context.adherence.status,
        due_planned_workout_count=context.adherence.due_workout_count,
        verified_completed_workout_count=(context.adherence.verified_completed_workout_count),
        due_unmatched_workout_count=context.adherence.due_unmatched_workout_count,
        actual_run_count=context.run_exposure.run_count,
        actual_run_distance_km=context.run_exposure.distance_km,
        actual_run_elapsed_duration_seconds=(context.run_exposure.elapsed_duration_seconds),
        actual_other_sport_exposure=context.other_sport_exposure_by_sport,
        source_coverage_status=coverage.status,
        limitation=limitation,
    )


def _cycle_totals(
    plan: RaceMacroPlan,
    compact_weeks: list[CompactTrainingWeek],
) -> PlanCycleTotals:
    distance_values = [
        week.actual_run_distance_km
        for week in compact_weeks
        if week.actual_run_distance_km is not None
    ]
    return PlanCycleTotals(
        planned_week_count=plan.total_weeks,
        reviewed_week_count=len(compact_weeks),
        planned_target_run_volume_meters=sum(week.target_run_volume_meters for week in plan.weeks),
        due_planned_workout_count=sum(week.due_planned_workout_count for week in compact_weeks),
        verified_completed_workout_count=sum(
            week.verified_completed_workout_count for week in compact_weeks
        ),
        due_unmatched_workout_count=sum(week.due_unmatched_workout_count for week in compact_weeks),
        actual_run_count=sum(week.actual_run_count for week in compact_weeks),
        actual_run_distance_km=(sum(distance_values) if distance_values else None),
        actual_run_elapsed_duration_seconds=sum(
            week.actual_run_elapsed_duration_seconds for week in compact_weeks
        ),
        incomplete_source_coverage_week_count=sum(
            week.source_coverage_status in {"incomplete", "unavailable"} for week in compact_weeks
        ),
    )


def _reviewed_weeks_and_source_sha256(
    repo: RepositoryIO,
    *,
    plan: RaceMacroPlan,
    plan_started: bool,
    effective_end_date: date,
    evidence_as_of_date: date,
) -> tuple[list[WeeklyCoachContext], list[str], str]:
    weeks: list[WeeklyCoachContext] = []
    limitations: list[str] = []
    source_window_start = evidence_as_of_date - timedelta(days=evidence_as_of_date.weekday())
    source_evidence_as_of_date = evidence_as_of_date
    if plan_started:
        reviewed_end = min(effective_end_date, plan.end_date)
        reviewed_week_count = ((reviewed_end - plan.start_date).days // 7) + 1
        retained_week_count = min(
            reviewed_week_count,
            MAX_COMPACT_REVIEW_WEEKS,
        )
        retained_start = plan.start_date + timedelta(
            weeks=reviewed_week_count - retained_week_count
        )
        source_window_start = retained_start
        source_evidence_as_of_date = reviewed_end
        if retained_week_count < reviewed_week_count:
            limitations.append("Compact weekly evidence retains the most recent 52 plan weeks.")
    source_state_sha256 = coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=source_evidence_as_of_date,
        evidence_window_start=source_window_start,
    )
    if plan_started:
        history = build_coach_history(
            repo,
            as_of_date=reviewed_end,
            week_count=retained_week_count,
        )
        weeks = [week for week in history.weeks if week.week_start >= retained_start]
    if (
        coaching_evidence_source_sha256(
            repo,
            evidence_as_of_date=source_evidence_as_of_date,
            evidence_window_start=source_window_start,
        )
        != source_state_sha256
    ):
        raise PlanOperationError("Training evidence changed while cycle review was being built")
    return weeks, limitations, source_state_sha256


def create_cycle_review(
    repo: RepositoryIO,
    *,
    effective_end_date: date,
    evidence_as_of_date: date,
    goal_outcome: GoalOutcome,
    generated_at_utc: datetime | None = None,
) -> EvidenceArtifactReference:
    """Persist the exact retrospective evidence required before plan closure."""
    state = load_planning_aggregate(repo)
    if state is None or state.active_plan is None:
        raise PlanOperationError("Cycle review requires one active plan")
    active_plan = state.active_plan
    plan = active_plan.plan
    if not isinstance(plan, RaceMacroPlan):
        raise PlanOperationError("Cycle review requires an active race macro plan")
    generation_timestamp = _validated_timestamp(generated_at_utc)
    training_timezone = ZoneInfo(plan.constraints_snapshot.training_timezone)
    plan_creation_local_date = plan.created_at_utc.astimezone(training_timezone).date()
    generation_local_date = generation_timestamp.astimezone(training_timezone).date()
    if effective_end_date < plan_creation_local_date:
        raise PlanOperationError("Effective plan end cannot predate plan creation")
    if effective_end_date > plan.end_date:
        raise PlanOperationError("Effective plan end cannot follow its horizon")
    if evidence_as_of_date < effective_end_date:
        raise PlanOperationError("Cycle-review evidence date cannot predate the effective plan end")
    if evidence_as_of_date > generation_local_date:
        raise PlanOperationError("Cycle-review evidence date cannot postdate review generation")
    is_general_fitness = str(plan.goal.type) == "general_fitness"
    if is_general_fitness != (goal_outcome.status == "not_applicable"):
        raise PlanOperationError("Only general-fitness plans use a not-applicable goal outcome")
    goal_activity = _validate_goal_outcome(repo, goal_outcome)
    goal_activity_summary = activity_context(goal_activity) if goal_activity is not None else None
    if goal_activity is not None:
        if str(goal_activity.sport) not in RUNNING_SPORT_VALUES:
            raise PlanOperationError("Goal outcome activity must be a canonical running activity")
        if not (plan.start_date <= goal_activity.occurrence.local_date <= effective_end_date):
            raise PlanOperationError("Goal outcome activity falls outside the effective plan cycle")
    plan_started = (
        active_plan.plan_approval is not None
        and plan.start_date <= evidence_as_of_date
        and effective_end_date >= plan.start_date
    )
    weeks, limitations, source_state_sha256 = _reviewed_weeks_and_source_sha256(
        repo,
        plan=plan,
        plan_started=plan_started,
        effective_end_date=effective_end_date,
        evidence_as_of_date=evidence_as_of_date,
    )
    compact_weeks = [_compact_week(week) for week in weeks]
    coverage_limited_week_count = sum(
        week.source_coverage_status != "complete" for week in compact_weeks
    )
    if coverage_limited_week_count:
        limitations.append(
            "Source coverage was incomplete, unavailable, or explicitly "
            f"excluded for {coverage_limited_week_count} reviewed week(s)."
        )
    review = PlanCycleReview(
        plan_id=plan.id,
        plan_revision_id=plan.plan_revision_id,
        plan_start_date=plan.start_date,
        planned_end_date=plan.end_date,
        effective_end_date=effective_end_date,
        evidence_as_of_date=evidence_as_of_date,
        generated_at_utc=generation_timestamp,
        plan_started=plan_started,
        active_plan_sha256=canonical_data_sha256(active_plan),
        goal_outcome=goal_outcome,
        goal_activity=goal_activity_summary,
        totals=_cycle_totals(plan, compact_weeks),
        compact_weeks=compact_weeks,
        recent_detailed_weeks=weeks[-MAX_DETAILED_REVIEW_WEEKS:],
        source_context_sha256=canonical_data_sha256(
            {
                "active_plan": active_plan.model_dump(mode="json"),
                "reviewed_weeks": [week.model_dump(mode="json") for week in weeks],
                "goal_outcome": goal_outcome.model_dump(mode="json"),
                "goal_activity": (
                    goal_activity_summary.model_dump(mode="json")
                    if goal_activity_summary is not None
                    else None
                ),
            }
        ),
        source_state_sha256=source_state_sha256,
        evidence_limitations=limitations,
    )
    return import_evidence_artifact(
        repo,
        review,
        artifact_type="cycle_review",
    )
