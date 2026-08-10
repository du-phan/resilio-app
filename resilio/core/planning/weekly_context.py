"""Immutable evidence creation for one exact future run-plan week."""

from datetime import date, datetime

from resilio.core.coaching_context.service import build_week_planning_context
from resilio.core.planning.artifacts import import_evidence_artifact
from resilio.core.repository import RepositoryIO
from resilio.schemas.plan_history import EvidenceArtifactReference


def create_week_planning_context(
    repo: RepositoryIO,
    *,
    week_number: int,
    evidence_as_of_date: date,
    history_week_count: int,
    generated_at_utc: datetime | None = None,
    current_local_date: date | None = None,
) -> EvidenceArtifactReference:
    """Persist the exact evidence snapshot used to author one weekly proposal."""
    context = build_week_planning_context(
        repo,
        week_number=week_number,
        evidence_as_of_date=evidence_as_of_date,
        history_week_count=history_week_count,
        generated_at_utc=generated_at_utc,
        current_local_date=current_local_date,
    )
    return import_evidence_artifact(
        repo,
        context,
        artifact_type="week_planning_context",
    )
