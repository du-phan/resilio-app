"""Rewrite managed plan proposal references during fulfillment cutover."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from resilio.core.planning.artifacts import canonical_json_bytes
from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import (
    OwnedBaselineAssessmentVDOTEvidence,
    VDOTApproval,
    VDOTProposal,
)
from resilio.schemas.macro_plan_draft import MacroPlanDraft
from resilio.schemas.plan_history import BaselineAssessmentResult, EvidenceArtifactReference
from resilio.schemas.planning.applications import WeekApplication
from resilio.schemas.planning.drafts import AssessmentPlanDraft

PROPOSALS_DIRECTORY = "data/plans/proposals"


class PlanningProposalMigrationError(ValueError):
    """A managed proposal reference cannot be migrated exactly."""


class ArtifactReferenceMigrator(Protocol):
    def migrate(
        self,
        reference: EvidenceArtifactReference,
        *,
        active_plan_sha256: str | None = None,
        plan_skeleton_sha256_by_previous: dict[str, str] | None = None,
    ) -> EvidenceArtifactReference:
        ...

    def validate_owned_assessment_evidence(
        self,
        reference: EvidenceArtifactReference,
        result: BaselineAssessmentResult,
        *,
        require_closed_archive: bool,
    ) -> None:
        ...


def _proposal_model(raw: dict[str, object]) -> BaseModel:
    if "proposed_vdot" in raw and "evidence" in raw:
        return VDOTProposal.model_validate(raw)
    if "week_number" in raw and "running_workouts" in raw:
        return WeekApplication.model_validate(raw)
    if "assessment_reasons" in raw and "benchmark_intent" in raw:
        return AssessmentPlanDraft.model_validate(raw)
    if "methodology" in raw and "vdot_approval_id" in raw:
        return MacroPlanDraft.model_validate(raw)
    raise PlanningProposalMigrationError(
        "Managed proposal with planning evidence has an unknown contract"
    )


class PlanningProposalMigration:
    def __init__(self, repo: RepositoryIO, graph: ArtifactReferenceMigrator):
        self.repo = repo
        self.graph = graph
        self.raw_bytes_by_path = self._load_reference_holders()
        self.rewritten_bytes_by_relative_path: dict[str, bytes] = {}
        self.current_sha256_by_previous: dict[str, str] = {}
        self.file_migrations: list[tuple[str, str, str, str]] = []

    def _load_reference_holders(self) -> dict[Path, bytes]:
        root = self.repo.resolve_path(PROPOSALS_DIRECTORY)
        if not root.exists():
            return {}
        holders: dict[Path, bytes] = {}
        for path in root.glob("*.json"):
            if not path.is_file() or path.is_symlink():
                raise PlanningProposalMigrationError(
                    f"Managed proposal path is not a regular file: {path}"
                )
            raw_bytes = path.read_bytes()
            try:
                raw = json.loads(raw_bytes)
            except ValueError as exc:
                raise PlanningProposalMigrationError(
                    f"Managed proposal is not valid JSON: {path}"
                ) from exc
            is_vdot_review_holder = (
                isinstance(raw, dict)
                and isinstance(raw.get("evidence"), dict)
                and raw["evidence"].get("evidence_type") == "owned_baseline_assessment"
            )
            if isinstance(raw, dict) and (
                "planning_context_reference" in raw or is_vdot_review_holder
            ):
                _proposal_model(raw)
                holders[path] = raw_bytes
        return holders

    def _migrate_path(self, path: Path) -> str:
        previous_bytes = self.raw_bytes_by_path[path]
        previous_sha256 = hashlib.sha256(previous_bytes).hexdigest()
        if previous_sha256 in self.current_sha256_by_previous:
            return self.current_sha256_by_previous[previous_sha256]
        raw = json.loads(previous_bytes)
        assert isinstance(raw, dict)
        model = _proposal_model(raw)
        if isinstance(model, VDOTProposal):
            evidence = model.evidence
            if not isinstance(evidence, OwnedBaselineAssessmentVDOTEvidence):
                raise PlanningProposalMigrationError(
                    "VDOT proposal does not contain owned assessment evidence"
                )
            reference = EvidenceArtifactReference(
                artifact_type="assessment_review",
                artifact_sha256=evidence.assessment_review_sha256,
            )
            self.graph.validate_owned_assessment_evidence(
                reference,
                evidence.result,
                require_closed_archive=False,
            )
        else:
            reference = EvidenceArtifactReference.model_validate(raw["planning_context_reference"])
        migrated_reference = self.graph.migrate(reference)
        if migrated_reference == reference:
            self.current_sha256_by_previous[previous_sha256] = previous_sha256
            return previous_sha256
        if isinstance(model, VDOTProposal):
            raw["evidence"]["assessment_review_sha256"] = migrated_reference.artifact_sha256
        else:
            raw["planning_context_reference"] = migrated_reference.model_dump(mode="json")
        model = _proposal_model(raw)
        current_bytes = canonical_json_bytes(model)
        current_sha256 = hashlib.sha256(current_bytes).hexdigest()
        matching_paths = [
            candidate
            for candidate, candidate_bytes in self.raw_bytes_by_path.items()
            if hashlib.sha256(candidate_bytes).hexdigest() == previous_sha256
        ]
        for matching_path in matching_paths:
            relative_path = str(matching_path.relative_to(self.repo.repo_root))
            if current_bytes != previous_bytes:
                self.rewritten_bytes_by_relative_path[relative_path] = current_bytes
                self._record_file_migration(
                    relative_path,
                    relative_path,
                    previous_sha256,
                    current_sha256,
                )
        self.current_sha256_by_previous[previous_sha256] = current_sha256
        return current_sha256

    def _record_file_migration(
        self,
        previous_file: str,
        current_relative_path: str,
        previous_sha256: str,
        current_sha256: str,
    ) -> None:
        migration = (
            previous_file,
            current_relative_path,
            previous_sha256,
            current_sha256,
        )
        if migration not in self.file_migrations:
            self.file_migrations.append(migration)

    def migrate_vdot_approval(self, approval: VDOTApproval) -> VDOTApproval:
        """Rebind exact assessment proposal bytes through an audited managed copy."""
        evidence = approval.proposal_snapshot.evidence
        if not isinstance(evidence, OwnedBaselineAssessmentVDOTEvidence):
            return approval
        source_path = Path(approval.proposal_file).expanduser().resolve()
        if not source_path.is_file() or source_path.is_symlink():
            raise PlanningProposalMigrationError(
                "Approved VDOT proposal source file is unavailable"
            )
        source_bytes = source_path.read_bytes()
        previous_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if previous_sha256 != approval.proposal_file_sha256:
            raise PlanningProposalMigrationError(
                "Approved VDOT proposal source bytes changed before migration"
            )
        source_proposal = VDOTProposal.model_validate_json(source_bytes)
        if source_proposal != approval.proposal_snapshot:
            raise PlanningProposalMigrationError(
                "Approved VDOT proposal snapshot differs from its exact source file"
            )
        reference = EvidenceArtifactReference(
            artifact_type="assessment_review",
            artifact_sha256=evidence.assessment_review_sha256,
        )
        self.graph.validate_owned_assessment_evidence(
            reference,
            evidence.result,
            require_closed_archive=True,
        )
        migrated_reference = self.graph.migrate(reference)
        if migrated_reference == reference:
            return approval
        migrated_evidence = evidence.model_copy(
            update={"assessment_review_sha256": migrated_reference.artifact_sha256}
        )
        migrated_proposal = source_proposal.model_copy(update={"evidence": migrated_evidence})
        current_bytes = canonical_json_bytes(migrated_proposal)
        current_sha256 = hashlib.sha256(current_bytes).hexdigest()
        if source_path in self.raw_bytes_by_path:
            relative_path = str(source_path.relative_to(self.repo.repo_root))
        else:
            relative_path = f"{PROPOSALS_DIRECTORY}/{approval.approval_id}-migrated-v1.json"
            target_path = self.repo.resolve_path(relative_path)
            if target_path.is_symlink() or (
                target_path.exists()
                and (not target_path.is_file() or target_path.read_bytes() != current_bytes)
            ):
                raise PlanningProposalMigrationError(
                    "Managed migrated VDOT proposal path already contains different bytes"
                )
        if not self.repo.resolve_path(relative_path).exists():
            self.rewritten_bytes_by_relative_path[relative_path] = current_bytes
        self.current_sha256_by_previous[previous_sha256] = current_sha256
        self._record_file_migration(
            str(source_path),
            relative_path,
            previous_sha256,
            current_sha256,
        )
        return approval.model_copy(
            update={
                "proposal_file": str(self.repo.resolve_path(relative_path)),
                "proposal_file_sha256": current_sha256,
                "proposal_snapshot": migrated_proposal,
            }
        )

    def pending_file_requires_reapproval(
        self,
        approved_file: str,
        approved_file_sha256: str,
    ) -> bool:
        path = Path(approved_file).expanduser().resolve()
        if not path.is_file() or path.is_symlink():
            raise PlanningProposalMigrationError(
                "Pending weekly approval source file is unavailable"
            )
        raw_bytes = path.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != approved_file_sha256:
            raise PlanningProposalMigrationError(
                "Pending weekly approval source bytes changed before migration"
            )
        try:
            application = WeekApplication.model_validate_json(raw_bytes)
        except ValueError as exc:
            raise PlanningProposalMigrationError(
                "Pending weekly approval source is invalid"
            ) from exc
        return (
            self.graph.migrate(application.planning_context_reference)
            != application.planning_context_reference
        )

    def migrate_all(self) -> None:
        for path in self.raw_bytes_by_path:
            self._migrate_path(path)
