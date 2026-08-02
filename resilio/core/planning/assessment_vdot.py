"""Create VDOT proposal evidence from one closed baseline assessment."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from resilio.core.planning.assessment_evidence import (
    load_verified_closed_assessment_review,
)
from resilio.core.planning.errors import PlanOperationError
from resilio.core.planning.profile_plan_transaction import coordinated_plan_lock
from resilio.core.repository import RepositoryIO
from resilio.core.vdot import VDOTCalculationRangeError, calculate_vdot
from resilio.schemas.approvals import (
    OwnedBaselineAssessmentVDOTEvidence,
    VDOTProposal,
)
from resilio.schemas.vdot import RaceDistance


def create_vdot_proposal_from_assessment(
    repo: RepositoryIO,
    *,
    review_sha256: str,
    generated_at_utc: datetime | None = None,
) -> VDOTProposal:
    """Build a reviewable VDOT proposal without mutating approval state."""
    timestamp = generated_at_utc or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PlanOperationError("VDOT proposal timestamp must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    with coordinated_plan_lock(repo, "vdot_proposal_from_assessment"):
        review = load_verified_closed_assessment_review(
            repo,
            review_sha256=review_sha256,
        )
        result = review.result
        generated_local_date = timestamp.astimezone(
            ZoneInfo(result.performance_timezone)
        ).date()
        if result.performance_date > generated_local_date:
            raise PlanOperationError("Assessment result cannot postdate its VDOT proposal")
        try:
            calculation = calculate_vdot(
                RaceDistance(result.race_distance),
                result.elapsed_time_seconds,
            )
        except (VDOTCalculationRangeError, ValueError) as exc:
            raise PlanOperationError(
                f"Assessment result cannot produce a VDOT proposal: {exc}"
            ) from exc
        evidence = OwnedBaselineAssessmentVDOTEvidence(
            evidence_type="owned_baseline_assessment",
            race_distance=result.race_distance,
            elapsed_time_seconds=result.elapsed_time_seconds,
            performance_date=result.performance_date,
            performance_timezone=result.performance_timezone,
            assessment_review_sha256=review_sha256,
            result=result,
        )
        return VDOTProposal(
            proposed_vdot=calculation.vdot,
            evidence=evidence,
            evidence_summary=(
                "Athlete-confirmed owned baseline assessment result from "
                f"{result.performance_date.isoformat()} over "
                f"{result.race_distance}."
            ),
            generated_at_utc=timestamp,
        )
