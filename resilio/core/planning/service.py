"""Revision-bound training-plan and approval application services."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from resilio.core.methodology import (
    MethodologyRegistryError,
    resolve_methodology_choice,
)
from resilio.core.planning.adherence_evidence import (
    ApprovedWorkoutWindow as ApprovedWorkoutWindow,
)
from resilio.core.planning.approval_evidence import (
    ApprovalEvidenceError,
)
from resilio.core.planning.approval_evidence import (
    load_vdot_proposal_unlocked as _load_vdot_proposal_unlocked,
)
from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    canonical_data_sha256,
    load_evidence_artifact,
    save_closed_plan_archive,
)
from resilio.core.planning.assessment_plan_service import (
    create_assessment_plan as create_assessment_plan,
)
from resilio.core.planning.audit import (
    new_planning_id as _new_id,
)
from resilio.core.planning.audit import (
    validated_utc_timestamp as _now_utc,
)
from resilio.core.planning.errors import PlanOperationError as PlanOperationError
from resilio.core.planning.freshness import (
    load_planning_profile_unlocked as _load_profile,
)
from resilio.core.planning.freshness import (
    require_fresh_plan as _require_fresh_plan,
)
from resilio.core.planning.freshness import (
    require_verified_vdot_approval as _verify_vdot_approval,
)
from resilio.core.planning.integrity import (
    plan_skeleton_sha256,
    planning_constraints_snapshot,
    planning_inputs_sha256,
)
from resilio.core.planning.macro_evidence import load_validated_macro_context
from resilio.core.planning.plan_proposal import (
    discard_unapproved_current_plan as discard_unapproved_current_plan,
)
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.progression_assessment import macro_draft_from_plan
from resilio.core.planning.progression_review import (
    require_progression_review_unlocked,
    validate_long_run_target,
)
from resilio.core.planning.source_state import (
    coaching_evidence_source_sha256_unlocked,
)
from resilio.core.planning.state_repository import (
    load_planning_aggregate as load_planning_aggregate,
)
from resilio.core.planning.state_repository import (
    persist_planning_state as _persist,
)
from resilio.core.planning.state_repository import (
    required_planning_state_unlocked as _required_state,
)
from resilio.core.planning.weekly_service import (
    apply_approved_week as apply_approved_week,
)
from resilio.core.planning.weekly_service import (
    approve_week_application as approve_week_application,
)
from resilio.core.planning.weekly_service import (
    load_week_application as load_week_application,
)
from resilio.core.planning.weekly_service import (
    validate_week_application as validate_week_application,
)
from resilio.core.planning.workout_evidence import (
    load_approved_workouts_for_date_range as load_approved_workouts_for_date_range,
)
from resilio.core.planning.workout_evidence import (
    load_publishable_workout as load_publishable_workout,
)
from resilio.core.planning.workout_evidence import (
    load_publishable_workouts as load_publishable_workouts,
)
from resilio.core.repository import RepositoryIO
from resilio.core.vdot import parse_time_string
from resilio.core.workout_fulfillment.pair_operation_evidence import (
    matching_resilio_pair_operation,
)
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.locking import (
    coordinated_publication_plan_activity_lock,
)
from resilio.core.workout_publication.manifest import load_manifest
from resilio.core.workout_publication.publication_deletions import (
    monitored_pending_workout_ids,
)
from resilio.schemas.approvals import (
    ActivePlanState,
    ClosedPlanArchive,
    PlanningState,
    VDOTApproval,
)
from resilio.schemas.macro_plan_draft import MacroPlanDraft
from resilio.schemas.plan_history import (
    EvidenceArtifactReference,
    PlanClosure,
    PlanClosureDisposition,
)
from resilio.schemas.planning.approval_records import PlanApproval
from resilio.schemas.planning.plans import RaceMacroPlan, TrainingPlan
from resilio.schemas.planning_evidence import (
    PlanCycleReview,
)
from resilio.schemas.profile import AthleteProfile


def load_current_plan(
    repo: RepositoryIO,
    *,
    allow_missing: bool = False,
) -> TrainingPlan | None:
    state = load_planning_aggregate(repo, allow_missing=allow_missing)
    if state is None or state.active_plan is None:
        if allow_missing:
            return None
        raise PlanOperationError("No current training plan is available")
    return state.active_plan.plan


def _draft_goal_matches_profile(
    draft: MacroPlanDraft,
    profile: AthleteProfile,
) -> bool:
    profile_goal = profile.goal
    draft_target_seconds = (
        parse_time_string(draft.goal.target_time) if draft.goal.target_time is not None else None
    )
    return (
        profile_goal.type.value == str(draft.goal.type)
        and profile_goal.target_date == draft.goal.target_date
        and profile_goal.target_finish_time_seconds == draft_target_seconds
    )


def approve_vdot_proposal(
    repo: RepositoryIO,
    proposal_file: Path,
    *,
    approved_at_utc: datetime | None = None,
) -> PlanningState:
    """Approve exact proposal bytes and invalidate dependent plan state."""
    resolved_file = proposal_file.expanduser().resolve()
    approval_timestamp = _now_utc(approved_at_utc)
    with coordinated_plan_lock(repo, "approve_vdot_proposal"):
        try:
            proposal_file_evidence = _load_vdot_proposal_unlocked(
                repo,
                resolved_file,
            )
        except ApprovalEvidenceError as exc:
            raise PlanOperationError(str(exc)) from exc
        proposal = proposal_file_evidence.proposal
        if proposal.generated_at_utc > approval_timestamp:
            raise PlanOperationError(
                "VDOT proposal was generated after the requested approval time"
            )
        approval = VDOTApproval(
            approval_id=_new_id("vdot_approval"),
            approved_vdot=proposal.proposed_vdot,
            proposal_file=str(resolved_file),
            proposal_file_sha256=proposal_file_evidence.file_sha256,
            evidence_type=proposal.evidence_type,
            proposal_snapshot=proposal,
            approved_at_utc=approval_timestamp,
        )
        state = _required_state(repo)
        if state.active_plan is not None:
            raise PlanOperationError(
                "Close the active plan with fresh cycle-review evidence before "
                "replacing its VDOT approval"
            )
        replacement = state.model_copy(
            update={
                "vdot_approvals": [*state.vdot_approvals, approval],
                "active_vdot_approval_id": approval.approval_id,
            }
        )
        return _persist(repo, replacement)


def _publication_closure_blockers(
    repo: RepositoryIO,
    active_plan: ActivePlanState,
    *,
    effective_end_date: date,
) -> list[str]:
    publication_manifest = load_manifest(repo)
    fulfillment_manifest = load_fulfillment_manifest(repo)
    monitored_pending_ids = monitored_pending_workout_ids(repo)
    plan = active_plan.plan
    blockers = [
        local_workout_id
        for local_workout_id, pending in publication_manifest.pending.items()
        if pending.workout_identity.plan_id == plan.id
        and pending.workout_identity.plan_revision_id == plan.plan_revision_id
        and local_workout_id not in monitored_pending_ids
    ]
    for local_workout_id, publication in publication_manifest.workouts.items():
        if (
            publication.workout_identity.plan_id != plan.id
            or publication.workout_identity.plan_revision_id != plan.plan_revision_id
            or publication.occurrence_date <= effective_end_date
        ):
            continue
        matching_fulfillment = next(
            (
                fulfillment
                for fulfillment in fulfillment_manifest.fulfillments.values()
                if fulfillment.workout_identity == publication.workout_identity
                and fulfillment.provider_pair_supports_event(publication.event_id)
                and fulfillment.local_activity_id
                not in fulfillment_manifest.unresolved_fulfillment_conflicts
            ),
            None,
        )
        if matching_fulfillment is None:
            blockers.append(local_workout_id)
    for fulfillment in fulfillment_manifest.fulfillments.values():
        if (
            fulfillment.workout_identity.plan_id != plan.id
            or fulfillment.workout_identity.plan_revision_id != plan.plan_revision_id
        ):
            continue
        active_publication = publication_manifest.workouts.get(
            fulfillment.workout_identity.local_workout_id
        )
        if (
            active_publication is None
            or active_publication.workout_identity != fulfillment.workout_identity
        ):
            continue
        operation = matching_resilio_pair_operation(
            fulfillment_manifest,
            publication=active_publication,
            fulfillment=fulfillment,
        )
        if operation is not None and operation.state != "verified":
            blockers.append(operation.operation_id)
    return sorted(blockers)


def _validate_plan_closure(
    repo: RepositoryIO,
    active_plan: ActivePlanState,
    closure: PlanClosure,
) -> None:
    plan = active_plan.plan
    if not isinstance(plan, RaceMacroPlan):
        raise PlanOperationError("Race-cycle closure cannot close a baseline-assessment plan")
    evidence_reference = EvidenceArtifactReference(
        artifact_type="cycle_review",
        artifact_sha256=closure.cycle_review_artifact_sha256,
    )
    try:
        review = load_evidence_artifact(
            repo,
            evidence_reference,
            PlanCycleReview,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    if review.plan_id != plan.id or review.plan_revision_id != plan.plan_revision_id:
        raise PlanOperationError("Cycle review references another active plan revision")
    if review.active_plan_sha256 != canonical_data_sha256(active_plan):
        raise PlanOperationError("Active plan changed after cycle review")
    if (
        review.effective_end_date != closure.effective_end_date
        or review.goal_outcome != closure.goal_outcome
    ):
        raise PlanOperationError("Plan closure facts do not match the immutable cycle review")
    review_source_window_start = (
        review.compact_weeks[0].week_start
        if review.compact_weeks
        else review.evidence_as_of_date - timedelta(days=review.evidence_as_of_date.weekday())
    )
    review_source_as_of_date = (
        review.compact_weeks[-1].evidence_as_of_date
        if review.compact_weeks
        else review.evidence_as_of_date
    )
    if review.source_state_sha256 != coaching_evidence_source_sha256_unlocked(
        repo,
        evidence_as_of_date=review_source_as_of_date,
        evidence_window_start=review_source_window_start,
    ):
        raise PlanOperationError("Training evidence changed after cycle review")
    closed_local_date = closure.closed_at_utc.astimezone(
        ZoneInfo(plan.constraints_snapshot.training_timezone)
    ).date()
    if closure.effective_end_date > closed_local_date:
        raise PlanOperationError("Plan closure effective date cannot follow closure time")
    if closure.disposition == PlanClosureDisposition.COMPLETED_HORIZON:
        if closure.effective_end_date != plan.end_date:
            raise PlanOperationError("Completed-horizon closure must equal the plan end date")
    elif closure.disposition == PlanClosureDisposition.NEVER_STARTED:
        if review.plan_started:
            raise PlanOperationError("A plan with reviewed training weeks is not never-started")
    elif closure.effective_end_date >= plan.end_date:
        raise PlanOperationError("Midcycle or early-stop closure must predate the plan end date")
    is_general_fitness = str(plan.goal.type) == "general_fitness"
    if is_general_fitness != (closure.goal_outcome.status == "not_applicable"):
        raise PlanOperationError("Only general-fitness plans use a not-applicable goal outcome")
    publication_blockers = _publication_closure_blockers(
        repo,
        active_plan,
        effective_end_date=closure.effective_end_date,
    )
    if publication_blockers:
        raise PlanOperationError(
            "Reconcile unfinished publication intents, future owned workouts, and "
            "native pairing operations before "
            f"closing the plan: {publication_blockers}"
        )


def close_current_plan(
    repo: RepositoryIO,
    *,
    closure: PlanClosure,
) -> PlanningState:
    """Archive the active plan only after exact retrospective evidence exists."""
    with coordinated_publication_plan_activity_lock(repo, "close_current_plan"):
        state = _required_state(repo)
        if state.active_plan is None:
            raise PlanOperationError("No current plan is available to retire")
        _validate_plan_closure(repo, state.active_plan, closure)
        try:
            reference = save_closed_plan_archive(
                repo,
                ClosedPlanArchive(
                    active_plan_snapshot=state.active_plan,
                    closure=closure,
                ),
            )
        except PlanningArtifactError as exc:
            raise PlanOperationError(str(exc)) from exc
        return _persist(
            repo,
            state.model_copy(
                update={
                    "active_plan": None,
                    "closed_plan_references": [
                        *state.closed_plan_references,
                        reference,
                    ],
                }
            ),
        )


def close_current_plan_from_review(
    repo: RepositoryIO,
    *,
    cycle_review_reference: EvidenceArtifactReference,
    disposition: PlanClosureDisposition,
    reason: str,
    athlete_confirmation_reference: str,
    closed_at_utc: datetime | None = None,
) -> PlanningState:
    """Close the active cycle using facts loaded from one immutable review."""
    if cycle_review_reference.artifact_type != "cycle_review":
        raise PlanOperationError("Plan closure requires a cycle-review reference")
    try:
        review = load_evidence_artifact(
            repo,
            cycle_review_reference,
            PlanCycleReview,
        )
    except PlanningArtifactError as exc:
        raise PlanOperationError(str(exc)) from exc
    closure = PlanClosure(
        disposition=disposition,
        effective_end_date=review.effective_end_date,
        reason=reason,
        athlete_confirmation_reference=athlete_confirmation_reference,
        cycle_review_artifact_sha256=(cycle_review_reference.artifact_sha256),
        goal_outcome=review.goal_outcome,
        closed_at_utc=_now_utc(closed_at_utc),
    )
    return close_current_plan(repo, closure=closure)


def create_macro_plan(
    repo: RepositoryIO,
    draft: MacroPlanDraft,
    *,
    created_at_utc: datetime | None = None,
) -> RaceMacroPlan:
    """Create a fresh macro revision from the active VDOT approval and profile."""
    with coordinated_publication_plan_activity_lock(repo, "create_macro_plan"):
        state = _required_state(repo)
        if state.active_plan is not None:
            raise PlanOperationError("A current plan already exists; close it before replacement")
        vdot_approval = _verify_vdot_approval(
            repo, state.active_vdot_approval, activity_lock_held=True
        )
        if draft.vdot_approval_id != vdot_approval.approval_id:
            raise PlanOperationError("Macro draft does not reference the active VDOT approval")
        profile = _load_profile(repo)
        if not _draft_goal_matches_profile(draft, profile):
            raise PlanOperationError(
                "Macro draft goal does not match the athlete-confirmed profile goal"
            )
        context = load_validated_macro_context(
            repo,
            state,
            draft,
            profile,
        )
        profile_hash = planning_inputs_sha256(profile)
        try:
            methodology = resolve_methodology_choice(
                repo.repo_root,
                draft.methodology,
                goal_type=str(draft.goal.type),
            )
        except MethodologyRegistryError as exc:
            raise PlanOperationError(str(exc)) from exc
        creation_timestamp = _now_utc(created_at_utc)
        if creation_timestamp < vdot_approval.approved_at_utc:
            raise PlanOperationError("Macro plan creation cannot predate its VDOT approval")
        if creation_timestamp < context.generated_at_utc:
            raise PlanOperationError("Macro plan creation cannot predate its planning context")
        plan = RaceMacroPlan(
            id=_new_id("plan"),
            plan_revision_id=_new_id("plan_revision"),
            vdot_approval_id=vdot_approval.approval_id,
            planning_context_reference=draft.planning_context_reference,
            planning_inputs_sha256=profile_hash,
            created_at_utc=creation_timestamp,
            planning_rationale=draft.planning_rationale,
            adaptation_decisions=draft.adaptation_decisions,
            goal=draft.goal,
            methodology=methodology,
            weeks=draft.weeks,
            baseline_vdot=vdot_approval.approved_vdot,
            constraints_snapshot=planning_constraints_snapshot(profile),
        )
        for week in draft.weeks:
            validate_long_run_target(week)
        updated = state.model_copy(update={"active_plan": ActivePlanState(plan=plan)})
        require_progression_review_unlocked(
            repo,
            candidate=draft,
            kind="macro",
            binding=context.progression,
            timestamp=creation_timestamp,
            constraints=plan.constraints_snapshot,
        )
        _persist(repo, updated)
        return plan


def approve_current_plan(
    repo: RepositoryIO,
    *,
    approved_at_utc: datetime | None = None,
) -> PlanningState:
    """Bind athlete approval to the current immutable plan skeleton."""
    with coordinated_publication_plan_activity_lock(repo, "approve_current_plan"):
        state = _required_state(repo)
        plan = _require_fresh_plan(repo, state, activity_lock_held=True)
        if state.active_plan is not None and state.active_plan.plan_approval is not None:
            raise PlanOperationError(
                "The current plan is already approved; use an explicit amendment for changes"
            )
        approval_timestamp = _now_utc(approved_at_utc)
        if approval_timestamp < plan.created_at_utc:
            raise PlanOperationError("Plan approval cannot predate plan creation")
        if (
            isinstance(plan, RaceMacroPlan)
            and state.active_plan is not None
            and state.active_plan.plan_approval is None
        ):
            context = load_validated_macro_context(
                repo,
                state,
                macro_draft_from_plan(plan),
                _load_profile(repo),
            )
            require_progression_review_unlocked(
                repo,
                candidate=macro_draft_from_plan(plan),
                kind="macro",
                binding=context.progression,
                timestamp=approval_timestamp,
                constraints=plan.constraints_snapshot,
            )
        approval = PlanApproval(
            approval_id=_new_id("plan_approval"),
            plan_kind=plan.kind,
            plan_id=plan.id,
            plan_revision_id=plan.plan_revision_id,
            plan_skeleton_sha256=plan_skeleton_sha256(plan),
            vdot_approval_id=(plan.vdot_approval_id if isinstance(plan, RaceMacroPlan) else None),
            planning_inputs_sha256=plan.planning_inputs_sha256,
            approved_at_utc=approval_timestamp,
        )
        assert state.active_plan is not None
        active_plan = state.active_plan.model_copy(update={"plan_approval": approval})
        return _persist(
            state=state.model_copy(update={"active_plan": active_plan}),
            repo=repo,
        )
