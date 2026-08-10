"""Evidence binding and other-sport coverage for exact weekly run proposals."""

from collections import defaultdict

from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    load_evidence_artifact,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.integrity import (
    plan_skeleton_sha256,
    target_week_skeleton_sha256,
)
from resilio.core.planning.source_state import coaching_evidence_source_sha256
from resilio.core.repository import RepositoryIO
from resilio.schemas.activity import is_running_sport
from resilio.schemas.coaching import WeekPlanningContext
from resilio.schemas.planning.applications import WeekApplication
from resilio.schemas.planning.plans import TrainingPlan
from resilio.schemas.planning.weeks import WeekPlan


def _observed_activity_ids_by_sport(
    context: WeekPlanningContext,
) -> dict[str, set[str]]:
    observed: dict[str, set[str]] = defaultdict(set)
    for week in context.recent_history.weeks:
        for activity in week.activities:
            if not is_running_sport(activity.sport):
                observed[activity.sport].add(activity.local_activity_id)
    return dict(observed)


def _validate_other_sport_considerations(
    application: WeekApplication,
    context: WeekPlanningContext,
) -> None:
    observed_ids_by_sport = _observed_activity_ids_by_sport(context)
    expected_sports = {
        expectation.sport_name
        for expectation in context.constraints.athlete_managed_sport_expectations
    }
    required_sports = expected_sports | set(observed_ids_by_sport)
    considerations_by_sport = {
        consideration.sport_name: consideration
        for consideration in application.other_sport_considerations
    }
    considered_sports = set(considerations_by_sport)
    if considered_sports != required_sports:
        missing = sorted(required_sports - considered_sports)
        unexpected = sorted(considered_sports - required_sports)
        raise PlanOperationError(
            "Other-sport considerations do not cover the exact planning context "
            f"(missing={missing}, unexpected={unexpected})"
        )
    for sport_name, consideration in considerations_by_sport.items():
        observed_ids = observed_ids_by_sport.get(sport_name, set())
        considered_ids = set(consideration.recent_activity_ids)
        if considered_ids != observed_ids:
            missing = sorted(observed_ids - considered_ids)
            unexpected = sorted(considered_ids - observed_ids)
            raise PlanOperationError(
                f"Consideration for {sport_name} does not reference its exact recent "
                f"activities (missing={missing}, unexpected={unexpected})"
            )


def validate_week_planning_evidence(
    repo: RepositoryIO,
    *,
    plan: TrainingPlan,
    target_week: WeekPlan,
    application: WeekApplication,
) -> WeekPlanningContext:
    """Prove that a weekly proposal covers its immutable, still-current evidence."""
    try:
        context = load_evidence_artifact(
            repo,
            application.planning_context_reference,
            WeekPlanningContext,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    target = context.target_week
    if (
        target.plan_id != plan.id
        or target.plan_revision_id != plan.plan_revision_id
        or target.week_number != target_week.week_number
        or target.plan_skeleton_sha256 != plan_skeleton_sha256(plan)
        or target.target_week_skeleton_sha256 != target_week_skeleton_sha256(target_week)
    ):
        raise PlanOperationError(
            "Week-planning context does not match the current plan-week skeleton"
        )
    current_source_sha256 = coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=context.evidence_as_of_date,
        evidence_window_start=context.recent_history.evidence_window_start,
    )
    if current_source_sha256 != context.source_state_sha256:
        raise PlanOperationError(
            "Training evidence changed after the week-planning context was created"
        )
    _validate_other_sport_considerations(application, context)
    return context
