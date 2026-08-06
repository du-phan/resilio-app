"""Verification of exact-file planning approvals at every read boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from resilio.core.activity_sync.archive import (
    ActivityArchive,
    ActivityArchiveError,
)
from resilio.core.activity_transaction import ACTIVITY_MUTATION_LOCK_PATH
from resilio.core.locking import OperationLock, OperationLockError
from resilio.core.paths import get_activities_dir
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.profile.repository import ProfileRepository
from resilio.core.repository import RepositoryIO
from resilio.core.vdot import VDOTCalculationRangeError, calculate_vdot
from resilio.schemas.activity import ActivityStatus, is_running_sport
from resilio.schemas.approvals import (
    ManualVDOTEvidence,
    OwnedBaselineAssessmentVDOTEvidence,
    PersonalBestVDOTEvidence,
    RacePerformanceVDOTEvidence,
    VDOTApproval,
    VDOTProposal,
)
from resilio.schemas.vdot import RaceDistance


class ApprovalEvidenceError(RuntimeError):
    """Persisted approval metadata no longer proves its source evidence."""


@dataclass(frozen=True)
class VerifiedVDOTProposalFile:
    """Validated proposal and the digest of the exact bytes that were parsed."""

    proposal: VDOTProposal
    file_sha256: str


def _read_vdot_proposal(
    path: Path,
    *,
    expected_sha256: str | None = None,
) -> VerifiedVDOTProposalFile:
    try:
        exact_bytes = path.read_bytes()
    except OSError as exc:
        raise ApprovalEvidenceError(f"VDOT proposal file could not be read: {exc}") from exc
    file_sha256 = hashlib.sha256(exact_bytes).hexdigest()
    if expected_sha256 is not None and file_sha256 != expected_sha256:
        raise ApprovalEvidenceError("Approved VDOT proposal changed after approval")
    try:
        proposal = VDOTProposal.model_validate_json(exact_bytes)
    except ValueError as exc:
        raise ApprovalEvidenceError(f"VDOT proposal file is invalid: {exc}") from exc
    _verify_proposal_calculation(proposal)
    return VerifiedVDOTProposalFile(
        proposal=proposal,
        file_sha256=file_sha256,
    )


def _verify_proposal_calculation(proposal: VDOTProposal) -> None:
    evidence = proposal.evidence
    if isinstance(evidence, ManualVDOTEvidence):
        if evidence.athlete_confirmed_vdot != proposal.proposed_vdot:
            raise ApprovalEvidenceError(
                "Manual VDOT evidence does not match the proposed value"
            )
        return
    assert isinstance(
        evidence,
        RacePerformanceVDOTEvidence
        | PersonalBestVDOTEvidence
        | OwnedBaselineAssessmentVDOTEvidence,
    )
    try:
        calculated = calculate_vdot(
            RaceDistance(evidence.race_distance),
            evidence.elapsed_time_seconds,
        )
    except (VDOTCalculationRangeError, ValueError) as exc:
        raise ApprovalEvidenceError(
            f"Race evidence cannot produce an approved VDOT: {exc}"
        ) from exc
    if calculated.vdot != proposal.proposed_vdot:
        raise ApprovalEvidenceError(
            "Proposed VDOT does not match the structured performance evidence"
        )


def _verify_personal_best_source(
    repo: RepositoryIO,
    evidence: PersonalBestVDOTEvidence,
) -> None:
    try:
        profile = ProfileRepository(repo)._load_unlocked()
    except (OSError, ValueError) as exc:
        raise ApprovalEvidenceError(
            f"Athlete profile could not verify personal-best evidence: {exc}"
        ) from exc
    if profile is None:
        raise ApprovalEvidenceError(
            "Athlete profile is missing for personal-best evidence"
        )
    distance_name = (
        evidence.race_distance.value
        if isinstance(evidence.race_distance, RaceDistance)
        else evidence.race_distance
    )
    personal_best = profile.personal_bests_by_distance.get(distance_name)
    if personal_best is None:
        raise ApprovalEvidenceError(
            "The source personal best is absent from the athlete profile"
        )
    if (
        personal_best.elapsed_time_seconds != evidence.elapsed_time_seconds
        or personal_best.performance_date != evidence.performance_date
    ):
        raise ApprovalEvidenceError(
            "The source personal best no longer matches the proposal"
        )
    if profile.training_timezone != evidence.performance_timezone:
        raise ApprovalEvidenceError(
            "Personal-best evidence timezone must match the athlete profile"
        )


def _verify_race_activity_source(
    repo: RepositoryIO,
    evidence: RacePerformanceVDOTEvidence,
) -> None:
    archive_root = repo.resolve_path(get_activities_dir())
    lock_path = repo.resolve_path(ACTIVITY_MUTATION_LOCK_PATH)
    try:
        with OperationLock(lock_path, "verify_vdot_race_evidence"):
            activity = ActivityArchive(archive_root).load(
                evidence.source_local_activity_id
            )
    except OperationLockError as exc:
        raise ApprovalEvidenceError(
            "Activity evidence is temporarily unavailable during synchronization"
        ) from exc
    except ActivityArchiveError as exc:
        raise ApprovalEvidenceError(
            f"Race activity evidence is invalid: {exc}"
        ) from exc
    if activity is None:
        raise ApprovalEvidenceError(
            "The source race activity is absent from the canonical archive"
        )
    if activity.status != ActivityStatus.ACTIVE:
        raise ApprovalEvidenceError("The source race activity is not active")
    if not is_running_sport(activity.sport):
        raise ApprovalEvidenceError(
            "The source race evidence must reference a running activity"
        )
    if activity.occurrence.local_date != evidence.performance_date:
        raise ApprovalEvidenceError(
            "The source race activity does not match the performance date"
        )
    if activity.duration.elapsed_seconds != evidence.elapsed_time_seconds:
        raise ApprovalEvidenceError(
            "The source race activity does not match the elapsed time"
        )
    if (
        activity.distance_meters is None
        or abs(activity.distance_meters - evidence.measured_distance_meters) > 0.01
    ):
        raise ApprovalEvidenceError(
            "The source race activity does not match the measured distance"
        )
    if activity.occurrence.timezone != evidence.performance_timezone:
        raise ApprovalEvidenceError(
            "The source race activity does not match the performance timezone"
        )
    if (
        activity.audit.performance_evidence_sha256
        != evidence.source_performance_evidence_sha256
    ):
        raise ApprovalEvidenceError(
            "The source race activity fingerprint no longer matches the proposal"
        )


def _verify_proposal_source(
    repo: RepositoryIO,
    proposal: VDOTProposal,
) -> None:
    evidence = proposal.evidence
    if isinstance(evidence, PersonalBestVDOTEvidence):
        _verify_personal_best_source(repo, evidence)
    elif isinstance(evidence, RacePerformanceVDOTEvidence):
        _verify_race_activity_source(repo, evidence)
    elif isinstance(evidence, OwnedBaselineAssessmentVDOTEvidence):
        from resilio.core.planning.assessment_evidence import (
            verify_owned_assessment_vdot_evidence,
        )
        from resilio.core.planning.errors import PlanOperationError

        try:
            verify_owned_assessment_vdot_evidence(repo, evidence)
        except PlanOperationError as exc:
            raise ApprovalEvidenceError(str(exc)) from exc


def load_vdot_proposal_unlocked(
    repo: RepositoryIO,
    path: Path,
    *,
    expected_sha256: str | None = None,
) -> VerifiedVDOTProposalFile:
    """Validate exact proposal bytes while the caller holds the plan lock."""
    result = _read_vdot_proposal(path, expected_sha256=expected_sha256)
    _verify_proposal_source(repo, result.proposal)
    return result


def load_vdot_proposal(
    repo: RepositoryIO,
    path: Path,
) -> VDOTProposal:
    """Load fully verified proposal evidence under coordinated state locks."""
    try:
        with coordinated_plan_lock(repo, "read_vdot_proposal"):
            return load_vdot_proposal_unlocked(repo, path).proposal
    except OperationLockError as exc:
        raise ApprovalEvidenceError(
            "VDOT evidence is temporarily unavailable during a state transition"
        ) from exc


def load_vdot_approval_evidence_unlocked(
    repo: RepositoryIO,
    approval: VDOTApproval | None,
) -> tuple[VDOTApproval, VDOTProposal]:
    """Load one approval and its proposal while the caller holds the plan lock."""
    if approval is None:
        raise ApprovalEvidenceError("An approved VDOT proposal is required")
    proposal_path = Path(approval.proposal_file)
    proposal_file = load_vdot_proposal_unlocked(
        repo,
        proposal_path,
        expected_sha256=approval.proposal_file_sha256,
    )
    proposal = proposal_file.proposal
    if (
        proposal.proposed_vdot != approval.approved_vdot
        or proposal.evidence_type != approval.evidence_type
    ):
        raise ApprovalEvidenceError("Approved VDOT proposal no longer matches its approval")
    if approval.approved_at_utc < proposal.generated_at_utc:
        raise ApprovalEvidenceError(
            "VDOT approval predates its proposal generation"
        )
    return approval, proposal


def verify_vdot_approval_unlocked(
    repo: RepositoryIO,
    approval: VDOTApproval | None,
) -> VDOTApproval:
    """Re-prove approval evidence while the caller holds the plan lock."""
    approval, _proposal = load_vdot_approval_evidence_unlocked(
        repo,
        approval,
    )
    return approval


def verify_vdot_approval(
    repo: RepositoryIO,
    approval: VDOTApproval | None,
) -> VDOTApproval:
    """Re-prove an approval under coordinated profile, plan, and source locks."""
    try:
        with coordinated_plan_lock(repo, "verify_vdot_approval"):
            return verify_vdot_approval_unlocked(repo, approval)
    except OperationLockError as exc:
        raise ApprovalEvidenceError(
            "VDOT approval is temporarily unavailable during a state transition"
        ) from exc
