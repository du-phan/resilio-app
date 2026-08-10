"""Presentation-neutral training-plan operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from resilio.core.planning.artifacts import load_evidence_artifact
from resilio.core.planning.assessment_context import (
    create_assessment_planning_context,
)
from resilio.core.planning.assessment_review import (
    close_assessment_from_review,
    create_assessment_review,
    list_assessment_result_candidates,
)
from resilio.core.planning.cycle_review import (
    confirmed_goal_outcome,
    create_cycle_review,
)
from resilio.core.planning.macro_context import create_macro_planning_context
from resilio.core.planning.service import (
    PlanOperationError,
    close_current_plan_from_review,
    discard_unapproved_current_plan,
    load_current_plan,
)
from resilio.core.planning.service import (
    create_assessment_plan as persist_assessment_plan,
)
from resilio.core.planning.service import (
    create_macro_plan as persist_macro_plan,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import PlanningState
from resilio.schemas.assessment import AssessmentReason, TemporaryScheduleConstraint
from resilio.schemas.macro_plan_draft import MacroPlanDraft
from resilio.schemas.plan_history import (
    EvidenceArtifactReference,
    PlanClosureDisposition,
)
from resilio.schemas.planning.drafts import AssessmentPlanDraft
from resilio.schemas.planning.plans import (
    BaselineAssessmentPlan,
    RaceMacroPlan,
    TrainingPlan,
)
from resilio.schemas.planning.weeks import WeekPlan
from resilio.schemas.planning_evidence import (
    AssessmentPlanningContext,
    AssessmentResultCandidate,
    BaselineAssessmentReview,
    MacroPlanningContext,
    PlanCycleReview,
)


@dataclass(frozen=True)
class PlanError:
    error_type: str
    message: str


class PlanStatus(BaseModel):
    plan_kind: str
    plan_id: str
    methodology: str | None = None
    benchmark_distance: str | None = None
    total_week_count: int = Field(ge=1)
    populated_week_numbers: list[int]
    next_unpopulated_week_number: int | None

    model_config = ConfigDict(extra="forbid")


class CycleReviewEvidenceResult(BaseModel):
    reference: EvidenceArtifactReference
    review: PlanCycleReview

    model_config = ConfigDict(extra="forbid")


class MacroContextEvidenceResult(BaseModel):
    reference: EvidenceArtifactReference
    context: MacroPlanningContext

    model_config = ConfigDict(extra="forbid")


class AssessmentContextEvidenceResult(BaseModel):
    reference: EvidenceArtifactReference
    context: AssessmentPlanningContext

    model_config = ConfigDict(extra="forbid")


class AssessmentReviewEvidenceResult(BaseModel):
    reference: EvidenceArtifactReference
    review: BaselineAssessmentReview

    model_config = ConfigDict(extra="forbid")


def _repository() -> RepositoryIO:
    return RepositoryIO()


def get_current_plan() -> TrainingPlan | PlanError:
    try:
        result = load_current_plan(_repository(), allow_missing=True)
        if result is None:
            return PlanError("not_found", "No current training plan is available")
        return result
    except PlanOperationError as exc:
        return PlanError("validation", str(exc))


def discard_unapproved_plan(
    *,
    expected_plan_revision_id: str,
) -> PlanningState | PlanError:
    try:
        return discard_unapproved_current_plan(
            _repository(),
            expected_plan_revision_id=expected_plan_revision_id,
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def create_macro_plan(draft: MacroPlanDraft) -> RaceMacroPlan | PlanError:
    try:
        return persist_macro_plan(_repository(), draft)
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def create_macro_plan_from_file(path: Path) -> RaceMacroPlan | PlanError:
    try:
        draft = MacroPlanDraft.model_validate_json(path.read_text())
    except OSError as exc:
        return PlanError("not_found", f"Macro plan draft could not be read: {exc}")
    except ValueError as exc:
        return PlanError("validation", f"Macro plan draft is invalid: {exc}")
    return create_macro_plan(draft)


def create_assessment_plan(draft: AssessmentPlanDraft) -> BaselineAssessmentPlan | PlanError:
    try:
        return persist_assessment_plan(_repository(), draft)
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def create_assessment_plan_from_file(path: Path) -> BaselineAssessmentPlan | PlanError:
    try:
        draft = AssessmentPlanDraft.model_validate_json(path.read_text())
    except OSError as exc:
        return PlanError("not_found", f"Assessment plan draft could not be read: {exc}")
    except ValueError as exc:
        return PlanError("validation", f"Assessment plan draft is invalid: {exc}")
    return create_assessment_plan(draft)


def create_cycle_review_evidence(
    *,
    effective_end_date: date,
    evidence_as_of_date: date,
    goal_status: str,
    goal_activity_id: str | None,
    athlete_confirmation_reference: str,
    goal_notes: str | None = None,
) -> CycleReviewEvidenceResult | PlanError:
    try:
        repo = _repository()
        outcome = confirmed_goal_outcome(
            repo,
            status=goal_status,
            local_activity_id=goal_activity_id,
            athlete_confirmation_reference=athlete_confirmation_reference,
            notes=goal_notes,
        )
        reference = create_cycle_review(
            repo,
            effective_end_date=effective_end_date,
            evidence_as_of_date=evidence_as_of_date,
            goal_outcome=outcome,
        )
        return CycleReviewEvidenceResult(
            reference=reference,
            review=load_evidence_artifact(
                repo,
                reference,
                PlanCycleReview,
            ),
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def create_macro_context_evidence(
    *,
    evidence_as_of_date: date,
    intended_plan_start_date: date,
) -> MacroContextEvidenceResult | PlanError:
    try:
        repo = _repository()
        reference = create_macro_planning_context(
            repo,
            evidence_as_of_date=evidence_as_of_date,
            intended_plan_start_date=intended_plan_start_date,
        )
        return MacroContextEvidenceResult(
            reference=reference,
            context=load_evidence_artifact(
                repo,
                reference,
                MacroPlanningContext,
            ),
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def create_assessment_context_evidence(
    *,
    evidence_as_of_date: date,
    intended_plan_start_date: date,
    assessment_reasons: list[AssessmentReason],
    temporary_schedule_constraints: list[TemporaryScheduleConstraint] | None = None,
) -> AssessmentContextEvidenceResult | PlanError:
    try:
        repo = _repository()
        reference = create_assessment_planning_context(
            repo,
            evidence_as_of_date=evidence_as_of_date,
            intended_plan_start_date=intended_plan_start_date,
            assessment_reasons=assessment_reasons,
            temporary_schedule_constraints=temporary_schedule_constraints or [],
        )
        return AssessmentContextEvidenceResult(
            reference=reference,
            context=load_evidence_artifact(
                repo,
                reference,
                AssessmentPlanningContext,
            ),
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def get_assessment_result_candidates() -> list[AssessmentResultCandidate] | PlanError:
    try:
        return list_assessment_result_candidates(_repository())
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def create_assessment_review_evidence(
    *,
    candidate_id: str,
    evidence_as_of_date: date,
    official_distance_confirmation_reference: str,
    athlete_confirmation_reference: str,
    review_summary: str,
) -> AssessmentReviewEvidenceResult | PlanError:
    try:
        repo = _repository()
        reference = create_assessment_review(
            repo,
            candidate_id=candidate_id,
            evidence_as_of_date=evidence_as_of_date,
            official_distance_confirmation_reference=(official_distance_confirmation_reference),
            athlete_confirmation_reference=athlete_confirmation_reference,
            review_summary=review_summary,
        )
        return AssessmentReviewEvidenceResult(
            reference=reference,
            review=load_evidence_artifact(
                repo,
                reference,
                BaselineAssessmentReview,
            ),
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def close_assessment(
    *,
    assessment_review_sha256: str,
    reason: str,
    athlete_confirmation_reference: str,
) -> PlanningState | PlanError:
    try:
        return close_assessment_from_review(
            _repository(),
            assessment_review_reference=EvidenceArtifactReference(
                artifact_type="assessment_review",
                artifact_sha256=assessment_review_sha256,
            ),
            reason=reason,
            athlete_confirmation_reference=athlete_confirmation_reference,
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def close_plan_cycle(
    *,
    cycle_review_sha256: str,
    disposition: PlanClosureDisposition,
    reason: str,
    athlete_confirmation_reference: str,
) -> PlanningState | PlanError:
    try:
        return close_current_plan_from_review(
            _repository(),
            cycle_review_reference=EvidenceArtifactReference(
                artifact_type="cycle_review",
                artifact_sha256=cycle_review_sha256,
            ),
            disposition=disposition,
            reason=reason,
            athlete_confirmation_reference=athlete_confirmation_reference,
        )
    except (PlanOperationError, ValueError, OSError) as exc:
        return PlanError("validation", str(exc))


def get_plan_week(week_number: int) -> WeekPlan | PlanError:
    plan = get_current_plan()
    if isinstance(plan, PlanError):
        return plan
    matching = [week for week in plan.weeks if week.week_number == week_number]
    if len(matching) != 1:
        return PlanError(
            "not_found",
            f"Week {week_number} does not exist in the current plan",
        )
    return matching[0]


def get_plan_status() -> PlanStatus | PlanError:
    plan = get_current_plan()
    if isinstance(plan, PlanError):
        return plan
    populated = sorted(week.week_number for week in plan.weeks if week.running_workouts)
    next_unpopulated = next(
        (week.week_number for week in plan.weeks if not week.running_workouts),
        None,
    )
    return PlanStatus(
        plan_kind=plan.kind,
        plan_id=plan.id,
        methodology=(
            plan.methodology.identifier.value if isinstance(plan, RaceMacroPlan) else None
        ),
        benchmark_distance=(
            str(plan.benchmark_intent.race_distance)
            if isinstance(plan, BaselineAssessmentPlan)
            else None
        ),
        total_week_count=plan.total_weeks,
        populated_week_numbers=populated,
        next_unpopulated_week_number=next_unpopulated,
    )


def build_macro_template(total_weeks: int) -> dict[str, object] | PlanError:
    if total_weeks <= 0:
        return PlanError("validation", "total_weeks must be positive")
    return {
        "goal": {
            "type": None,
            "target_date": None,
            "target_time": None,
        },
        "methodology": {
            "identifier": None,
            "selection_rationale": None,
        },
        "weeks": [
            {
                "week_number": week_number,
                "phase": None,
                "start_date": None,
                "end_date": None,
                "target_run_volume_meters": None,
                "workout_structure_hints": {
                    "quality": {
                        "maximum_sessions": None,
                        "types": None,
                    },
                    "long_run": {
                        "emphasis": None,
                        "minimum_weekly_run_volume_percent": None,
                        "maximum_weekly_run_volume_percent": None,
                        "target_distance_meters": None,
                    },
                    "intensity_distribution": None,
                },
                "running_workouts": [],
                "is_recovery_week": False,
                "notes": None,
            }
            for week_number in range(1, total_weeks + 1)
        ],
        "vdot_approval_id": None,
        "planning_context_reference": {
            "artifact_type": "macro_planning_context",
            "artifact_sha256": None,
        },
        "planning_rationale": None,
        "adaptation_decisions": [
            {
                "decision_type": "methodology_selection",
                "evidence_ids": [],
                "observed_facts": None,
                "planning_change": None,
                "affected_week_numbers": [],
                "uncertainty_or_limitation": None,
            },
            {
                "decision_type": "starting_volume",
                "evidence_ids": [],
                "observed_facts": None,
                "planning_change": None,
                "affected_week_numbers": [1],
                "uncertainty_or_limitation": None,
            },
        ],
    }


def build_assessment_template(total_weeks: int) -> dict[str, object] | PlanError:
    if total_weeks <= 0:
        return PlanError("validation", "total_weeks must be positive")
    return {
        "weeks": [
            {
                "week_number": week_number,
                "phase": "base" if week_number < total_weeks else "assessment",
                "start_date": None,
                "end_date": None,
                "target_run_volume_meters": None,
                "workout_structure_hints": {
                    "quality": {
                        "maximum_sessions": 0 if week_number < total_weeks else 1,
                        "types": [] if week_number < total_weeks else ["benchmark"],
                    },
                    "long_run": None,
                    "intensity_distribution": None,
                },
                "running_workouts": [],
                "is_recovery_week": False,
                "notes": None,
            }
            for week_number in range(1, total_weeks + 1)
        ],
        "planning_context_reference": {
            "artifact_type": "assessment_planning_context",
            "artifact_sha256": None,
        },
        "planning_rationale": None,
        "adaptation_decisions": [
            {
                "decision_type": "starting_volume",
                "evidence_ids": [],
                "observed_facts": None,
                "planning_change": None,
                "affected_week_numbers": [],
                "uncertainty_or_limitation": None,
            },
            {
                "decision_type": "benchmark_scheduling",
                "evidence_ids": [],
                "observed_facts": None,
                "planning_change": None,
                "affected_week_numbers": [total_weeks],
                "uncertainty_or_limitation": None,
            },
        ],
        "assessment_reasons": [],
        "benchmark_intent": {
            "race_distance": "5k",
            "preferred_date": None,
            "fallback_window_start": None,
            "fallback_window_end": None,
        },
        "temporary_schedule_constraints": [],
        "medical_rehabilitation_excluded": True,
    }
