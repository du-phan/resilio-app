"""Athlete-legible review queue and explicit reconciliation approvals."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from pydantic import ValidationError

from resilio.core.activity_sync.archive import ActivityArchive
from resilio.core.repository import RepositoryIO
from resilio.core.sync_state import read_sync_state
from resilio.schemas.reconciliation import (
    ActivityQuarantineAcknowledgement,
    ActivityQuarantineAcknowledgementLedger,
    ActivityQuarantineAcknowledgementResult,
    ActivityQuarantineReviewItem,
    ExternalDeletionReviewItem,
    ReconciliationExclusion,
    ReconciliationExclusionResult,
    ReconciliationOverride,
    ReconciliationOverrideLedger,
    ReconciliationOverrideResult,
    ReconciliationReviewCandidate,
    ReconciliationReviewItem,
)
from resilio.schemas.repository import RepoError

OVERRIDE_LEDGER_PATH = "data/state/activity_reconciliation_overrides.json"
QUARANTINE_ACKNOWLEDGEMENT_LEDGER_PATH = (
    "data/state/activity_quarantine_acknowledgements.json"
)


class ReconciliationReviewError(RuntimeError):
    pass


def load_override_ledger(repo: RepositoryIO) -> ReconciliationOverrideLedger:
    result = repo.read_json(
        OVERRIDE_LEDGER_PATH,
        ReconciliationOverrideLedger,
    )
    if result is None:
        return ReconciliationOverrideLedger()
    if isinstance(result, RepoError):
        raise ReconciliationReviewError(
            f"Invalid activity reconciliation approval ledger: {result}"
        )
    return result


def save_override_ledger(
    repo: RepositoryIO,
    ledger: ReconciliationOverrideLedger,
) -> None:
    error = repo.write_json(OVERRIDE_LEDGER_PATH, ledger)
    if error is not None:
        raise ReconciliationReviewError(
            f"Unable to save activity reconciliation approval: {error}"
        )


def load_quarantine_acknowledgement_ledger(
    repo: RepositoryIO,
) -> ActivityQuarantineAcknowledgementLedger:
    result = repo.read_json(
        QUARANTINE_ACKNOWLEDGEMENT_LEDGER_PATH,
        ActivityQuarantineAcknowledgementLedger,
    )
    if result is None:
        return ActivityQuarantineAcknowledgementLedger()
    if isinstance(result, RepoError):
        raise ReconciliationReviewError(
            f"Invalid activity quarantine acknowledgement ledger: {result}"
        )
    return result


def save_quarantine_acknowledgement_ledger(
    repo: RepositoryIO,
    ledger: ActivityQuarantineAcknowledgementLedger,
) -> None:
    error = repo.write_json(
        QUARANTINE_ACKNOWLEDGEMENT_LEDGER_PATH,
        ledger,
    )
    if error is not None:
        raise ReconciliationReviewError(
            f"Unable to save activity quarantine acknowledgement: {error}"
        )


def quarantine_failure_fingerprint(payload: dict) -> str:
    material = {
        "rule": payload["rule"],
        "error_type": payload["error_type"],
        "validation_issues": payload.get("validation_issues", []),
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def reconciliation_review_fingerprint(payload: dict) -> str:
    material = {
        "action": payload.get("action"),
        "rule": payload.get("rule"),
        "external_activity_id_sha256": payload.get(
            "external_activity_id_sha256"
        ),
        "candidate_local_ids": sorted(
            str(item) for item in payload.get("candidate_local_ids") or []
        ),
        "evidence": payload.get("evidence") or {},
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_mapping_quarantine_decision(
    *,
    external_activity_id_sha256: str,
    error: Exception,
) -> dict:
    validation_issues = []
    if isinstance(error, ValidationError):
        validation_issues = sorted(
            (
                {
                    "location": ".".join(
                        str(part) for part in issue["loc"]
                    ),
                    "issue_type": str(issue["type"]),
                }
                for issue in error.errors(include_url=False)
            ),
            key=lambda issue: (
                issue["location"],
                issue["issue_type"],
            ),
        )
    payload = {
        "action": "quarantine",
        "rule": "canonical_mapping_failed",
        "external_activity_id_sha256": external_activity_id_sha256,
        "error_type": type(error).__name__,
        "validation_issues": validation_issues,
        "acknowledgeable": bool(validation_issues),
    }
    payload["failure_fingerprint_sha256"] = (
        quarantine_failure_fingerprint(payload)
    )
    return payload


def _current_quarantine(repo: RepositoryIO) -> dict:
    run_id = read_sync_state(repo).checkpoint_run_id
    if not run_id:
        return {"ambiguous_decisions": []}
    path = repo.resolve_path(
        f"data/state/sync-runs/{run_id}/quarantine.json"
    )
    if not path.exists():
        return {"ambiguous_decisions": []}
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ReconciliationReviewError(
            "Current activity review report is invalid"
        ) from exc
    if not isinstance(payload.get("ambiguous_decisions"), list):
        raise ReconciliationReviewError(
            "Current activity review report has an invalid decision list"
        )
    return payload


def list_activity_quarantines(
    repo: RepositoryIO,
) -> list[ActivityQuarantineReviewItem]:
    ledger = load_quarantine_acknowledgement_ledger(repo)
    items = []
    for raw in _current_quarantine(repo)["ambiguous_decisions"]:
        if (
            raw.get("action") != "quarantine"
            or "failure_fingerprint_sha256" not in raw
        ):
            continue
        external_hash = str(raw["external_activity_id_sha256"])
        fingerprint = str(raw["failure_fingerprint_sha256"])
        acknowledgement = ledger.acknowledgements.get(external_hash)
        items.append(
            ActivityQuarantineReviewItem(
                external_activity_id_sha256=external_hash,
                rule=str(raw["rule"]),
                error_type=str(raw["error_type"]),
                validation_issues=raw.get("validation_issues") or [],
                failure_fingerprint_sha256=fingerprint,
                acknowledgeable=bool(raw.get("acknowledgeable", False)),
                acknowledged=bool(
                    acknowledgement is not None
                    and acknowledgement.failure_fingerprint_sha256
                    == fingerprint
                ),
            )
        )
    return sorted(
        items,
        key=lambda item: item.external_activity_id_sha256,
    )


def list_external_deletion_reviews(
    repo: RepositoryIO,
) -> list[ExternalDeletionReviewItem]:
    payload = _current_quarantine(repo)
    local_ids = payload.get("external_deletion_candidates") or []
    if not isinstance(local_ids, list):
        raise ReconciliationReviewError(
            "Current external deletion review queue is invalid"
        )
    records = {
        activity.local_activity_id: activity
        for activity in ActivityArchive(
            repo.resolve_path("data/activities")
        ).load_all()
    }
    items = []
    for local_id in sorted(str(item) for item in local_ids):
        activity = records.get(local_id)
        if activity is None:
            raise ReconciliationReviewError(
                "An external deletion candidate is missing locally"
            )
        items.append(
            ExternalDeletionReviewItem(
                local_activity_id=local_id,
                local_date=activity.date,
                sport=activity.sport_type,
                name=activity.name,
            )
        )
    return items


def acknowledge_activity_quarantine(
    repo: RepositoryIO,
    *,
    external_activity_id_sha256: str,
    failure_fingerprint_sha256: str,
) -> ActivityQuarantineAcknowledgementResult:
    review = next(
        (
            item
            for item in list_activity_quarantines(repo)
            if item.external_activity_id_sha256
            == external_activity_id_sha256
        ),
        None,
    )
    if review is None:
        raise ReconciliationReviewError(
            "The external activity hash is not in the current quarantine queue"
        )
    if not review.acknowledgeable:
        raise ReconciliationReviewError(
            "This quarantine cannot be acknowledged safely"
        )
    if review.failure_fingerprint_sha256 != failure_fingerprint_sha256:
        raise ReconciliationReviewError(
            "The quarantine failure fingerprint is no longer current"
        )

    ledger = load_quarantine_acknowledgement_ledger(repo)
    existing = ledger.acknowledgements.get(external_activity_id_sha256)
    if (
        existing is not None
        and existing.failure_fingerprint_sha256
        == failure_fingerprint_sha256
    ):
        action = "unchanged"
    else:
        ledger.acknowledgements[external_activity_id_sha256] = (
            ActivityQuarantineAcknowledgement(
                external_activity_id_sha256=external_activity_id_sha256,
                failure_fingerprint_sha256=failure_fingerprint_sha256,
                acknowledged_at_utc=datetime.now(timezone.utc),
            )
        )
        save_quarantine_acknowledgement_ledger(repo, ledger)
        action = "acknowledged"
    return ActivityQuarantineAcknowledgementResult(
        external_activity_id_sha256=external_activity_id_sha256,
        failure_fingerprint_sha256=failure_fingerprint_sha256,
        action=action,
    )


def list_reconciliation_reviews(
    repo: RepositoryIO,
) -> list[ReconciliationReviewItem]:
    records = {
        activity.local_activity_id: activity
        for activity in ActivityArchive(
            repo.resolve_path("data/activities")
        ).load_all()
    }
    items: list[ReconciliationReviewItem] = []
    for raw in _current_quarantine(repo)["ambiguous_decisions"]:
        if raw.get("action") != "ambiguous":
            continue
        external_hash = str(raw["external_activity_id_sha256"])
        candidates: list[ReconciliationReviewCandidate] = []
        evidence = raw.get("evidence") or {}
        for local_id in sorted(raw.get("candidate_local_ids") or []):
            activity = records.get(local_id)
            if activity is None:
                continue
            linked_external_id = (
                activity.origin.intervals_icu_activity_id
            )
            candidates.append(
                ReconciliationReviewCandidate(
                    local_activity_id=local_id,
                    local_date=activity.date,
                    sport=activity.sport_type,
                    name=activity.name,
                    duration_seconds=activity.duration_seconds,
                    distance_meters=activity.distance_meters,
                    already_linked_to_different_external_id=bool(
                        linked_external_id
                        and hashlib.sha256(
                            linked_external_id.encode()
                        ).hexdigest()
                        != external_hash
                    ),
                    evidence=evidence.get(local_id, evidence),
                )
            )
        items.append(
            ReconciliationReviewItem(
                external_activity_id_sha256=external_hash,
                review_fingerprint_sha256=(
                    reconciliation_review_fingerprint(raw)
                ),
                rule=str(raw.get("rule", "ambiguous")),
                original_file_probe=evidence.get("original_file_probe"),
                candidates=candidates,
            )
        )
    return sorted(
        items,
        key=lambda item: item.external_activity_id_sha256,
    )


def approve_reconciliation_override(
    repo: RepositoryIO,
    *,
    external_activity_id_sha256: str,
    local_activity_id: str,
) -> ReconciliationOverrideResult:
    review = next(
        (
            item
            for item in list_reconciliation_reviews(repo)
            if item.external_activity_id_sha256
            == external_activity_id_sha256
        ),
        None,
    )
    if review is None:
        raise ReconciliationReviewError(
            "The external activity hash is not in the current review queue"
        )
    if local_activity_id not in {
        candidate.local_activity_id for candidate in review.candidates
    }:
        raise ReconciliationReviewError(
            "The local activity is not a current candidate for this review"
        )
    candidate = next(
        candidate
        for candidate in review.candidates
        if candidate.local_activity_id == local_activity_id
    )
    if candidate.already_linked_to_different_external_id:
        raise ReconciliationReviewError(
            "The local activity is already linked to a different external "
            "recording; exclude the duplicate instead"
        )

    ledger = load_override_ledger(repo)
    existing = ledger.overrides.get(external_activity_id_sha256)
    if existing is not None:
        if existing.local_activity_id != local_activity_id:
            raise ReconciliationReviewError(
                "This external activity already has a different approval"
            )
        return ReconciliationOverrideResult(
            external_activity_id_sha256=external_activity_id_sha256,
            local_activity_id=local_activity_id,
            action="unchanged",
        )

    ledger.overrides[external_activity_id_sha256] = ReconciliationOverride(
        external_activity_id_sha256=external_activity_id_sha256,
        local_activity_id=local_activity_id,
        approved_at_utc=datetime.now(timezone.utc),
    )
    save_override_ledger(repo, ledger)
    return ReconciliationOverrideResult(
        external_activity_id_sha256=external_activity_id_sha256,
        local_activity_id=local_activity_id,
        action="approved",
    )


def exclude_duplicate_reconciliation(
    repo: RepositoryIO,
    *,
    external_activity_id_sha256: str,
    local_activity_id: str,
    review_fingerprint_sha256: str,
) -> ReconciliationExclusionResult:
    review = next(
        (
            item
            for item in list_reconciliation_reviews(repo)
            if item.external_activity_id_sha256
            == external_activity_id_sha256
        ),
        None,
    )
    if review is None:
        raise ReconciliationReviewError(
            "The external activity hash is not in the current review queue"
        )
    if review.review_fingerprint_sha256 != review_fingerprint_sha256:
        raise ReconciliationReviewError(
            "The activity review fingerprint is no longer current"
        )
    if len(review.candidates) != 1:
        raise ReconciliationReviewError(
            "Only a unique duplicate-recording candidate can be excluded"
        )
    candidate = review.candidates[0]
    if (
        candidate.local_activity_id != local_activity_id
        or not candidate.already_linked_to_different_external_id
    ):
        raise ReconciliationReviewError(
            "The selected activity is not an already-linked duplicate candidate"
        )

    ledger = load_override_ledger(repo)
    existing = ledger.exclusions.get(external_activity_id_sha256)
    if (
        existing is not None
        and existing.local_activity_id == local_activity_id
        and existing.review_fingerprint_sha256
        == review_fingerprint_sha256
    ):
        action = "unchanged"
    else:
        ledger.overrides.pop(external_activity_id_sha256, None)
        ledger.exclusions[external_activity_id_sha256] = (
            ReconciliationExclusion(
                external_activity_id_sha256=external_activity_id_sha256,
                local_activity_id=local_activity_id,
                review_fingerprint_sha256=review_fingerprint_sha256,
                reason="duplicate_external_recording",
                excluded_at_utc=datetime.now(timezone.utc),
            )
        )
        save_override_ledger(repo, ledger)
        action = "excluded"
    return ReconciliationExclusionResult(
        external_activity_id_sha256=external_activity_id_sha256,
        local_activity_id=local_activity_id,
        review_fingerprint_sha256=review_fingerprint_sha256,
        action=action,
    )
