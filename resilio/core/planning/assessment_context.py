"""Build immutable evidence for a non-rehabilitation baseline assessment."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from resilio.core.coaching_context.service import build_coach_history
from resilio.core.planning.artifacts import (
    canonical_data_sha256,
    import_evidence_artifact,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.integrity import (
    planning_constraints_snapshot,
    planning_profile_sha256,
)
from resilio.core.planning.source_state import coaching_evidence_source_sha256
from resilio.core.planning.state_repository import load_planning_aggregate
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.schemas.assessment import (
    AssessmentReason,
    TemporaryOtherSportCommitmentOverride,
    TemporaryScheduleConstraint,
)
from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning_evidence import (
    AssessmentPlanningContext,
    PlanningEvidencePointer,
)
from resilio.schemas.profile import AthleteProfile

MAX_RECENT_ASSESSMENT_WEEKS = 12


def _validated_timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("Assessment-context timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def _validate_sport_overrides(
    profile: AthleteProfile,
    overrides: Sequence[TemporaryOtherSportCommitmentOverride],
    *,
    intended_plan_start_date: date,
) -> None:
    override_keys = [
        (override.week_start_date, override.sport_name) for override in overrides
    ]
    if len(override_keys) != len(set(override_keys)):
        raise PlanOperationError(
            "Temporary other-sport overrides must be unique by week and sport"
        )
    active_sport_names = {
        commitment.sport_name
        for commitment in profile.other_sport_commitments
        if commitment.active
    }
    for override in overrides:
        if override.sport_name not in active_sport_names:
            raise PlanOperationError("Temporary override references an inactive other sport")
        if override.week_start_date < intended_plan_start_date:
            raise PlanOperationError(
                "Temporary other-sport override predates the assessment plan"
            )


def _planning_evidence_index(
    recent_week_start_dates: Sequence[date],
    *,
    include_temporary_schedule_constraints: bool,
    include_temporary_other_sport_overrides: bool,
) -> list[PlanningEvidencePointer]:
    pointers = [
        PlanningEvidencePointer(
            evidence_id="profile.current_constraints",
            category="profile",
            description=(
                "Athlete-confirmed goal, run availability, multisport commitments, "
                "and durable scheduling constraints."
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
    if include_temporary_other_sport_overrides:
        pointers.append(
            PlanningEvidencePointer(
                evidence_id=(
                    "assessment.temporary_other_sport_commitment_overrides"
                ),
                category="schedule_constraint",
                description=(
                    "Coach-proposed session counts for exact other sports and "
                    "assessment weeks, subject to whole-plan approval."
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
    temporary_other_sport_commitment_overrides: Sequence[
        TemporaryOtherSportCommitmentOverride
    ] = (),
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
    normalized_sport_overrides = [
        TemporaryOtherSportCommitmentOverride.model_validate(override)
        for override in temporary_other_sport_commitment_overrides
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
    _validate_sport_overrides(
        profile,
        normalized_sport_overrides,
        intended_plan_start_date=intended_plan_start_date,
    )
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
        include_temporary_other_sport_overrides=bool(normalized_sport_overrides),
    )
    source_payload = {
        "profile": profile.model_dump(mode="json"),
        "assessment_reasons": [reason.value for reason in normalized_reasons],
        "temporary_schedule_constraints": [
            constraint.model_dump(mode="json")
            for constraint in normalized_schedule_constraints
        ],
        "temporary_other_sport_commitment_overrides": [
            override.model_dump(mode="json") for override in normalized_sport_overrides
        ],
        "recent_detailed_weeks": [week.model_dump(mode="json") for week in recent_weeks],
    }
    context = AssessmentPlanningContext(
        evidence_as_of_date=evidence_as_of_date,
        intended_plan_start_date=intended_plan_start_date,
        generated_at_utc=generation_timestamp,
        planning_profile_sha256=planning_profile_sha256(profile),
        current_goal=profile.goal,
        current_constraints=planning_constraints_snapshot(profile),
        assessment_reasons=normalized_reasons,
        temporary_schedule_constraints=normalized_schedule_constraints,
        temporary_other_sport_commitment_overrides=normalized_sport_overrides,
        recent_detailed_weeks=recent_weeks,
        evidence_index=evidence_index,
        source_context_sha256=canonical_data_sha256(source_payload),
        source_state_sha256=source_state_sha256,
    )
    return import_evidence_artifact(
        repo,
        context,
        artifact_type="assessment_planning_context",
    )
