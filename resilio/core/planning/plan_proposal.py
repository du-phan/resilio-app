"""Safe replacement boundary for an unapproved active plan proposal."""

from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.state_repository import (
    persist_planning_state,
    required_planning_state_unlocked,
)
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.repository import load_fulfillment_manifest
from resilio.core.workout_publication.locking import coordinated_publication_plan_lock
from resilio.core.workout_publication.manifest import load_manifest
from resilio.schemas.approvals import PlanningState
from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.workout_fulfillment import (
    HistoricalLegacyWorkoutFulfillment,
    WorkoutFulfillmentRecord,
)


def _belongs_to_plan_revision(
    identity: PlanWorkoutIdentity,
    *,
    plan_id: str,
    plan_revision_id: str,
) -> bool:
    return identity.plan_id == plan_id and identity.plan_revision_id == plan_revision_id


def _publication_ownership_identities(repo: RepositoryIO) -> list[PlanWorkoutIdentity]:
    manifest = load_manifest(repo)
    return [
        *(record.workout_identity for record in manifest.workouts.values()),
        *(record.workout_identity for record in manifest.pending.values()),
        *(record.publication.workout_identity for record in manifest.retired.values()),
        *(record.publication.workout_identity for record in manifest.retirement_history),
        *(
            record.pending_publication.workout_identity
            for record in manifest.retired_pending.values()
        ),
        *(
            record.pending_publication.workout_identity
            for record in manifest.pending_retirement_history
        ),
        *(record.workout_identity for record in manifest.historical_legacy_workouts.values()),
    ]


def _fulfillment_ownership_records(
    repo: RepositoryIO,
) -> list[WorkoutFulfillmentRecord | HistoricalLegacyWorkoutFulfillment]:
    manifest = load_fulfillment_manifest(repo)
    return [
        *manifest.fulfillments.values(),
        *manifest.historical_legacy_fulfillments.values(),
        *(revocation.fulfillment for revocation in manifest.revoked_fulfillments),
    ]


def discard_unapproved_current_plan(
    repo: RepositoryIO,
    *,
    expected_plan_revision_id: str,
) -> PlanningState:
    """Discard only the exact proposal proven never approved, applied, or published."""
    with coordinated_publication_plan_lock(repo, "discard_unapproved_current_plan"):
        state = required_planning_state_unlocked(repo)
        active_plan = state.active_plan
        if active_plan is None:
            raise PlanOperationError("No current plan proposal is available to discard")
        plan = active_plan.plan
        if plan.plan_revision_id != expected_plan_revision_id:
            raise PlanOperationError(
                "Current plan revision differs from the proposal selected for discard"
            )
        if active_plan.plan_approval is not None:
            raise PlanOperationError(
                "An approved plan requires evidence-backed closure and cannot be discarded"
            )
        if active_plan.pending_weekly_approval is not None:
            raise PlanOperationError("A plan with a pending weekly approval cannot be discarded")
        if active_plan.applied_week_revisions:
            raise PlanOperationError("A plan with applied week revisions cannot be discarded")

        published_ids = sorted(
            identity.local_workout_id
            for identity in _publication_ownership_identities(repo)
            if _belongs_to_plan_revision(
                identity,
                plan_id=plan.id,
                plan_revision_id=plan.plan_revision_id,
            )
        )
        fulfilled_activity_ids = sorted(
            record.local_activity_id
            for record in _fulfillment_ownership_records(repo)
            if _belongs_to_plan_revision(
                record.workout_identity,
                plan_id=plan.id,
                plan_revision_id=plan.plan_revision_id,
            )
        )
        if published_ids or fulfilled_activity_ids:
            raise PlanOperationError(
                "Plan ownership records exist and must be reconciled before discard: "
                f"published={published_ids}, fulfilled={fulfilled_activity_ids}"
            )
        return persist_planning_state(
            repo,
            state.model_copy(update={"active_plan": None}),
        )
