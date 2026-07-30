"""Build the immutable evidence gate for a new macro training plan."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from resilio.core.coaching_context.service import build_coach_history
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    canonical_data_sha256,
    import_evidence_artifact,
    load_all_closed_plan_cycles,
    load_evidence_artifact,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.freshness import require_verified_vdot_approval
from resilio.core.planning.integrity import (
    planning_constraints_snapshot,
    planning_profile_sha256,
)
from resilio.core.planning.source_state import (
    coaching_evidence_source_sha256,
)
from resilio.core.planning.state_repository import load_planning_aggregate
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import ClosedPlanCycle, PlanningState, VDOTApproval
from resilio.schemas.coaching import WeeklyCoachContext
from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning_evidence import (
    CompactTrainingWeek,
    HistoricalPlanSummary,
    MacroPlanningContext,
    PlanCycleReview,
    PlanningEvidencePointer,
)
from resilio.schemas.profile import AthleteProfile

MAX_HISTORICAL_COMPACT_WEEKS = 52
MAX_RECENT_DETAILED_WEEKS = 12


def _validated_timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("Macro-planning context timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def _load_cycle_review(
    repo: RepositoryIO,
    cycle: ClosedPlanCycle,
) -> tuple[PlanCycleReview, EvidenceArtifactReference]:
    reference = EvidenceArtifactReference(
        artifact_type="cycle_review",
        artifact_sha256=cycle.closure.cycle_review_artifact_sha256,
    )
    try:
        review = load_evidence_artifact(
            repo,
            reference,
            PlanCycleReview,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    plan = cycle.active_plan_snapshot.plan
    if (
        review.plan_id != plan.id
        or review.macro_revision_id != plan.macro_revision_id
        or review.active_plan_sha256 != canonical_data_sha256(cycle.active_plan_snapshot)
        or review.effective_end_date != cycle.closure.effective_end_date
        or review.goal_outcome != cycle.closure.goal_outcome
    ):
        raise PlanOperationError("Closed plan cycle does not match its cycle-review evidence")
    return review, reference


def _historical_evidence(
    repo: RepositoryIO,
    state: PlanningState,
) -> tuple[
    list[HistoricalPlanSummary],
    list[CompactTrainingWeek],
    list[PlanningEvidencePointer],
]:
    try:
        cycles = load_all_closed_plan_cycles(
            repo,
            state.closed_plan_cycle_references,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    summaries: list[HistoricalPlanSummary] = []
    compact_weeks: list[CompactTrainingWeek] = []
    pointers: list[PlanningEvidencePointer] = []
    for cycle in cycles:
        review, reference = _load_cycle_review(repo, cycle)
        plan = cycle.active_plan_snapshot.plan
        summaries.append(
            HistoricalPlanSummary(
                plan_id=plan.id,
                macro_revision_id=plan.macro_revision_id,
                plan_start_date=plan.start_date,
                planned_end_date=plan.end_date,
                effective_end_date=cycle.closure.effective_end_date,
                methodology_identifier=plan.methodology.identifier,
                goal=plan.goal,
                goal_outcome=cycle.closure.goal_outcome,
                goal_activity=review.goal_activity,
                closure_disposition=cycle.closure.disposition,
                totals=review.totals,
                cycle_review_reference=reference,
            )
        )
        compact_weeks.extend(review.compact_weeks)
        pointers.extend(
            [
                PlanningEvidencePointer(
                    evidence_id=f"closed_plan.{plan.id}.summary",
                    category="closed_plan",
                    description=(
                        "Plan-level targets and execution totals from the "
                        f"closed cycle {plan.id}."
                    ),
                    artifact_reference=reference,
                ),
                PlanningEvidencePointer(
                    evidence_id=f"goal_outcome.{plan.id}",
                    category="goal_outcome",
                    description=(
                        "Athlete-confirmed goal disposition and exact evidence "
                        f"for the closed cycle {plan.id}."
                    ),
                    artifact_reference=reference,
                ),
            ]
        )
        if review.evidence_limitations:
            pointers.append(
                PlanningEvidencePointer(
                    evidence_id=f"coverage_limitation.{plan.id}",
                    category="coverage_limitation",
                    description=(
                        "Declared evidence limitations for the closed cycle " f"{plan.id}."
                    ),
                    artifact_reference=reference,
                )
            )
    compact_weeks.sort(key=lambda week: week.week_start)
    return (
        summaries,
        compact_weeks[-MAX_HISTORICAL_COMPACT_WEEKS:],
        pointers,
    )


def _source_payload(
    *,
    profile: AthleteProfile,
    approval: VDOTApproval,
    summaries: list[HistoricalPlanSummary],
    compact_weeks: list[CompactTrainingWeek],
    recent_weeks: list[WeeklyCoachContext],
) -> dict[str, object]:
    return {
        "profile": profile.model_dump(mode="json"),
        "vdot_approval": approval.model_dump(mode="json"),
        "historical_plan_summaries": [summary.model_dump(mode="json") for summary in summaries],
        "historical_compact_weeks": [week.model_dump(mode="json") for week in compact_weeks],
        "recent_detailed_weeks": [week.model_dump(mode="json") for week in recent_weeks],
    }


def create_macro_planning_context(
    repo: RepositoryIO,
    *,
    evidence_as_of_date: date,
    intended_plan_start_date: date,
    generated_at_utc: datetime | None = None,
    current_local_date: date | None = None,
) -> EvidenceArtifactReference:
    """Persist the required bounded evidence package for macro-plan creation."""
    today = current_local_date or date.today()
    if evidence_as_of_date > today:
        raise PlanOperationError("Evidence as-of date cannot be in the future")
    if intended_plan_start_date.weekday() != 0:
        raise PlanOperationError("New plan start date must be a Monday")
    if intended_plan_start_date <= evidence_as_of_date:
        raise PlanOperationError("New plan start date must be after the evidence as-of date")
    state = load_planning_aggregate(repo)
    if state is None:
        raise PlanOperationError("Planning state is required")
    if state.active_plan is not None:
        raise PlanOperationError("Close the active plan before creating renewal evidence")
    approval = require_verified_vdot_approval(
        repo,
        state.active_vdot_approval,
    )
    try:
        profile = ProfileRepository(repo).load()
    except (OSError, ValueError) as exc:
        raise PlanOperationError(str(exc)) from exc
    if profile is None:
        raise PlanOperationError("Athlete profile does not exist")
    generation_timestamp = _validated_timestamp(generated_at_utc)
    generation_local_date = generation_timestamp.astimezone(
        ZoneInfo(profile.training_timezone)
    ).date()
    if evidence_as_of_date > generation_local_date:
        raise PlanOperationError("Macro-planning evidence date cannot postdate context generation")
    summaries, compact_weeks, historical_pointers = _historical_evidence(
        repo,
        state,
    )
    source_state_sha256 = coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=evidence_as_of_date,
    )
    recent_history = build_coach_history(
        repo,
        as_of_date=evidence_as_of_date,
        week_count=MAX_RECENT_DETAILED_WEEKS,
    )
    recent_weeks = recent_history.weeks
    if (
        coaching_evidence_source_sha256(
            repo,
            evidence_as_of_date=evidence_as_of_date,
        )
        != source_state_sha256
    ):
        raise PlanOperationError("Training evidence changed while macro context was being built")
    current_state = load_planning_aggregate(repo)
    if current_state != state:
        raise PlanOperationError("Planning state changed while macro context was being built")
    evidence_index = [
        PlanningEvidencePointer(
            evidence_id="profile.current_constraints",
            category="profile",
            description=(
                "Athlete-confirmed current goal, availability, multisport "
                "commitments, and scheduling constraints."
            ),
        ),
        PlanningEvidencePointer(
            evidence_id=f"vdot.{approval.approval_id}",
            category="vdot",
            description=("The active VDOT approval and its exact persisted proposal evidence."),
        ),
        *historical_pointers,
        *[
            PlanningEvidencePointer(
                evidence_id=f"recent_week.{week.week_start.isoformat()}",
                category="recent_week",
                description=(
                    "Typed activity, adherence, recovery, intensity, and source "
                    f"coverage evidence for the week of {week.week_start.isoformat()}."
                ),
            )
            for week in recent_weeks
        ],
    ]
    source_payload = _source_payload(
        profile=profile,
        approval=approval,
        summaries=summaries,
        compact_weeks=compact_weeks,
        recent_weeks=recent_weeks,
    )
    context = MacroPlanningContext(
        evidence_as_of_date=evidence_as_of_date,
        intended_plan_start_date=intended_plan_start_date,
        generated_at_utc=generation_timestamp,
        planning_profile_sha256=planning_profile_sha256(profile),
        current_goal=profile.goal,
        current_constraints=planning_constraints_snapshot(profile),
        active_vdot_approval_id=approval.approval_id,
        historical_plan_summaries=summaries,
        historical_compact_weeks=compact_weeks,
        recent_detailed_weeks=recent_weeks,
        evidence_index=evidence_index,
        source_context_sha256=canonical_data_sha256(source_payload),
        source_state_sha256=source_state_sha256,
    )
    return import_evidence_artifact(
        repo,
        context,
        artifact_type="macro_planning_context",
    )
