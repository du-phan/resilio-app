"""Immutable plan archive and evidence-artifact persistence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from resilio.core.repository import RepositoryIO
from resilio.schemas.approvals import ClosedPlanCycle
from resilio.schemas.plan_history import (
    ClosedPlanCycleReference,
    EvidenceArtifactReference,
)
from resilio.schemas.repository import RepoError

ARCHIVE_DIRECTORY = "data/plans/archive"
EVIDENCE_DIRECTORY = "data/plans/evidence"

T = TypeVar("T", bound=BaseModel)


class PlanningArtifactError(OSError):
    """An immutable planning artifact could not be proven valid."""


def canonical_json_bytes(model: BaseModel) -> bytes:
    """Serialize model bytes deterministically for durable SHA-256 identities."""
    payload = model.model_dump(mode="json", by_alias=True)
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode()


def model_sha256(model: BaseModel) -> str:
    return hashlib.sha256(canonical_json_bytes(model)).hexdigest()


def canonical_data_sha256(value: BaseModel | dict[str, Any] | list[Any]) -> str:
    """Hash typed evidence inputs with the same canonical JSON rules."""
    payload = (
        value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else value
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_immutable_bytes(repo: RepositoryIO, path: str, payload: bytes) -> None:
    resolved = repo.resolve_path(path)
    if resolved.exists():
        if resolved.is_symlink():
            raise PlanningArtifactError(f"Planning artifact cannot be a symlink: {path}")
        if resolved.read_bytes() != payload:
            raise PlanningArtifactError(
                f"Immutable planning artifact already exists with other bytes: {path}"
            )
        return
    error = repo.write_text(path, payload.decode())
    if isinstance(error, RepoError):
        raise PlanningArtifactError(f"Planning artifact could not be written: {error}")
    if resolved.read_bytes() != payload:
        raise PlanningArtifactError("Persisted planning artifact bytes changed during write")


def archive_path(plan_id: str) -> str:
    return f"{ARCHIVE_DIRECTORY}/{plan_id}.json"


def save_closed_plan_cycle(
    repo: RepositoryIO,
    cycle: ClosedPlanCycle,
) -> ClosedPlanCycleReference:
    validated = ClosedPlanCycle.model_validate(cycle.model_dump(mode="python"))
    digest = model_sha256(validated)
    _write_immutable_bytes(
        repo,
        archive_path(validated.active_plan_snapshot.plan.id),
        canonical_json_bytes(validated),
    )
    return ClosedPlanCycleReference(
        plan_id=validated.active_plan_snapshot.plan.id,
        macro_revision_id=validated.active_plan_snapshot.plan.macro_revision_id,
        archive_sha256=digest,
        closed_at_utc=validated.closure.closed_at_utc,
    )


def load_closed_plan_cycle(
    repo: RepositoryIO,
    reference: ClosedPlanCycleReference,
) -> ClosedPlanCycle:
    result = repo.read_json(
        archive_path(reference.plan_id),
        ClosedPlanCycle,
    )
    if result is None:
        raise PlanningArtifactError(f"Closed plan archive is missing: {reference.plan_id}")
    if isinstance(result, RepoError):
        raise PlanningArtifactError(f"Closed plan archive is invalid: {result}")
    if result.active_plan_snapshot.plan.id != reference.plan_id:
        raise PlanningArtifactError("Closed plan archive ID does not match its reference")
    if result.active_plan_snapshot.plan.macro_revision_id != reference.macro_revision_id:
        raise PlanningArtifactError(
            "Closed plan archive macro revision does not match its reference"
        )
    if model_sha256(result) != reference.archive_sha256:
        raise PlanningArtifactError("Closed plan archive bytes changed after closure")
    return result


def load_all_closed_plan_cycles(
    repo: RepositoryIO,
    references: list[ClosedPlanCycleReference],
) -> list[ClosedPlanCycle]:
    return [load_closed_plan_cycle(repo, reference) for reference in references]


def evidence_path(reference: EvidenceArtifactReference) -> str:
    return f"{EVIDENCE_DIRECTORY}/{reference.artifact_type}/" f"{reference.artifact_sha256}.json"


def import_evidence_artifact(
    repo: RepositoryIO,
    model: BaseModel,
    *,
    artifact_type: Literal["cycle_review", "macro_planning_context"],
) -> EvidenceArtifactReference:
    if artifact_type not in {"cycle_review", "macro_planning_context"}:
        raise ValueError(f"Unsupported evidence artifact type: {artifact_type}")
    digest = model_sha256(model)
    reference = EvidenceArtifactReference(
        artifact_type=artifact_type,
        artifact_sha256=digest,
    )
    _write_immutable_bytes(
        repo,
        evidence_path(reference),
        canonical_json_bytes(model),
    )
    return reference


def load_evidence_artifact(
    repo: RepositoryIO,
    reference: EvidenceArtifactReference,
    schema: type[T],
) -> T:
    result = repo.read_json(evidence_path(reference), schema)
    if result is None:
        raise PlanningArtifactError(
            f"Planning evidence artifact is missing: {reference.artifact_sha256}"
        )
    if isinstance(result, RepoError):
        raise PlanningArtifactError(f"Planning evidence artifact is invalid: {result}")
    if model_sha256(result) != reference.artifact_sha256:
        raise PlanningArtifactError("Planning evidence artifact changed after import")
    return result
