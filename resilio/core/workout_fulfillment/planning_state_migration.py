"""Planning-state and closed-plan graph rewrite for fulfillment cutover."""

from typing import Any, Protocol

from resilio.core.planning.artifacts import (
    PlanningArtifactError,
    archive_path,
    canonical_data_sha256,
    load_all_closed_plan_archives,
    model_sha256,
)
from resilio.core.planning.integrity import (
    applied_running_workouts_sha256,
    plan_skeleton_sha256,
)
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.planning_evidence_migration_models import (
    PlanSkeletonHashMigration,
)
from resilio.core.workout_fulfillment.planning_proposal_migration import (
    PlanningProposalMigration,
)
from resilio.schemas.approvals import ActivePlanState, ClosedPlanArchive, PlanningState
from resilio.schemas.plan_history import (
    AssessmentClosure,
    EvidenceArtifactReference,
    PlanClosure,
)


class PlanningEvidenceMigrationError(ValueError):
    """Planning evidence cannot be rewritten without preserving exact meaning."""


class PlanningArtifactGraph(Protocol):
    blocked_cycle_review_keys: set[tuple[str, str]]

    def migrate(
        self,
        reference: EvidenceArtifactReference,
        *,
        active_plan_sha256: str | None = None,
        plan_skeleton_sha256_by_previous: dict[str, str] | None = None,
    ) -> EvidenceArtifactReference:
        ...

    def source_payload(
        self,
        reference: EvidenceArtifactReference,
    ) -> dict[str, Any]:
        ...

    def validate_assessment_result_source(
        self,
        reference: EvidenceArtifactReference,
    ) -> None:
        ...

    def mark_closed_assessment_review_validated(
        self,
        reference: EvidenceArtifactReference,
    ) -> None:
        ...


def _validate_source_review_binding(
    *,
    archive: ClosedPlanArchive,
    reference: EvidenceArtifactReference,
    graph: PlanningArtifactGraph,
) -> None:
    raw = graph.source_payload(reference)
    active_plan = archive.active_plan_snapshot
    plan = active_plan.plan
    if (
        raw.get("plan_id") != plan.id
        or raw.get("plan_revision_id") != plan.plan_revision_id
        or raw.get("active_plan_sha256") != canonical_data_sha256(active_plan)
    ):
        raise PlanningEvidenceMigrationError(
            "Closure review did not match its source plan before migration"
        )
    closure = archive.closure
    if isinstance(closure, PlanClosure):
        if raw.get("effective_end_date") != closure.effective_end_date.isoformat() or raw.get(
            "goal_outcome"
        ) != closure.goal_outcome.model_dump(mode="json"):
            raise PlanningEvidenceMigrationError(
                "Cycle review did not match its source closure before migration"
            )
        return
    result = raw.get("result")
    benchmark_intent = getattr(plan, "benchmark_intent", None)
    if (
        not isinstance(result, dict)
        or result.get("performance_date") != closure.effective_end_date.isoformat()
        or benchmark_intent is None
        or raw.get("benchmark_intent") != benchmark_intent.model_dump(mode="json")
    ):
        raise PlanningEvidenceMigrationError(
            "Assessment review did not match its source closure before migration"
        )
    graph.validate_assessment_result_source(reference)
    graph.mark_closed_assessment_review_validated(reference)


