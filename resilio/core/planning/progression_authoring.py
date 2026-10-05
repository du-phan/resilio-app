"""Read-only assessment and immutable review binding for complete proposals."""

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from resilio.canonical import canonical_data_sha256
from resilio.core.coaching_context.running_progression import (
    build_running_progression_evidence_unlocked,
)
from resilio.core.planning.artifacts import (
    canonical_json_bytes,
    import_evidence_artifact,
    load_evidence_artifact,
)
from resilio.core.planning.audit import validated_utc_timestamp
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.freshness import load_planning_profile_unlocked, require_fresh_plan
from resilio.core.planning.macro_evidence import load_validated_macro_context
from resilio.core.planning.progression_assessment import (
    ProgressionCandidate,
    ProgressionKind,
    build_progression_assessment,
)
from resilio.core.planning.progression_review import validate_review
from resilio.core.planning.state_repository import required_planning_state_unlocked
from resilio.core.planning.weekly_evidence import validate_week_context
from resilio.core.repository import RepositoryIO
from resilio.core.state_permissions import ensure_private_directory_tree, harden_sensitive_file
from resilio.core.workout_publication.locking import coordinated_publication_plan_activity_lock
from resilio.schemas.coaching import WeekPlanningContext
from resilio.schemas.macro_plan_draft import MacroPlanDraft
from resilio.schemas.plan_history import EvidenceArtifactReference
from resilio.schemas.planning.amendments import MacroAmendmentProposal
from resilio.schemas.planning.applications import WeekApplication
from resilio.schemas.planning.weeks import WeekPlan
from resilio.schemas.planning_evidence import MacroPlanningContext
from resilio.schemas.running_progression import (
    ProgressionAssessmentV1,
    RunProgressionBindingV1,
    RunProgressionReviewV1,
)


def load_progression_candidate(path: Path, kind: ProgressionKind) -> ProgressionCandidate:
    schemas: dict[
        ProgressionKind, type[MacroPlanDraft] | type[MacroAmendmentProposal] | type[WeekApplication]
    ] = {
        "macro": MacroPlanDraft,
        "amendment": MacroAmendmentProposal,
        "week": WeekApplication,
    }
    if path.is_symlink():
        raise PlanOperationError("Progression candidate cannot be a symlink")
    return schemas[kind].model_validate_json(path.read_bytes())


def _candidate_contexts(
    repo: RepositoryIO,
    candidate: ProgressionCandidate,
) -> list[MacroPlanningContext | WeekPlanningContext]:
    if isinstance(candidate, MacroPlanDraft):
        return [
            load_evidence_artifact(repo, candidate.planning_context_reference, MacroPlanningContext)
        ]
    references = (
        candidate.planning_context_references
        if isinstance(candidate, MacroAmendmentProposal)
        else [candidate.planning_context_reference]
    )
    return [
        load_evidence_artifact(repo, reference, WeekPlanningContext) for reference in references
    ]


def _assessment_unlocked(
    repo: RepositoryIO,
    candidate: ProgressionCandidate,
    kind: ProgressionKind,
    timestamp: datetime,
) -> tuple[ProgressionAssessmentV1, list[MacroPlanningContext | WeekPlanningContext]]:
    contexts = _candidate_contexts(repo, candidate)
    context = contexts[0]
    constraints = (
        context.current_constraints
        if isinstance(context, MacroPlanningContext)
        else context.constraints
    )
    local_today = timestamp.astimezone(ZoneInfo(constraints.training_timezone)).date()
    target: WeekPlan | None = None
    if isinstance(candidate, WeekApplication):
        state = required_planning_state_unlocked(repo)
        if state.active_plan is None:
            raise PlanOperationError("Weekly progression assessment requires an active plan")
        target = next(
            (
                week
                for week in state.active_plan.plan.weeks
                if week.week_number == candidate.week_number
            ),
            None,
        )
        if target is None:
            raise PlanOperationError("Candidate week is absent from the active plan")
    evidence = build_running_progression_evidence_unlocked(repo, as_of_date=local_today)
    return (
        build_progression_assessment(
            candidate, kind=kind, evidence=evidence, target_week=target, constraints=constraints
        ),
        contexts,
    )


