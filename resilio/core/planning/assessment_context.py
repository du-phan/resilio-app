"""Build immutable evidence for a non-rehabilitation baseline assessment."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from resilio.core.coaching_context.service import build_coach_history
from resilio.core.planning.artifacts import import_evidence_artifact
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.integrity import (
    planning_constraints_snapshot,
    planning_inputs_sha256,
)
from resilio.core.planning.source_state import coaching_evidence_source_sha256
from resilio.core.planning.state_repository import load_planning_aggregate
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryScheduleConstraint,
)
from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning_evidence import (
    AssessmentPlanningContext,
    PlanningEvidencePointer,
)

MAX_RECENT_ASSESSMENT_WEEKS = 12


def _validated_timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("Assessment-context timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def _planning_evidence_index(
    recent_week_start_dates: Sequence[date],
    *,
    include_temporary_schedule_constraints: bool,
) -> list[PlanningEvidencePointer]:
    pointers = [
        PlanningEvidencePointer(
            evidence_id="profile.current_constraints",
            category="profile",
            description=(
                "Athlete-confirmed goal, run availability, athlete-managed sport "
                "expectations, and durable scheduling constraints."
            ),
        ),
        *[
            PlanningEvidencePointer(
                evidence_id=f"recent_week.{week_start.isoformat()}",
                category="recent_week",
                description=(
                    "Typed activity, recovery, adherence, and evidence coverage for "
                    f"the week of {week_start.isoformat()}."
                ),
            )
            for week_start in recent_week_start_dates
        ],
    ]
    if include_temporary_schedule_constraints:
        pointers.append(
            PlanningEvidencePointer(
                evidence_id="assessment.temporary_schedule_constraints",
                category="schedule_constraint",
                description=(
                    "Athlete-confirmed unavailable date ranges that apply only "
                    "to this baseline-assessment plan."
                ),
            )
        )
    return pointers


def create_assessment_planning_context(
    repo: RepositoryIO,
    *,
    evidence_as_of_date: date,
    intended_plan_start_date: date,
    assessment_reasons: Sequence[AssessmentReason | str],
    temporary_schedule_constraints: Sequence[TemporaryScheduleConstraint] = (),
    generated_at_utc: datetime | None = None,
    current_local_date: date | None = None,
) -> EvidenceArtifactReference:
    """Persist current profile and training evidence for an assessment block."""
    today = current_local_date or date.today()
    if evidence_as_of_date > today:
        raise PlanOperationError("Evidence as-of date cannot be in the future")
    if intended_plan_start_date.weekday() != 0:
        raise PlanOperationError("Assessment plan start date must be a Monday")
    if intended_plan_start_date <= evidence_as_of_date:
        raise PlanOperationError("Assessment plan start must follow the evidence date")
    normalized_reasons = [AssessmentReason(reason) for reason in assessment_reasons]
    normalized_schedule_constraints = [
        TemporaryScheduleConstraint.model_validate(constraint)
        for constraint in temporary_schedule_constraints
    ]
    if not normalized_reasons:
        raise PlanOperationError("At least one assessment reason is required")
    if len(normalized_reasons) != len(set(normalized_reasons)):
        raise PlanOperationError("Assessment reasons must be unique")
    state = load_planning_aggregate(repo, allow_missing=True)
    if state is not None and state.active_plan is not None:
        raise PlanOperationError("Close the active plan before creating assessment evidence")
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
        raise PlanOperationError("Assessment evidence date cannot postdate context generation")
    source_state_sha256 = coaching_evidence_source_sha256(
        repo,
        evidence_as_of_date=evidence_as_of_date,
    )
    recent_weeks = build_coach_history(
        repo,
        as_of_date=evidence_as_of_date,
        week_count=MAX_RECENT_ASSESSMENT_WEEKS,
    ).weeks
    if (
        coaching_evidence_source_sha256(
            repo,
            evidence_as_of_date=evidence_as_of_date,
        )
        != source_state_sha256
    ):
        raise PlanOperationError("Training evidence changed while assessment context was built")
    if load_planning_aggregate(repo, allow_missing=True) != state:
        raise PlanOperationError("Planning state changed while assessment context was built")
    evidence_index = _planning_evidence_index(
        [week.week_start for week in recent_weeks],
        include_temporary_schedule_constraints=bool(normalized_schedule_constraints),
    )
    context = AssessmentPlanningContext(
        evidence_as_of_date=evidence_as_of_date,
        intended_plan_start_date=intended_plan_start_date,
        generated_at_utc=generation_timestamp,
        planning_inputs_sha256=planning_inputs_sha256(profile),
        current_goal=profile.goal,
        current_constraints=planning_constraints_snapshot(profile),
        assessment_reasons=normalized_reasons,
        temporary_schedule_constraints=normalized_schedule_constraints,
        recent_detailed_weeks=recent_weeks,
        evidence_index=evidence_index,
        source_state_sha256=source_state_sha256,
    )
    return import_evidence_artifact(
        repo,
        context,
        artifact_type="assessment_planning_context",
    )
