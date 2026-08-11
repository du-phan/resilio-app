"""Strict planning-evidence cutover for the workout-fulfillment migration."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from resilio.core.planning.artifacts import (
    EVIDENCE_DIRECTORY,
    archive_path,
    canonical_data_sha256,
    evidence_path,
    model_sha256,
)
from resilio.core.planning.assessment_evidence import (
    verify_assessment_result_source,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.source_state import (
    coaching_evidence_source_sha256_unlocked,
)
from resilio.core.planning.state_repository import load_planning_aggregate_unlocked
from resilio.core.repository import RepositoryIO
from resilio.core.workout_fulfillment.legacy_source_state import (
    legacy_coaching_evidence_source_sha256_unlocked,
)
from resilio.core.workout_fulfillment.planning_evidence_migration_models import (
    PlanningEvidenceHashMigration,
    PlanningEvidenceMigrationAudit,
    PlanningEvidenceMigrationResult,
    PlanSkeletonHashMigration,
    ProposalFileHashMigration,
)
from resilio.core.workout_fulfillment.planning_evidence_transform import (
    contains_legacy_planning_contracts,
    fulfillment_index,
    migrate_embedded_planning_contracts,
)
from resilio.core.workout_fulfillment.planning_proposal_migration import (
    PlanningProposalMigration,
)
from resilio.core.workout_fulfillment.planning_state_migration import (
    PlanningEvidenceMigrationError as PlanningEvidenceMigrationError,
)
from resilio.core.workout_fulfillment.planning_state_migration import (
    load_closed_archives,
    migrate_active_plan,
    migrate_closed_plan_history,
)
from resilio.schemas.approvals import (
    ClosedPlanArchive,
    PlanningState,
)
from resilio.schemas.coaching import WeekPlanningContext
from resilio.schemas.plan_history import (
    BaselineAssessmentResult,
    EvidenceArtifactReference,
)
from resilio.schemas.planning_evidence import (
    AssessmentPlanningContext,
    BaselineAssessmentReview,
    MacroPlanningContext,
    PlanCycleReview,
)
from resilio.schemas.publication import PublicationManifest
from resilio.schemas.workout_fulfillment import WorkoutFulfillmentManifest

ArtifactKey = tuple[str, str]

ARTIFACT_SCHEMAS: dict[str, type[BaseModel]] = {
    "cycle_review": PlanCycleReview,
    "macro_planning_context": MacroPlanningContext,
    "assessment_planning_context": AssessmentPlanningContext,
    "week_planning_context": WeekPlanningContext,
    "assessment_review": BaselineAssessmentReview,
}


def _raw_model_sha256(payload: dict[str, Any]) -> str:
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class _ArtifactGraphMigration:
    def __init__(
        self,
        repo: RepositoryIO,
        fulfillment_manifest: WorkoutFulfillmentManifest,
        publication_manifest: PublicationManifest,
        legacy_completion_raw: dict[str, Any] | None,
        legacy_publication_raw: dict[str, Any] | None,
    ):
        self.repo = repo
        self.fulfillment_index = fulfillment_index(fulfillment_manifest)
        self.fulfillment_manifest = fulfillment_manifest
        self.publication_manifest = publication_manifest
        self.legacy_completion_raw = legacy_completion_raw
        self.legacy_publication_raw = legacy_publication_raw
        self.raw_by_key = self._load_raw_artifacts()
        self.reference_by_key: dict[ArtifactKey, EvidenceArtifactReference] = {}
        self.model_by_path: dict[str, BaseModel] = {}
        self.visiting: set[ArtifactKey] = set()
        self.blocked_cycle_review_keys: set[ArtifactKey] = set()
        self.validated_closed_assessment_review_keys: set[ArtifactKey] = set()

    def _load_raw_artifacts(self) -> dict[ArtifactKey, dict[str, Any]]:
        root = self.repo.resolve_path(EVIDENCE_DIRECTORY)
        if not root.exists():
            return {}
        loaded: dict[ArtifactKey, dict[str, Any]] = {}
        for path in root.rglob("*.json"):
            if not path.is_file() or path.is_symlink():
                raise PlanningEvidenceMigrationError(
                    f"Planning evidence path is not a regular file: {path}"
                )
            artifact_type = path.parent.name
            if artifact_type not in ARTIFACT_SCHEMAS:
                raise PlanningEvidenceMigrationError(
                    f"Unknown planning evidence artifact type: {artifact_type}"
                )
            try:
                raw = json.loads(path.read_text())
            except (OSError, ValueError) as exc:
                raise PlanningEvidenceMigrationError(
                    f"Planning evidence artifact is not valid JSON: {path}"
                ) from exc
            if not isinstance(raw, dict) or _raw_model_sha256(raw) != path.stem:
                raise PlanningEvidenceMigrationError(
                    f"Planning evidence artifact hash is invalid: {path}"
                )
            loaded[(artifact_type, path.stem)] = raw
        return loaded

    def _replace_embedded_references(self, value: Any) -> None:
        if isinstance(value, dict):
            if set(("artifact_type", "artifact_sha256")).issubset(value):
                reference = EvidenceArtifactReference.model_validate(value)
                key = (reference.artifact_type, reference.artifact_sha256)
                if reference.artifact_type == "week_planning_context":
                    raise PlanningEvidenceMigrationError(
                        "Planning evidence cannot contain a backward week-context reference"
                    )
                if key in self.blocked_cycle_review_keys and key not in self.reference_by_key:
                    raise PlanningEvidenceMigrationError(
                        "Planning evidence references a cycle review before its plan archive"
                    )
                migrated = self.migrate(reference)
                value.update(migrated.model_dump(mode="json"))
                return
            for child in value.values():
                self._replace_embedded_references(child)
        elif isinstance(value, list):
            for child in value:
                self._replace_embedded_references(child)

    def source_payload(self, reference: EvidenceArtifactReference) -> dict[str, Any]:
        """Return immutable pre-transform bytes for contextual authority checks."""
        raw = self.raw_by_key.get((reference.artifact_type, reference.artifact_sha256))
        if raw is None:
            raise PlanningEvidenceMigrationError("Referenced planning evidence artifact is missing")
        return copy.deepcopy(raw)

    def validate_assessment_result_source(
        self,
        reference: EvidenceArtifactReference,
    ) -> None:
        """Re-prove closed assessment result evidence before rebinding hashes."""
        review = self._source_assessment_review(reference)
        try:
            verify_assessment_result_source(
                self.repo,
                review,
                publication_manifest=self.publication_manifest,
                fulfillment_manifest=self.fulfillment_manifest,
            )
        except (PlanOperationError, ValueError) as exc:
            raise PlanningEvidenceMigrationError(
                f"Assessment result source is invalid before migration: {exc}"
            ) from exc

    def _source_assessment_review(
        self,
        reference: EvidenceArtifactReference,
    ) -> BaselineAssessmentReview:
        if reference.artifact_type != "assessment_review":
            raise PlanningEvidenceMigrationError(
                "Owned assessment evidence must reference an assessment review"
            )
        raw = self.source_payload(reference)
        migrate_embedded_planning_contracts(
            raw,
            evidence_by_identity=self.fulfillment_index,
        )
        raw.pop("source_context_sha256", None)
        try:
            return BaselineAssessmentReview.model_validate(raw)
        except ValueError as exc:
            raise PlanningEvidenceMigrationError(
                f"Assessment review is invalid before migration: {exc}"
            ) from exc

    def validate_owned_assessment_evidence(
        self,
        reference: EvidenceArtifactReference,
        result: BaselineAssessmentResult,
        *,
        require_closed_archive: bool,
    ) -> None:
        """Prove proposal evidence is the exact result in its referenced review."""
        key = (reference.artifact_type, reference.artifact_sha256)
        if require_closed_archive and key not in self.validated_closed_assessment_review_keys:
            raise PlanningEvidenceMigrationError(
                "Approved VDOT assessment review does not belong to a closed assessment archive"
            )
        review = self._source_assessment_review(reference)
        if review.result != result:
            raise PlanningEvidenceMigrationError(
                "VDOT assessment evidence differs from its referenced review"
            )

    def mark_closed_assessment_review_validated(
        self,
        reference: EvidenceArtifactReference,
    ) -> None:
        """Record exact closure ownership after its complete source proof passes."""
        self.validated_closed_assessment_review_keys.add(
            (reference.artifact_type, reference.artifact_sha256)
        )

    def migrate(
        self,
        reference: EvidenceArtifactReference,
        *,
        active_plan_sha256: str | None = None,
        plan_skeleton_sha256_by_previous: dict[str, str] | None = None,
    ) -> EvidenceArtifactReference:
        key = (reference.artifact_type, reference.artifact_sha256)
        existing = self.reference_by_key.get(key)
        if existing is not None:
            return existing
        raw_source = self.raw_by_key.get(key)
        if raw_source is None:
            raise PlanningEvidenceMigrationError("Referenced planning evidence artifact is missing")
        if key in self.visiting:
            raise PlanningEvidenceMigrationError("Planning evidence references form a cycle")
        self.visiting.add(key)
        raw = copy.deepcopy(raw_source)
        legacy_contract = contains_legacy_planning_contracts(raw)
        try:
            legacy_source_is_current = True
            if legacy_contract and "source_state_sha256" in raw:
                try:
                    expected_legacy_source_sha256 = self._legacy_source_state_sha256(
                        reference.artifact_type,
                        raw,
                    )
                except (PlanOperationError, ValueError):
                    legacy_source_is_current = False
                else:
                    legacy_source_is_current = (
                        raw["source_state_sha256"] == expected_legacy_source_sha256
                    )
            self._replace_embedded_references(raw)
            migrate_embedded_planning_contracts(
                raw,
                evidence_by_identity=self.fulfillment_index,
            )
            raw.pop("source_context_sha256", None)
            if legacy_contract and "source_state_sha256" in raw:
                raw["source_state_sha256"] = (
                    self._source_state_sha256(reference.artifact_type, raw)
                    if legacy_source_is_current
                    else canonical_data_sha256(
                        {"invalidated_legacy_source_state_sha256": raw["source_state_sha256"]}
                    )
                )
            if active_plan_sha256 is not None:
                if reference.artifact_type not in {
                    "cycle_review",
                    "assessment_review",
                }:
                    raise PlanningEvidenceMigrationError(
                        "Only closure-review evidence may bind an active-plan hash"
                    )
                raw["active_plan_sha256"] = active_plan_sha256
            if reference.artifact_type == "week_planning_context":
                target = raw.get("target_week")
                if not isinstance(target, dict):
                    raise PlanningEvidenceMigrationError(
                        "Week-planning context lacks its target-week evidence"
                    )
                previous = target.get("plan_skeleton_sha256")
                if plan_skeleton_sha256_by_previous and previous in (
                    plan_skeleton_sha256_by_previous
                ):
                    target["plan_skeleton_sha256"] = plan_skeleton_sha256_by_previous[str(previous)]
            schema = ARTIFACT_SCHEMAS[reference.artifact_type]
            model = schema.model_validate(raw)
        except PlanningEvidenceMigrationError:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise PlanningEvidenceMigrationError(
                f"Planning evidence cannot be migrated: {reference.artifact_type}"
            ) from exc
        finally:
            self.visiting.remove(key)
        digest = model_sha256(model)
        migrated = EvidenceArtifactReference(
            artifact_type=reference.artifact_type,
            artifact_sha256=digest,
        )
        self.reference_by_key[key] = migrated
        if migrated != reference:
            self.model_by_path[evidence_path(migrated)] = model
        return migrated

    def _legacy_source_state_sha256(
        self,
        artifact_type: str,
        raw: dict[str, Any],
    ) -> str:
        evidence_as_of_date, evidence_window_start = self._source_window(
            artifact_type,
            raw,
        )
        return legacy_coaching_evidence_source_sha256_unlocked(
            self.repo,
            evidence_as_of_date=evidence_as_of_date,
            evidence_window_start=evidence_window_start,
            legacy_completion_raw=self.legacy_completion_raw,
            legacy_publication_raw=self.legacy_publication_raw,
        )

    def _source_state_sha256(
        self,
        artifact_type: str,
        raw: dict[str, Any],
    ) -> str:
        evidence_as_of_date, evidence_window_start = self._source_window(
            artifact_type,
            raw,
        )
        return coaching_evidence_source_sha256_unlocked(
            self.repo,
            evidence_as_of_date=evidence_as_of_date,
            evidence_window_start=evidence_window_start,
            fulfillment_manifest=self.fulfillment_manifest,
            publication_manifest=self.publication_manifest,
        )

    @staticmethod
    def _source_window(
        artifact_type: str,
        raw: dict[str, Any],
    ) -> tuple[date, date | None]:
        evidence_as_of_date = date.fromisoformat(str(raw["evidence_as_of_date"]))
        evidence_window_start: date | None = None
        if artifact_type == "week_planning_context":
            evidence_window_start = date.fromisoformat(
                str(raw["recent_history"]["evidence_window_start"])
            )
        elif artifact_type == "assessment_review":
            evidence_window_start = date.fromisoformat(str(raw["plan_start_date"]))
        elif artifact_type == "cycle_review":
            compact_weeks = raw.get("compact_weeks", [])
            if compact_weeks:
                evidence_window_start = date.fromisoformat(str(compact_weeks[0]["week_start"]))
                evidence_as_of_date = date.fromisoformat(
                    str(compact_weeks[-1]["evidence_as_of_date"])
                )
            else:
                evidence_window_start = evidence_as_of_date - timedelta(
                    days=evidence_as_of_date.weekday()
                )
        return evidence_as_of_date, evidence_window_start


def _prepared_migration_result(
    *,
    repo: RepositoryIO,
    state: PlanningState | None,
    migrated_state: PlanningState | None,
    migrated_archives: dict[str, ClosedPlanArchive],
    graph: _ArtifactGraphMigration,
    proposals: PlanningProposalMigration,
    skeleton_migrations: list[PlanSkeletonHashMigration],
) -> PlanningEvidenceMigrationResult:
    artifact_migrations = [
        PlanningEvidenceHashMigration(
            artifact_type=artifact_type,
            previous_artifact_sha256=previous_sha256,
            current_artifact_sha256=migrated.artifact_sha256,
        )
        for (artifact_type, previous_sha256), migrated in sorted(graph.reference_by_key.items())
        if migrated.artifact_sha256 != previous_sha256
    ]
    proposal_file_migrations = [
        ProposalFileHashMigration(
            previous_file=previous_file,
            current_relative_path=current_relative_path,
            previous_file_sha256=previous_sha256,
            current_file_sha256=current_sha256,
        )
        for previous_file, current_relative_path, previous_sha256, current_sha256 in sorted(
            proposals.file_migrations
        )
    ]
    state_changed = migrated_state != state
    archive_changed = state is not None and any(
        model_sha256(migrated_archives[archive_path(reference.plan_id)]) != reference.archive_sha256
        for reference in state.closed_plan_references
    )
    if (
        not artifact_migrations
        and not skeleton_migrations
        and not proposal_file_migrations
        and not state_changed
        and not archive_changed
    ):
        return PlanningEvidenceMigrationResult(state, {}, {}, {}, (), None)
    audit = PlanningEvidenceMigrationAudit(
        artifact_migrations=artifact_migrations,
        plan_skeleton_migrations=skeleton_migrations,
        proposal_file_migrations=proposal_file_migrations,
    )
    obsolete_artifact_paths = tuple(
        evidence_path(
            EvidenceArtifactReference.model_validate(
                {
                    "artifact_type": item.artifact_type,
                    "artifact_sha256": item.previous_artifact_sha256,
                }
            )
        )
        for item in artifact_migrations
    )
    return PlanningEvidenceMigrationResult(
        planning_state=migrated_state,
        closed_archives_by_relative_path=migrated_archives,
        new_artifacts_by_relative_path=graph.model_by_path,
        rewritten_proposals_by_relative_path=(proposals.rewritten_bytes_by_relative_path),
        obsolete_artifact_relative_paths=obsolete_artifact_paths,
        audit=audit,
    )


def prepare_planning_evidence_migration(
    repo: RepositoryIO,
    *,
    fulfillment_manifest: WorkoutFulfillmentManifest,
    publication_manifest: PublicationManifest,
    legacy_completion_raw: dict[str, Any] | None = None,
    legacy_publication_raw: dict[str, Any] | None = None,
) -> PlanningEvidenceMigrationResult:
    """Prepare a lossless strict-schema graph rewrite without writing any state."""
    state = load_planning_aggregate_unlocked(repo, allow_missing=True)
    graph = _ArtifactGraphMigration(
        repo,
        fulfillment_manifest,
        publication_manifest,
        legacy_completion_raw,
        legacy_publication_raw,
    )
    proposals = PlanningProposalMigration(repo, graph)
    skeleton_migrations: list[PlanSkeletonHashMigration] = []
    if state is None:
        for key in graph.raw_by_key:
            graph.migrate(
                EvidenceArtifactReference.model_validate(
                    {"artifact_type": key[0], "artifact_sha256": key[1]}
                )
            )
        proposals.migrate_all()
        return _prepared_migration_result(
            repo=repo,
            state=None,
            migrated_state=None,
            migrated_archives={},
            graph=graph,
            proposals=proposals,
            skeleton_migrations=skeleton_migrations,
        )
    migrated_archives, migrated_closed_references = migrate_closed_plan_history(
        state,
        load_closed_archives(repo, state),
        graph,
        proposals,
        skeleton_migrations,
    )
    current_active_plan = (
        migrate_active_plan(
            state.active_plan,
            graph,
            proposals,
            skeleton_migrations,
        )
        if state.active_plan is not None
        else None
    )
    for key in graph.raw_by_key:
        if key not in graph.reference_by_key:
            graph.migrate(
                EvidenceArtifactReference.model_validate(
                    {"artifact_type": key[0], "artifact_sha256": key[1]}
                )
            )
    migrated_vdot_approvals = [
        proposals.migrate_vdot_approval(approval) for approval in state.vdot_approvals
    ]
    proposals.migrate_all()
    migrated_state = PlanningState.model_validate(
        state.model_copy(
            update={
                "vdot_approvals": migrated_vdot_approvals,
                "active_plan": current_active_plan,
                "closed_plan_references": migrated_closed_references,
            }
        ).model_dump(mode="python")
    )
    return _prepared_migration_result(
        repo=repo,
        state=state,
        migrated_state=migrated_state,
        migrated_archives=migrated_archives,
        graph=graph,
        proposals=proposals,
        skeleton_migrations=skeleton_migrations,
    )
