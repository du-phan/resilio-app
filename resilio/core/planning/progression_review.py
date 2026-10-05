"""Required evidence-linked coach review, shared by authoring and consuming gates."""

from datetime import datetime
from zoneinfo import ZoneInfo

from resilio.canonical import canonical_data_sha256
from resilio.core.coaching_context.running_progression import (
    build_running_progression_evidence_unlocked,
)
from resilio.core.planning.artifacts import load_evidence_artifact
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.progression_assessment import (
    ProgressionCandidate,
    ProgressionKind,
    build_progression_assessment,
    candidate_sha256,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.coaching import WeekPlanningContext
from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning.constraints import PlanningConstraintsSnapshot
from resilio.schemas.planning.weeks import WeekPlan
from resilio.schemas.running_progression import (
    ProgressionAssessmentV1,
    RunProgressionBindingV1,
    RunProgressionReviewV1,
)


def validate_review(
    assessment: ProgressionAssessmentV1,
    review: RunProgressionReviewV1,
) -> bool:
    """Return readiness; revise/defer and weekly conditional decisions remain proposals."""
    if (
        review.candidate_sha256 != assessment.candidate_sha256
        or review.evidence_sha256 != canonical_data_sha256(assessment.evidence)
    ):
        raise PlanOperationError(
            "Progression review does not bind the exact candidate and evidence"
        )
    if set(review.acknowledged_limitations) != set(assessment.evidence.limitations):
        raise PlanOperationError("Progression review must acknowledge every evidence limitation")
    expected_keys = {f"week.{item.week_number}" for item in assessment.weeks}
    expected_keys.update(item.key for item in assessment.sessions)
    judgments = {item.key: item for item in review.judgments}
    if len(judgments) != len(review.judgments) or set(judgments) != expected_keys:
        raise PlanOperationError(
            "Progression review must cover every affected week and session exactly"
        )
    available_ids = {item.activity_id for item in assessment.evidence.recordings}
    if set(review.reasoning) != {item.reasoning_id for item in review.judgments}:
        raise PlanOperationError(
            "Review reasoning must be referenced exactly without orphaned entries"
        )
    for reasoning in review.reasoning.values():
        if not set(reasoning.evidence_activity_ids).issubset(available_ids):
            raise PlanOperationError("Progression judgment cites an unavailable running activity")
    for judgment in review.judgments:
        if (
            not assessment.minimum_run_days_per_week
            <= judgment.intended_running_day_count
            <= assessment.maximum_run_days_per_week
        ):
            raise PlanOperationError(
                "Reviewed running frequency exceeds athlete-confirmed constraints"
            )
    for week in assessment.weeks:
        judgment = judgments[f"week.{week.week_number}"]
        if (
            week.intended_running_day_count is not None
            and judgment.intended_running_day_count != week.intended_running_day_count
        ):
            raise PlanOperationError(
                "Reviewed running frequency differs from the exact workout dates"
            )
        related = [
            judgments[item.key]
            for item in assessment.sessions
            if item.week_number == week.week_number
        ]
        if any(
            item.intended_running_day_count != judgment.intended_running_day_count
            for item in related
        ):
            raise PlanOperationError(
                "Week and session judgments disagree about intended running frequency"
            )
    if any(item.local_date > assessment.evidence.as_of_date for item in review.athlete_reports):
        raise PlanOperationError("Athlete reports cannot postdate the evidence as-of date")
    allowed = {"proceed"} if assessment.kind == "week" else {"proceed", "conditional"}
    return all(item.decision in allowed for item in review.judgments)


def resolve_progression_binding(
    repo: RepositoryIO,
    binding: RunProgressionBindingV1 | EvidenceArtifactReference | None,
) -> RunProgressionBindingV1 | None:
    """Resolve one shared whole-amendment review without chains or circular references."""
    if isinstance(binding, EvidenceArtifactReference):
        if binding.artifact_type != "week_planning_context":
            raise PlanOperationError("Shared progression review requires a week-planning context")
        context = load_evidence_artifact(repo, binding, WeekPlanningContext)
        if not isinstance(context.progression, RunProgressionBindingV1):
            raise PlanOperationError(
                "Shared progression review must resolve directly to a bound review"
            )
        return context.progression
    return binding


def require_progression_review_unlocked(
    repo: RepositoryIO,
    *,
    candidate: ProgressionCandidate,
    kind: ProgressionKind,
    binding: RunProgressionBindingV1 | EvidenceArtifactReference | None,
    timestamp: datetime,
    constraints: PlanningConstraintsSnapshot,
    target_week: WeekPlan | None = None,
) -> None:
    """Recompute numerical facts under the activity lock; source SHA alone is insufficient."""
    binding = resolve_progression_binding(repo, binding)
    if binding is None:
        raise PlanOperationError("A current evidence-linked running progression review is required")
    if binding.bound_at_utc.tzinfo is None or binding.bound_at_utc > timestamp:
        raise PlanOperationError("Progression review binding cannot postdate the operation")
    local_today = timestamp.astimezone(ZoneInfo(constraints.training_timezone)).date()
    assessment = binding.assessment
    if assessment.evidence.as_of_date != local_today:
        raise PlanOperationError(
            "Progression review must use evidence through the operation's local date"
        )
    if assessment.kind != kind or assessment.candidate_sha256 != candidate_sha256(candidate):
        raise PlanOperationError("Progression review belongs to another complete candidate")
    evidence = build_running_progression_evidence_unlocked(repo, as_of_date=local_today)
    current = build_progression_assessment(
        candidate, kind=kind, evidence=evidence, target_week=target_week, constraints=constraints
    )
    if current != assessment:
        raise PlanOperationError(
            "Progression facts changed or do not match their authoritative sources"
        )
    if not validate_review(current, binding.review):
        raise PlanOperationError(
            "Progression review requires revision or unmet future prerequisites"
        )


def validate_long_run_target(week: WeekPlan) -> None:
    hints = week.workout_structure_hints.long_run
    if hints is None or hints.target_distance_meters is None:
        return
    if week.target_run_volume_meters <= 0:
        raise PlanOperationError("A long-run target requires positive weekly distance")
    share_percent = 100 * hints.target_distance_meters / week.target_run_volume_meters
    if (
        not hints.minimum_weekly_run_volume_percent
        <= share_percent
        <= hints.maximum_weekly_run_volume_percent
    ):
        raise PlanOperationError("Long-run target is outside its declared weekly-distance range")
