"""Revision-bound training-plan and approval application services."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

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
    applied_workout_sha256,
    macro_skeleton_sha256,
    planning_constraints_snapshot,
    planning_profile_sha256,
    sha256_file,
    target_week_skeleton_sha256,
)
from resilio.core.planning.policy import (
    WeekPolicyError,
    validate_populated_week,
)
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.planning.state_repository import (
    load_planning_aggregate as load_planning_aggregate,
)
from resilio.core.planning.state_repository import (
    persist_planning_state as _persist,
)
from resilio.core.planning.state_repository import (
    required_planning_state_unlocked as _required_state,
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
from resilio.schemas.approvals import (
    AppliedWeekRevision,
    MacroApproval,
    PlanningState,
    RetiredPlanRevision,
    VDOTApproval,
    WeeklyApplicationAction,
    WeeklyApproval,
)
from resilio.schemas.plan import (
    MacroPlanDraft,
    MasterPlan,
    WeekApplication,
    WeekPlan,
)
from resilio.schemas.profile import AthleteProfile


def _now_utc(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("Planning timestamps must be timezone-aware")
    return timestamp.astimezone(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def load_current_plan(
    repo: RepositoryIO,
    *,
    allow_missing: bool = False,
) -> MasterPlan | None:
    state = load_planning_aggregate(repo, allow_missing=allow_missing)
    if state is None or state.current_plan is None:
        if allow_missing:
            return None
        raise PlanOperationError("No current training plan is available")
    return state.current_plan


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
            approved_at_utc=approval_timestamp,
        )
        state = _required_state(repo)
        retired_revisions = _retire_current_revision(
            state,
            retired_at_utc=approval.approved_at_utc,
            reason="VDOT approval replaced; dependent plan revision retired",
        )
        replacement = state.model_copy(
            update={
                "vdot_approval": approval,
                "current_plan": None,
                "macro_approval": None,
                "pending_weekly_approval": None,
                "applied_week_revisions": [],
                "retired_plan_revisions": retired_revisions,
                "plan_invalidated_at_utc": None,
                "plan_invalidation_reason": None,
            }
        )
        return _persist(repo, replacement)


def _retire_current_revision(
    state: PlanningState,
    *,
    retired_at_utc: datetime,
    reason: str,
) -> list[RetiredPlanRevision]:
    history = list(state.retired_plan_revisions)
    if state.current_plan is not None:
        history.append(
            RetiredPlanRevision(
                plan=state.current_plan,
                macro_approval=state.macro_approval,
                applied_week_revisions=state.applied_week_revisions,
                retired_at_utc=retired_at_utc,
                retirement_reason=reason,
            )
        )
    return history


def retire_current_plan(
    repo: RepositoryIO,
    *,
    reason: str,
    retired_at_utc: datetime | None = None,
) -> PlanningState:
    """Retire the current revision before a deliberate replacement."""
    if len(reason.strip()) < 10:
        raise PlanOperationError("Plan retirement reason must be specific")
    timestamp = _now_utc(retired_at_utc)
    with coordinated_plan_lock(repo, "retire_current_plan"):
        state = _required_state(repo)
        if state.current_plan is None:
            raise PlanOperationError("No current plan is available to retire")
        return _persist(
            repo,
            state.model_copy(
                update={
                    "current_plan": None,
                    "macro_approval": None,
                    "pending_weekly_approval": None,
                    "applied_week_revisions": [],
                    "retired_plan_revisions": _retire_current_revision(
                        state,
                        retired_at_utc=timestamp,
                        reason=reason.strip(),
                    ),
                    "plan_invalidated_at_utc": None,
                    "plan_invalidation_reason": None,
                }
            ),
        )


def create_macro_plan(
    repo: RepositoryIO,
    draft: MacroPlanDraft,
    *,
    created_at_utc: datetime | None = None,
) -> MasterPlan:
    """Create a fresh macro revision from the active VDOT approval and profile."""
    with coordinated_plan_lock(repo, "create_macro_plan"):
        state = _required_state(repo)
        if state.current_plan is not None:
            raise PlanOperationError(
                "A current plan already exists; invalidate it before replacement"
            )
        vdot_approval = _verify_vdot_approval(repo, state.vdot_approval)
        if draft.vdot_approval_id != vdot_approval.approval_id:
            raise PlanOperationError("Macro draft does not reference the active VDOT approval")
        profile = _load_profile(repo)
        if not _draft_goal_matches_profile(draft, profile):
            raise PlanOperationError(
                "Macro draft goal does not match the athlete-confirmed profile goal"
            )
        profile_hash = planning_profile_sha256(profile)
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
            raise PlanOperationError(
                "Macro plan creation cannot predate its VDOT approval"
            )
        plan = MasterPlan(
            id=_new_id("plan"),
            macro_revision_id=_new_id("macro_revision"),
            vdot_approval_id=vdot_approval.approval_id,
            planning_profile_sha256=profile_hash,
            created_at_utc=creation_timestamp,
            goal=draft.goal,
            methodology=methodology,
            weeks=draft.weeks,
            baseline_vdot=vdot_approval.approved_vdot,
            constraints_snapshot=planning_constraints_snapshot(profile),
            conflict_policy=profile.conflict_policy,
        )
        updated = state.model_copy(
            update={
                "current_plan": plan,
                "macro_approval": None,
                "pending_weekly_approval": None,
                "applied_week_revisions": [],
                "plan_invalidated_at_utc": None,
                "plan_invalidation_reason": None,
            }
        )
        _persist(repo, updated)
        return plan


def approve_current_macro_plan(
    repo: RepositoryIO,
    *,
    approved_at_utc: datetime | None = None,
) -> PlanningState:
    """Bind athlete approval to the current immutable macro skeleton."""
    with coordinated_plan_lock(repo, "approve_current_macro_plan"):
        state = _required_state(repo)
        plan = _require_fresh_plan(repo, state)
        assert state.vdot_approval is not None
        approval_timestamp = _now_utc(approved_at_utc)
        if approval_timestamp < plan.created_at_utc:
            raise PlanOperationError(
                "Macro approval cannot predate plan creation"
            )
        approval = MacroApproval(
            approval_id=_new_id("macro_approval"),
            plan_id=plan.id,
            macro_revision_id=plan.macro_revision_id,
            macro_skeleton_sha256=macro_skeleton_sha256(plan),
            vdot_approval_id=state.vdot_approval.approval_id,
            planning_profile_sha256=plan.planning_profile_sha256,
            approved_at_utc=approval_timestamp,
        )
        return _persist(state=state.model_copy(update={"macro_approval": approval}), repo=repo)


def load_week_application(path: Path) -> WeekApplication:
    try:
        return WeekApplication.model_validate_json(path.read_text())
    except OSError as exc:
        raise PlanOperationError(f"Approved week file could not be read: {exc}") from exc
    except ValueError as exc:
        raise PlanOperationError(f"Approved week file is invalid: {exc}") from exc


def validate_week_application(
    repo: RepositoryIO,
    application_file: Path,
) -> WeekApplication:
    """Validate an exact file against the fresh current macro and profile."""
    application = load_week_application(application_file)
    with coordinated_plan_lock(repo, "validate_week_application"):
        state = _required_state(repo)
        plan = _require_fresh_plan(repo, state)
        if state.macro_approval is None:
            raise PlanOperationError("The current macro plan is not approved")
        target_week = _find_week(plan, application.week_number)
        _populate_and_validate_week(plan, target_week, application)
    return application


def _find_week(plan: MasterPlan, week_number: int) -> WeekPlan:
    matching = [week for week in plan.weeks if week.week_number == week_number]
    if len(matching) != 1:
        raise PlanOperationError("Weekly payload does not identify exactly one macro-plan week")
    return matching[0]


def _populate_and_validate_week(
    plan: MasterPlan,
    target_week: WeekPlan,
    application: WeekApplication,
) -> WeekPlan:
    try:
        populated_week = WeekPlan(
            week_number=target_week.week_number,
            phase=target_week.phase,
            start_date=target_week.start_date,
            end_date=target_week.end_date,
            target_run_volume_meters=(target_week.target_run_volume_meters),
            workout_structure_hints=target_week.workout_structure_hints,
            workouts=application.workouts,
            is_recovery_week=target_week.is_recovery_week,
            notes=application.adjustment_rationale,
        )
        validate_populated_week(plan, populated_week)
    except (ValueError, WeekPolicyError) as exc:
        raise PlanOperationError(f"Weekly application violates approved policy: {exc}") from exc
    return populated_week


def approve_week_application(
    repo: RepositoryIO,
    approved_file: Path,
    *,
    approved_at_utc: datetime | None = None,
) -> PlanningState:
    """Bind an exact weekly proposal to its plan, revision, and prior content."""
    resolved_file = approved_file.expanduser().resolve()
    application = load_week_application(resolved_file)
    with coordinated_plan_lock(repo, "approve_week_application"):
        state = _required_state(repo)
        plan = _require_fresh_plan(repo, state)
        macro_approval = state.macro_approval
        if macro_approval is None:
            raise PlanOperationError("The current macro plan is not approved")
        if macro_approval.macro_skeleton_sha256 != macro_skeleton_sha256(plan):
            raise PlanOperationError("The approved macro skeleton has changed")
        week = _find_week(plan, application.week_number)
        _populate_and_validate_week(plan, week, application)
        existing_hash = applied_workout_sha256(week) if week.workouts else None
        action = (
            WeeklyApplicationAction.REPLACE
            if existing_hash is not None
            else WeeklyApplicationAction.INITIAL
        )
        approval_timestamp = _now_utc(approved_at_utc)
        if approval_timestamp < macro_approval.approved_at_utc:
            raise PlanOperationError(
                "Weekly approval cannot predate macro approval"
            )
        approval = WeeklyApproval(
            approval_id=_new_id("week_approval"),
            plan_id=plan.id,
            macro_revision_id=plan.macro_revision_id,
            macro_skeleton_sha256=macro_approval.macro_skeleton_sha256,
            week_number=application.week_number,
            target_week_skeleton_sha256=target_week_skeleton_sha256(week),
            action=action,
            previous_applied_workout_sha256=existing_hash,
            approved_at_utc=approval_timestamp,
            approved_file=str(resolved_file),
            approved_file_sha256=sha256_file(resolved_file),
        )
        return _persist(
            repo,
            state.model_copy(update={"pending_weekly_approval": approval}),
        )


def apply_approved_week(
    repo: RepositoryIO,
    approved_file: Path,
    *,
    applied_at_utc: datetime | None = None,
) -> MasterPlan:
    """Atomically consume an exact-file approval into its bound macro revision."""
    resolved_file = approved_file.expanduser().resolve()
    application = load_week_application(resolved_file)
    with coordinated_plan_lock(repo, "apply_approved_week"):
        state = _required_state(repo)
        plan = _require_fresh_plan(repo, state)
        approval = state.pending_weekly_approval
        if approval is None:
            raise PlanOperationError("Weekly approval is missing")
        if approval.plan_id != plan.id or approval.macro_revision_id != plan.macro_revision_id:
            raise PlanOperationError("Weekly approval references another plan revision")
        if approval.week_number != application.week_number:
            raise PlanOperationError("Approved week number does not match the payload")
        if Path(approval.approved_file) != resolved_file:
            raise PlanOperationError("Approved file path does not match the payload")
        if sha256_file(resolved_file) != approval.approved_file_sha256:
            raise PlanOperationError("Approved week file changed after approval")
        week = _find_week(plan, application.week_number)
        if target_week_skeleton_sha256(week) != approval.target_week_skeleton_sha256:
            raise PlanOperationError("Target macro week changed after approval")
        current_hash = applied_workout_sha256(week) if week.workouts else None
        if current_hash != approval.previous_applied_workout_sha256:
            raise PlanOperationError("Previously applied weekly content changed")
        populated_week = _populate_and_validate_week(
            plan,
            week,
            application,
        )
        updated_plan = MasterPlan.model_validate(
            plan.model_copy(
                update={
                    "weeks": [
                        populated_week
                        if candidate.week_number == populated_week.week_number
                        else candidate
                        for candidate in plan.weeks
                    ]
                }
            ).model_dump(mode="python", by_alias=True)
        )
        applied_revisions = list(state.applied_week_revisions)
        previous = next(
            (
                item
                for item in applied_revisions
                if item.week_number == application.week_number and item.active
            ),
            None,
        )
        timestamp = _now_utc(applied_at_utc)
        if timestamp < approval.approved_at_utc:
            raise PlanOperationError(
                "Weekly application cannot predate its weekly approval"
            )
        if previous is not None and previous.active:
            applied_revisions = [
                item.model_copy(
                    update={
                        "active": False,
                        "invalidated_at_utc": timestamp,
                        "invalidation_reason": "replaced_by_new_week_approval",
                    }
                )
                if item.approval_id == previous.approval_id
                else item
                for item in applied_revisions
            ]
        profile = _load_profile(repo)
        applied_revisions.append(
            AppliedWeekRevision(
                approval_id=approval.approval_id,
                plan_id=plan.id,
                macro_revision_id=plan.macro_revision_id,
                week_number=application.week_number,
                approved_file_sha256=approval.approved_file_sha256,
                applied_workout_sha256=applied_workout_sha256(populated_week),
                applied_week_snapshot=populated_week,
                schedule_timezone=profile.training_timezone,
                weekly_approved_at_utc=approval.approved_at_utc,
                applied_at_utc=timestamp,
            )
        )
        _persist(
            repo,
            state.model_copy(
                update={
                    "current_plan": updated_plan,
                    "pending_weekly_approval": None,
                    "applied_week_revisions": applied_revisions,
                }
            ),
        )
        return updated_plan
