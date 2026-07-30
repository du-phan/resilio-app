"""Conditional original-file hashing for unresolved activity identity."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from resilio.core.activity_sync.reconciliation import reconcile_activity
from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.errors import IntervalsIcuError
from resilio.schemas.activity import CanonicalActivity
from resilio.schemas.reconciliation import ReconciliationDecision


@dataclass(frozen=True)
class OriginalFileProbe:
    activity: CanonicalActivity
    decision: ReconciliationDecision


def _with_probe_evidence(
    decision: ReconciliationDecision,
    outcome: str,
) -> ReconciliationDecision:
    return decision.model_copy(
        update={
            "evidence": {
                **decision.evidence,
                "original_file_probe": outcome,
            }
        }
    )


def probe_original_file_for_ambiguity(
    *,
    client: IntervalsIcuClient,
    activity: CanonicalActivity,
    existing_records: Iterable[CanonicalActivity],
    decision: ReconciliationDecision,
) -> OriginalFileProbe:
    """Hash one temporary download and retry an ambiguous reconciliation."""
    external_id = activity.origin.intervals_icu_activity_id
    if not external_id:
        raise ValueError("external activity is missing its identity")
    try:
        content = client.get_original_file(external_id)
    except IntervalsIcuError as exc:
        return OriginalFileProbe(
            activity=activity,
            decision=_with_probe_evidence(
                decision,
                f"unavailable_{exc.error_type}",
            ),
        )
    if not content:
        return OriginalFileProbe(
            activity=activity,
            decision=_with_probe_evidence(decision, "unavailable_empty"),
        )

    digest = hashlib.sha256(content).hexdigest()
    enriched = activity.model_copy(
        update={"origin": activity.origin.model_copy(update={"original_file_sha256": digest})}
    )
    retried = reconcile_activity(enriched, existing_records)
    outcome = "unique_match" if retried.rule == "unique_original_file_sha256" else "no_unique_match"
    return OriginalFileProbe(
        activity=enriched,
        decision=_with_probe_evidence(retried, outcome),
    )
