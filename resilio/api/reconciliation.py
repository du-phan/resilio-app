"""Activity reconciliation review and approval API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from resilio.core.activity_sync.review import (
    ReconciliationReviewError,
    acknowledge_activity_quarantine,
    approve_reconciliation_override,
    exclude_duplicate_reconciliation,
    list_activity_quarantines,
    list_external_deletion_reviews,
    list_reconciliation_reviews,
)
from resilio.core.repository import RepositoryIO
from resilio.schemas.reconciliation import (
    ActivityQuarantineAcknowledgementResult,
    ActivityQuarantineReviewItem,
    ExternalDeletionReviewItem,
    ReconciliationExclusionResult,
    ReconciliationOverrideResult,
    ReconciliationReviewItem,
)


@dataclass
class ActivityReviewError:
    error_type: str
    message: str


def get_activity_reviews() -> Union[
    list[ReconciliationReviewItem],
    ActivityReviewError,
]:
    try:
        return list_reconciliation_reviews(RepositoryIO())
    except ReconciliationReviewError as exc:
        return ActivityReviewError("activity_review", str(exc))


def approve_activity_review(
    *,
    external_activity_id_sha256: str,
    local_activity_id: str,
) -> Union[ReconciliationOverrideResult, ActivityReviewError]:
    try:
        return approve_reconciliation_override(
            RepositoryIO(),
            external_activity_id_sha256=external_activity_id_sha256,
            local_activity_id=local_activity_id,
        )
    except ReconciliationReviewError as exc:
        return ActivityReviewError("activity_review", str(exc))


def exclude_duplicate_activity_review(
    *,
    external_activity_id_sha256: str,
    local_activity_id: str,
    review_fingerprint_sha256: str,
) -> Union[ReconciliationExclusionResult, ActivityReviewError]:
    try:
        return exclude_duplicate_reconciliation(
            RepositoryIO(),
            external_activity_id_sha256=external_activity_id_sha256,
            local_activity_id=local_activity_id,
            review_fingerprint_sha256=review_fingerprint_sha256,
        )
    except ReconciliationReviewError as exc:
        return ActivityReviewError("activity_review", str(exc))


def get_activity_quarantines() -> Union[
    list[ActivityQuarantineReviewItem],
    ActivityReviewError,
]:
    try:
        return list_activity_quarantines(RepositoryIO())
    except ReconciliationReviewError as exc:
        return ActivityReviewError("activity_review", str(exc))


def acknowledge_activity_quarantine_review(
    *,
    external_activity_id_sha256: str,
    failure_fingerprint_sha256: str,
) -> Union[
    ActivityQuarantineAcknowledgementResult,
    ActivityReviewError,
]:
    try:
        return acknowledge_activity_quarantine(
            RepositoryIO(),
            external_activity_id_sha256=external_activity_id_sha256,
            failure_fingerprint_sha256=failure_fingerprint_sha256,
        )
    except ReconciliationReviewError as exc:
        return ActivityReviewError("activity_review", str(exc))


def get_external_deletion_reviews() -> Union[
    list[ExternalDeletionReviewItem],
    ActivityReviewError,
]:
    try:
        return list_external_deletion_reviews(RepositoryIO())
    except ReconciliationReviewError as exc:
        return ActivityReviewError("activity_review", str(exc))
