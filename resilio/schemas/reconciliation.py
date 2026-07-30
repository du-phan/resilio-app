"""Deterministic activity reconciliation decisions."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from resilio.schemas.activity import CanonicalActivity


class ReconciliationAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    LINK = "link"
    AMBIGUOUS = "ambiguous"


class ReconciliationDecision(BaseModel):
    action: ReconciliationAction
    rule: str
    external_activity_id: str
    local_activity_id: Optional[str] = None
    candidate_local_ids: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    activity: Optional[CanonicalActivity] = None

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ReconciliationReviewCandidate(BaseModel):
    local_activity_id: str
    local_date: date
    sport: str
    name: str
    duration_seconds: int
    distance_meters: Optional[float] = None
    already_linked_to_different_external_id: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ReconciliationReviewItem(BaseModel):
    external_activity_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule: str
    original_file_probe: Optional[str] = None
    candidates: list[ReconciliationReviewCandidate]

    model_config = ConfigDict(extra="forbid")


class ReconciliationOverride(BaseModel):
    external_activity_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_activity_id: str
    review_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class ReconciliationExclusion(BaseModel):
    external_activity_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_activity_id: str
    review_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: Literal["duplicate_external_recording"]
    excluded_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class ReconciliationOverrideLedger(BaseModel):
    schema_version: int = 1
    overrides: dict[str, ReconciliationOverride] = Field(default_factory=dict)
    exclusions: dict[str, ReconciliationExclusion] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ReconciliationOverrideResult(BaseModel):
    external_activity_id_sha256: str
    local_activity_id: str
    review_fingerprint_sha256: str
    action: str

    model_config = ConfigDict(extra="forbid")


class ReconciliationExclusionResult(BaseModel):
    external_activity_id_sha256: str
    local_activity_id: str
    review_fingerprint_sha256: str
    action: str

    model_config = ConfigDict(extra="forbid")


class ActivityValidationIssue(BaseModel):
    location: str
    issue_type: str

    model_config = ConfigDict(extra="forbid")


class ActivityQuarantineReviewItem(BaseModel):
    external_activity_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule: str
    error_type: str
    validation_issues: list[ActivityValidationIssue] = Field(default_factory=list)
    failure_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledgeable: bool = False
    acknowledged: bool = False

    model_config = ConfigDict(extra="forbid")


class ActivityQuarantineAcknowledgement(BaseModel):
    external_activity_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    failure_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledged_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class ActivityQuarantineAcknowledgementLedger(BaseModel):
    schema_version: int = 1
    acknowledgements: dict[
        str,
        ActivityQuarantineAcknowledgement,
    ] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ActivityQuarantineAcknowledgementResult(BaseModel):
    external_activity_id_sha256: str
    failure_fingerprint_sha256: str
    action: str

    model_config = ConfigDict(extra="forbid")


class ExternalDeletionReviewItem(BaseModel):
    local_activity_id: str
    local_date: date
    sport: str
    name: str

    model_config = ConfigDict(extra="forbid")
