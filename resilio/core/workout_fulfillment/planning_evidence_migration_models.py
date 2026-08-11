"""Contracts and prepared writes for strict planning-evidence migration."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from resilio.core.activity_transaction import remove_path
from resilio.core.planning.artifacts import canonical_json_bytes
from resilio.core.repository import RepositoryIO
from resilio.core.state import PLANNING_STATE_PATH, save_planning_state
from resilio.schemas.approvals import ClosedPlanArchive, PlanningState
from resilio.schemas.repository import RepoError

PLANNING_EVIDENCE_MIGRATION_AUDIT_PATH = (
    "data/state/workout-fulfillment-planning-evidence-migration.json"
)


class PlanningEvidenceHashMigration(BaseModel):
    artifact_type: str
    previous_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class PlanSkeletonHashMigration(BaseModel):
    plan_id: str
    plan_revision_id: str
    previous_plan_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_plan_skeleton_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class ProposalFileHashMigration(BaseModel):
    previous_file: str
    current_relative_path: str
    previous_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class PlanningEvidenceMigrationAudit(BaseModel):
    schema_version: int = 1
    artifact_migrations: list[PlanningEvidenceHashMigration]
    plan_skeleton_migrations: list[PlanSkeletonHashMigration]
    proposal_file_migrations: list[ProposalFileHashMigration]

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class PlanningEvidenceMigrationResult:
    planning_state: PlanningState | None
    closed_archives_by_relative_path: dict[str, ClosedPlanArchive]
    new_artifacts_by_relative_path: dict[str, BaseModel]
    rewritten_proposals_by_relative_path: dict[str, bytes]
    obsolete_artifact_relative_paths: tuple[str, ...]
    audit: PlanningEvidenceMigrationAudit | None

    @property
    def changes_required(self) -> bool:
        return self.audit is not None

    @property
    def migrated_artifact_count(self) -> int:
        return 0 if self.audit is None else len(self.audit.artifact_migrations)

    @property
    def migrated_plan_count(self) -> int:
        return 0 if self.audit is None else len(self.audit.plan_skeleton_migrations)

    @property
    def target_relative_paths(self) -> tuple[str, ...]:
        if not self.changes_required:
            return ()
        return tuple(
            sorted(
                {
                    PLANNING_STATE_PATH,
                    PLANNING_EVIDENCE_MIGRATION_AUDIT_PATH,
                    *self.closed_archives_by_relative_path,
                    *self.new_artifacts_by_relative_path,
                    *self.rewritten_proposals_by_relative_path,
                    *self.obsolete_artifact_relative_paths,
                }
            )
        )

    def apply(self, repo: RepositoryIO) -> None:
        if not self.changes_required:
            return
        for relative_path, artifact in self.new_artifacts_by_relative_path.items():
            error = repo.write_text(relative_path, canonical_json_bytes(artifact).decode())
            if isinstance(error, RepoError):
                raise OSError(f"Planning evidence migration write failed: {error}")
        for relative_path, payload in self.rewritten_proposals_by_relative_path.items():
            error = repo.write_text(relative_path, payload.decode())
            if isinstance(error, RepoError):
                raise OSError(f"Planning proposal migration write failed: {error}")
        for relative_path, archive in self.closed_archives_by_relative_path.items():
            error = repo.write_text(relative_path, canonical_json_bytes(archive).decode())
            if isinstance(error, RepoError):
                raise OSError(f"Closed-plan migration write failed: {error}")
        if self.planning_state is not None:
            error = save_planning_state(self.planning_state, repo)
            if isinstance(error, RepoError):
                raise OSError(f"Planning-state migration write failed: {error}")
        assert self.audit is not None
        error = repo.write_json(PLANNING_EVIDENCE_MIGRATION_AUDIT_PATH, self.audit)
        if isinstance(error, RepoError):
            raise OSError(f"Planning migration audit write failed: {error}")
        for relative_path in self.obsolete_artifact_relative_paths:
            remove_path(repo.resolve_path(relative_path))