def _validate_base_contexts_unlocked(
    repo: RepositoryIO,
    candidate: ProgressionCandidate,
    timestamp: datetime,
) -> None:
    state = required_planning_state_unlocked(repo)
    if isinstance(candidate, MacroPlanDraft):
        macro_context = load_validated_macro_context(
            repo, state, candidate, load_planning_profile_unlocked(repo)
        )
        if macro_context.generated_at_utc > timestamp:
            raise PlanOperationError("Base planning context cannot postdate review binding")
        return
    plan = require_fresh_plan(repo, state, activity_lock_held=True)
    if state.active_plan is None or state.active_plan.plan_approval is None:
        raise PlanOperationError("Progression binding requires an approved active plan")
    if isinstance(candidate, MacroAmendmentProposal):
        if canonical_data_sha256(state.active_plan) != candidate.expected_active_plan_sha256:
            raise PlanOperationError(
                "Amendment candidate no longer matches current active authority"
            )
        targets = [
            (week.week_number, reference)
            for week, reference in zip(
                candidate.weeks, candidate.planning_context_references, strict=True
            )
        ]
    else:
        targets = [(candidate.week_number, candidate.planning_context_reference)]
    for week_number, reference in targets:
        target = next((week for week in plan.weeks if week.week_number == week_number), None)
        if target is None:
            raise PlanOperationError(
                "Progression context references a week absent from the active plan"
            )
        context = validate_week_context(repo, plan=plan, target_week=target, reference=reference)
        if context.generated_at_utc > timestamp:
            raise PlanOperationError("Base planning context cannot postdate review binding")
        if isinstance(candidate, MacroAmendmentProposal):
            local_today = timestamp.astimezone(
                ZoneInfo(plan.constraints_snapshot.training_timezone)
            ).date()
            if context.evidence_as_of_date != local_today:
                raise PlanOperationError("Amendment base context must cover its application date")


def assess_progression(
    repo: RepositoryIO,
    path: Path,
    *,
    kind: ProgressionKind,
    evaluated_at_utc: datetime | None = None,
) -> ProgressionAssessmentV1:
    candidate = load_progression_candidate(path, kind)
    with coordinated_publication_plan_activity_lock(repo, "assess_running_progression"):
        assessment, _ = _assessment_unlocked(
            repo, candidate, kind, validated_utc_timestamp(evaluated_at_utc)
        )
        return assessment


def bind_progression_review(
    repo: RepositoryIO,
    path: Path,
    review_path: Path,
    output_path: Path,
    *,
    kind: ProgressionKind,
    evaluated_at_utc: datetime | None = None,
) -> dict[str, object]:
    """Emit new approval-ready bytes only when the coach decision permits the candidate."""
    output_path = output_path.expanduser().absolute()
    if output_path.exists() or output_path.is_symlink():
        raise PlanOperationError(
            "Review binding requires a new output path; " "existing proposals are immutable"
        )
    candidate = load_progression_candidate(path, kind)
    review = RunProgressionReviewV1.model_validate_json(review_path.read_bytes())
    with coordinated_publication_plan_activity_lock(repo, "bind_running_progression_review"):
        timestamp = validated_utc_timestamp(evaluated_at_utc)
        _validate_base_contexts_unlocked(repo, candidate, timestamp)
        assessment, contexts = _assessment_unlocked(repo, candidate, kind, timestamp)
        if not validate_review(assessment, review):
            return {
                "status": "revision_required",
                "assessment": assessment.model_dump(mode="json"),
                "decisions": [item.model_dump(mode="json") for item in review.judgments],
            }
        binding = RunProgressionBindingV1(
            bound_at_utc=timestamp, assessment=assessment, review=review
        )
        references: list[EvidenceArtifactReference] = []
        for context in contexts:
            progression = binding if not references else references[0]
            reviewed_context = type(context).model_validate(
                context.model_copy(update={"progression": progression}).model_dump(mode="python")
            )
            references.append(
                import_evidence_artifact(
                    repo,
                    reviewed_context,
                    artifact_type="macro_planning_context"
                    if isinstance(context, MacroPlanningContext)
                    else "week_planning_context",
                )
            )
        updates: dict[str, object] = (
            {"planning_context_references": references}
            if isinstance(candidate, MacroAmendmentProposal)
            else {"planning_context_reference": references[0]}
        )
        final = type(candidate).model_validate(
            candidate.model_copy(update=updates).model_dump(mode="python")
        )
        # Exclusive creation also protects against a concurrent proposal writer.
        if any(parent.is_symlink() for parent in output_path.absolute().parents):
            raise PlanOperationError("Proposal output ancestors cannot be symlinks")
        data_root = repo.resolve_path("data")
        private_root = (
            data_root if output_path.absolute().is_relative_to(data_root) else output_path.parent
        )
        ensure_private_directory_tree(private_root, output_path.parent)
        descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(final))
            handle.flush()
            os.fsync(handle.fileno())
        harden_sensitive_file(output_path)
        return {
            "status": "review_bound",
            "proposal_file": str(output_path),
            "candidate_sha256": assessment.candidate_sha256,
            "planning_context_references": [item.model_dump(mode="json") for item in references],
        }
