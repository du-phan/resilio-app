"""Immutable run artifacts, verified backup, approvals, and ownership ledger."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ValidationError

from resilio.core.activity_transaction import write_json
from resilio.core.historical_activity_backfill.rendering import sha256_json
from resilio.core.repository import RepositoryIO
from resilio.schemas.historical_backfill import (
    ApprovalStage,
    BackfillApproval,
    BackfillPlan,
    BackfillRunEnvelope,
    CanaryProof,
    HistoricalActivityPublicationLedger,
)
from resilio.schemas.repository import RepoError

RUNS_ROOT = Path("data/migrations/historical-activity-backfill")
BACKUPS_ROOT = Path("data/backups/historical-activity-backfill")
LEDGER_PATH = "data/state/historical_activity_publications.json"


class HistoricalBackfillRepositoryError(RuntimeError):
    pass


def _model_payload(model: BaseModel, *, exclude: set[str]) -> dict:
    return model.model_dump(mode="json", exclude=exclude)


def plan_digest(plan: BackfillPlan) -> str:
    return sha256_json(_model_payload(plan, exclude={"plan_digest_sha256"}))


def approval_digest(approval: BackfillApproval) -> str:
    return sha256_json(
        _model_payload(approval, exclude={"approval_digest_sha256"})
    )


def canary_digest(proof: CanaryProof) -> str:
    return sha256_json(
        _model_payload(proof, exclude={"canary_digest_sha256"})
    )


def run_root(repo_root: Path, run_id: str) -> Path:
    return repo_root / RUNS_ROOT / run_id


def backup_root(repo_root: Path, run_id: str) -> Path:
    return repo_root / BACKUPS_ROOT / run_id


def _write_immutable_json(path: Path, model: BaseModel | dict) -> None:
    payload = (
        model.model_dump(mode="json")
        if isinstance(model, BaseModel)
        else model
    )
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text() != content:
            raise HistoricalBackfillRepositoryError(
                f"Immutable backfill artifact differs: {path.name}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content)
    os.replace(temporary, path)


def save_plan(repo_root: Path, plan: BackfillPlan, report_payload: dict) -> None:
    if plan_digest(plan) != plan.plan_digest_sha256:
        raise HistoricalBackfillRepositoryError("Backfill plan digest is invalid")
    if sha256_json(report_payload) != plan.report_digest_sha256:
        raise HistoricalBackfillRepositoryError("Backfill report digest is invalid")
    root = run_root(repo_root, plan.run_id)
    _write_immutable_json(root / "plan.json", plan)
    _write_immutable_json(root / "report.json", report_payload)
    markdown = _report_markdown(plan, report_payload)
    path = root / "report.md"
    if path.exists() and path.read_text() != markdown:
        raise HistoricalBackfillRepositoryError(
            "Immutable Markdown report differs"
        )
    if not path.exists():
        path.write_text(markdown)


def _report_markdown(plan: BackfillPlan, report_payload: dict) -> str:
    coverage = plan.coverage
    lines = [
        "# Historical activity backfill dry run",
        "",
        f"- Plan digest: `{plan.plan_digest_sha256}`",
        f"- Canonical archive activities: {coverage.archive_activity_count}",
        f"- Initial external links: {coverage.initial_external_links}",
        f"- Selected: {coverage.selected}",
        f"- Hidden exclusions: {coverage.hidden_excluded}",
        f"- Publishable: {coverage.publishable}",
        f"- Exact historical wall times: {coverage.exact_time}",
        f"- Local-noon adjustments: {coverage.noon_adjusted}",
        f"- Unresolved conflicts: {coverage.conflicts}",
        f"- Canary local activity: `{plan.canary_local_activity_id}`",
        "",
        "No raw external payloads, credentials, private notes, or plaintext hidden",
        "activity identifiers are retained in this report.",
        "",
        "## Decisions",
        "",
        "| Local activity | Action | Time policy | Source fingerprint | Payload fingerprint |",
        "|---|---|---|---|---|",
    ]
    for decision in sorted(
        plan.decisions,
        key=lambda item: item.local_activity_id,
    ):
        lines.append(
            f"| `{decision.local_activity_id}` | {decision.action} | "
            f"{decision.time_mode} | `{decision.source_fingerprint_sha256}` | "
            f"`{decision.payload_fingerprint_sha256}` |"
        )
    lines.extend(
        [
            "",
            f"Report fingerprint: `{sha256_json(report_payload)}`",
            "",
        ]
    )
    return "\n".join(lines)


def load_plan(repo_root: Path, digest: str) -> BackfillPlan:
    matches: list[BackfillPlan] = []
    roots = repo_root / RUNS_ROOT
    if roots.is_dir():
        for path in sorted(roots.glob("*/plan.json")):
            try:
                plan = BackfillPlan.model_validate_json(path.read_text())
            except ValidationError as exc:
                raise HistoricalBackfillRepositoryError(
                    f"Invalid backfill plan artifact: {path.parent.name}"
                ) from exc
            if plan.plan_digest_sha256 == digest:
                matches.append(plan)
    if len(matches) != 1:
        raise HistoricalBackfillRepositoryError(
            f"Expected one immutable backfill plan for digest, found {len(matches)}"
        )
    plan = matches[0]
    if plan_digest(plan) != digest:
        raise HistoricalBackfillRepositoryError("Backfill plan digest verification failed")
    return plan


def save_run_envelope(repo_root: Path, envelope: BackfillRunEnvelope) -> None:
    write_json(
        run_root(repo_root, envelope.run_id) / "run.json",
        envelope.model_dump(mode="json"),
    )


def save_approval(repo_root: Path, plan: BackfillPlan, approval: BackfillApproval) -> None:
    if approval.plan_digest_sha256 != plan.plan_digest_sha256:
        raise HistoricalBackfillRepositoryError("Approval is bound to another plan")
    if approval_digest(approval) != approval.approval_digest_sha256:
        raise HistoricalBackfillRepositoryError("Approval digest is invalid")
    _write_immutable_json(
        run_root(repo_root, plan.run_id) / f"approval-{approval.stage}.json",
        approval,
    )


def load_approval(
    repo_root: Path,
    plan: BackfillPlan,
    stage: ApprovalStage,
) -> BackfillApproval:
    path = run_root(repo_root, plan.run_id) / f"approval-{stage.value}.json"
    if not path.exists():
        raise HistoricalBackfillRepositoryError(
            f"Separate athlete approval for {stage.value} has not been recorded"
        )
    approval = BackfillApproval.model_validate_json(path.read_text())
    if (
        approval.stage != stage
        or approval.plan_digest_sha256 != plan.plan_digest_sha256
        or approval_digest(approval) != approval.approval_digest_sha256
    ):
        raise HistoricalBackfillRepositoryError(
            f"Recorded {stage.value} approval does not match the immutable plan"
        )
    return approval


def save_canary_proof(repo_root: Path, plan: BackfillPlan, proof: CanaryProof) -> None:
    if (
        proof.plan_digest_sha256 != plan.plan_digest_sha256
        or canary_digest(proof) != proof.canary_digest_sha256
    ):
        raise HistoricalBackfillRepositoryError("Canary proof digest is invalid")
    _write_immutable_json(
        run_root(repo_root, plan.run_id) / "canary-proof.json",
        proof,
    )


def load_canary_proof(repo_root: Path, plan: BackfillPlan) -> CanaryProof:
    path = run_root(repo_root, plan.run_id) / "canary-proof.json"
    if not path.exists():
        raise HistoricalBackfillRepositoryError("Verified canary proof is missing")
    proof = CanaryProof.model_validate_json(path.read_text())
    if (
        proof.plan_digest_sha256 != plan.plan_digest_sha256
        or canary_digest(proof) != proof.canary_digest_sha256
    ):
        raise HistoricalBackfillRepositoryError("Canary proof verification failed")
    return proof


def load_ledger(repo: RepositoryIO) -> HistoricalActivityPublicationLedger:
    result = repo.read_json(LEDGER_PATH, HistoricalActivityPublicationLedger)
    if result is None:
        return HistoricalActivityPublicationLedger()
    if isinstance(result, RepoError):
        raise HistoricalBackfillRepositoryError(
            f"Invalid historical publication ledger: {result}"
        )
    return result


def save_ledger(
    repo: RepositoryIO,
    ledger: HistoricalActivityPublicationLedger,
) -> None:
    validated = HistoricalActivityPublicationLedger.model_validate(
        ledger.model_dump(mode="python")
    )
    error = repo.write_json(LEDGER_PATH, validated)
    if error is not None:
        raise HistoricalBackfillRepositoryError(
            f"Failed to save historical publication ledger: {error}"
        )


def _backup_sources(repo_root: Path) -> Iterable[Path]:
    directories = [
        repo_root / "data/activities",
        repo_root / "data/metrics",
        repo_root / "data/athlete",
        repo_root / "data/plans",
    ]
    files = [
        repo_root / "data/state/activity_sync.json",
        repo_root / "data/state/workout_completions.json",
        repo_root / "data/state/workout_publications.json",
    ]
    for root in directories:
        if root.is_dir():
            yield from sorted(item for item in root.rglob("*") if item.is_file())
    yield from (path for path in files if path.is_file())


def create_verified_backup(repo_root: Path, plan: BackfillPlan) -> Path:
    root = backup_root(repo_root, plan.run_id)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        verify_backup(repo_root, plan)
        return root
    if root.exists():
        raise HistoricalBackfillRepositoryError(
            "Incomplete historical backfill backup already exists"
        )
    snapshot = root / "snapshot"
    snapshot.mkdir(parents=True, mode=0o700)
    entries: list[dict] = []
    for source in _backup_sources(repo_root):
        relative = source.relative_to(repo_root)
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        target.chmod(0o600)
        entries.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "size": target.stat().st_size,
            }
        )
    manifest = {
        "schema_version": 1,
        "run_id": plan.run_id,
        "plan_digest_sha256": plan.plan_digest_sha256,
        "files": entries,
        "files_digest_sha256": sha256_json(entries),
    }
    _write_immutable_json(manifest_path, manifest)
    for directory in sorted(
        (item for item in root.rglob("*") if item.is_dir()),
        reverse=True,
    ):
        directory.chmod(0o700)
    manifest_path.chmod(0o600)
    root.chmod(0o700)
    verify_backup(repo_root, plan)
    return root


def verify_backup(repo_root: Path, plan: BackfillPlan) -> dict:
    root = backup_root(repo_root, plan.run_id)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise HistoricalBackfillRepositoryError("Verified backfill backup is missing")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("plan_digest_sha256") != plan.plan_digest_sha256
        or sha256_json(manifest.get("files")) != manifest.get("files_digest_sha256")
    ):
        raise HistoricalBackfillRepositoryError("Backfill backup manifest is invalid")
    for entry in manifest["files"]:
        path = root / "snapshot" / entry["path"]
        if (
            not path.is_file()
            or path.stat().st_size != entry["size"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise HistoricalBackfillRepositoryError(
                f"Backfill backup verification failed: {entry['path']}"
            )
    if root.stat().st_mode & 0o077:
        raise HistoricalBackfillRepositoryError(
            "Backfill backup root must be mode-restricted to 0700"
        )
    return manifest


def original_activity_path(
    repo_root: Path,
    plan: BackfillPlan,
    local_activity_id: str,
    local_date,
) -> Path:
    return (
        backup_root(repo_root, plan.run_id)
        / "snapshot"
        / "data"
        / "activities"
        / local_date.strftime("%Y-%m")
        / f"{local_activity_id}.yaml"
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