def migrate_active_plan(
    active_plan: ActivePlanState,
    graph: PlanningArtifactGraph,
    proposals: PlanningProposalMigration,
    skeleton_migrations: list[PlanSkeletonHashMigration],
) -> ActivePlanState:
    previous_skeleton_sha256 = plan_skeleton_sha256(active_plan.plan)
    if (
        active_plan.plan_approval is not None
        and active_plan.plan_approval.plan_skeleton_sha256 != previous_skeleton_sha256
    ):
        raise PlanningEvidenceMigrationError(
            "Approved plan skeleton changed before fulfillment migration"
        )
    for revision in active_plan.applied_week_revisions:
        if (
            revision.plan_id != active_plan.plan.id
            or revision.plan_revision_id != active_plan.plan.plan_revision_id
            or revision.applied_running_workouts_sha256
            != applied_running_workouts_sha256(revision.applied_week_snapshot)
        ):
            raise PlanningEvidenceMigrationError(
                "Applied-week evidence changed before fulfillment migration"
            )
    migrated_context = graph.migrate(active_plan.plan.planning_context_reference)
    migrated_plan = active_plan.plan.model_copy(
        update={"planning_context_reference": migrated_context}
    )
    current_skeleton_sha256 = plan_skeleton_sha256(migrated_plan)
    if current_skeleton_sha256 != previous_skeleton_sha256:
        skeleton_migrations.append(
            PlanSkeletonHashMigration(
                plan_id=migrated_plan.id,
                plan_revision_id=migrated_plan.plan_revision_id,
                previous_plan_skeleton_sha256=previous_skeleton_sha256,
                current_plan_skeleton_sha256=current_skeleton_sha256,
            )
        )
    skeleton_map = {previous_skeleton_sha256: current_skeleton_sha256}
    migrated_revisions = [
        revision.model_copy(
            update={
                "planning_context_reference": graph.migrate(
                    revision.planning_context_reference,
                    plan_skeleton_sha256_by_previous=skeleton_map,
                )
            }
        )
        for revision in active_plan.applied_week_revisions
    ]
    migrated_approval = active_plan.plan_approval
    if migrated_approval is not None:
        migrated_approval = migrated_approval.model_copy(
            update={"plan_skeleton_sha256": current_skeleton_sha256}
        )
    pending_approval = active_plan.pending_weekly_approval
    if pending_approval is not None and (
        current_skeleton_sha256 != previous_skeleton_sha256
        or proposals.pending_file_requires_reapproval(
            pending_approval.approved_file,
            pending_approval.approved_file_sha256,
        )
    ):
        raise PlanningEvidenceMigrationError(
            "Discard or apply the pending weekly approval before fulfillment migration"
        )
    return ActivePlanState.model_validate(
        active_plan.model_copy(
            update={
                "plan": migrated_plan,
                "plan_approval": migrated_approval,
                "pending_weekly_approval": pending_approval,
                "applied_week_revisions": migrated_revisions,
            }
        ).model_dump(mode="python")
    )


def load_closed_archives(
    repo: RepositoryIO,
    state: PlanningState,
) -> list[ClosedPlanArchive]:
    try:
        return load_all_closed_plan_archives(repo, state.closed_plan_references)
    except PlanningArtifactError as exc:
        raise PlanningEvidenceMigrationError(
            "Closed-plan archive is missing, changed, or invalid"
        ) from exc


def migrate_closed_plan_history(
    state: PlanningState,
    archives: list[ClosedPlanArchive],
    graph: PlanningArtifactGraph,
    proposals: PlanningProposalMigration,
    skeleton_migrations: list[PlanSkeletonHashMigration],
) -> tuple[dict[str, ClosedPlanArchive], list[Any]]:
    graph.blocked_cycle_review_keys = {
        ("cycle_review", archive.closure.cycle_review_artifact_sha256)
        for archive in archives
        if isinstance(archive.closure, PlanClosure)
    }
    migrated_archives: dict[str, ClosedPlanArchive] = {}
    migrated_closed_references: list[Any] = []
    for closed_reference, archive in sorted(
        zip(state.closed_plan_references, archives, strict=True),
        key=lambda item: item[0].closed_at_utc,
    ):
        migrated_active_plan = migrate_active_plan(
            archive.active_plan_snapshot,
            graph,
            proposals,
            skeleton_migrations,
        )
        closure = archive.closure
        if isinstance(closure, PlanClosure):
            previous_review = EvidenceArtifactReference(
                artifact_type="cycle_review",
                artifact_sha256=closure.cycle_review_artifact_sha256,
            )
            graph.blocked_cycle_review_keys.discard(
                (previous_review.artifact_type, previous_review.artifact_sha256)
            )
            _validate_source_review_binding(
                archive=archive,
                reference=previous_review,
                graph=graph,
            )
            migrated_review = graph.migrate(
                previous_review,
                active_plan_sha256=canonical_data_sha256(migrated_active_plan),
            )
            closure = closure.model_copy(
                update={"cycle_review_artifact_sha256": migrated_review.artifact_sha256}
            )
        elif isinstance(closure, AssessmentClosure):
            previous_review = EvidenceArtifactReference(
                artifact_type="assessment_review",
                artifact_sha256=closure.assessment_review_artifact_sha256,
            )
            _validate_source_review_binding(
                archive=archive,
                reference=previous_review,
                graph=graph,
            )
            migrated_review = graph.migrate(
                previous_review,
                active_plan_sha256=canonical_data_sha256(migrated_active_plan),
            )
            closure = closure.model_copy(
                update={"assessment_review_artifact_sha256": migrated_review.artifact_sha256}
            )
        migrated_archive = ClosedPlanArchive.model_validate(
            archive.model_copy(
                update={
                    "active_plan_snapshot": migrated_active_plan,
                    "closure": closure,
                }
            ).model_dump(mode="python")
        )
        migrated_archives[archive_path(closed_reference.plan_id)] = migrated_archive
        migrated_closed_references.append(
            closed_reference.model_copy(update={"archive_sha256": model_sha256(migrated_archive)})
        )
    return migrated_archives, migrated_closed_references
