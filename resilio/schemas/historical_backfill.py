"""Provider-neutral contracts for the historical activity publication ledger."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

Sha256 = str


class BackfillDecisionAction(str, Enum):
    PUBLISH = "publish"
    EXCLUDE_HIDDEN = "exclude_hidden"
    ADOPT_OWNED = "adopt_owned"
    QUARANTINE = "quarantine"


class HistoricalTimeMode(str, Enum):
    EXACT_WALL_TIME = "exact_wall_time"
    LOCAL_NOON = "local_noon"


class BackfillPhase(str, Enum):
    DRY_RUN = "dry_run"
    CANARY_PENDING = "canary_pending"
    CANARY_VERIFIED = "canary_verified"
    APPLY_PENDING = "apply_pending"
    APPLIED = "applied"
    ROLLBACK_PENDING = "rollback_pending"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class ApprovalStage(str, Enum):
    CANARY = "canary"
    APPLY = "apply"
    RPE_DEFAULT = "rpe_default"


class PublicationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    ROLLBACK_PENDING = "rollback_pending"
    ROLLED_BACK = "rolled_back"


class FrozenBackfillBaseline(BaseModel):
    selected: int = 433
    hidden_excluded: int = 29
    publishable: int = 404
    exact_time: int = 405
    noon_adjusted: int = 28

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def counts_reconcile(self) -> "FrozenBackfillBaseline":
        if self.selected - self.hidden_excluded != self.publishable:
            raise ValueError("frozen selected/excluded/publishable counts do not reconcile")
        if self.exact_time + self.noon_adjusted != self.selected:
            raise ValueError("frozen timestamp coverage does not reconcile")
        return self


class BackfillDecision(BaseModel):
    local_activity_id: str
    action: BackfillDecisionAction
    time_mode: HistoricalTimeMode
    local_date: date
    source_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    payload_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    remote_activity_id_sha256: Optional[Sha256] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class BackfillCoverage(BaseModel):
    archive_activity_count: int
    initial_external_links: int
    selected: int
    hidden_excluded: int
    publishable: int
    exact_time: int
    noon_adjusted: int
    athlete_rpe: int
    public_descriptions: int
    positive_distance: int
    positive_elevation: int
    owned_recoveries: int = 0
    conflicts: int = 0

    model_config = ConfigDict(extra="forbid")


class BackfillPlan(BaseModel):
    schema_version: Literal[1] = 1
    run_id: str
    timezone: Literal["Europe/Paris"] = "Europe/Paris"
    destination_type: Literal["Bouldering", "RockClimbing"] = "RockClimbing"
    inventory_oldest: date
    inventory_newest: date
    downloads_disabled_confirmed: bool
    frozen_baseline: FrozenBackfillBaseline
    archive_source_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    metrics_tree_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    sync_state_base_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    external_inventory_base_digest_sha256: Sha256 = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    report_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    canary_local_activity_id: Optional[str]
    coverage: BackfillCoverage
    decisions: list[BackfillDecision]
    plan_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def decisions_are_unique(self) -> "BackfillPlan":
        ids = [decision.local_activity_id for decision in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("backfill plan contains duplicate local activity IDs")
        if len(ids) != self.coverage.selected:
            raise ValueError("backfill plan decision count does not match coverage")
        return self


class BackfillApproval(BaseModel):
    schema_version: Literal[1] = 1
    stage: ApprovalStage
    plan_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    canary_digest_sha256: Optional[Sha256] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    recorded_at_utc: datetime
    approval_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def mutation_stages_require_canary(self) -> "BackfillApproval":
        if (
            self.stage in {ApprovalStage.APPLY, ApprovalStage.RPE_DEFAULT}
            and not self.canary_digest_sha256
        ):
            raise ValueError(
                f"{self.stage} approval requires the exact canary digest"
            )
        if self.stage == ApprovalStage.CANARY and self.canary_digest_sha256:
            raise ValueError("canary approval must not include a canary digest")
        return self


class PendingPublicationIntent(BaseModel):
    local_activity_id: str
    ownership_external_id: str
    plan_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    payload_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    stage: Literal["canary", "apply", "rpe_default"]
    initiated_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class HistoricalActivityPublication(BaseModel):
    local_activity_id: str
    status: PublicationStatus
    destination_activity_id: str
    ownership_external_id: str
    destination_type: Literal["Bouldering", "RockClimbing"] = "RockClimbing"
    local_date: date
    plan_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    source_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    payload_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    readback_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    published_at_utc: datetime
    verified_at_utc: datetime
    rolled_back_at_utc: Optional[datetime] = None
    remote_athlete_rpe_override: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
    )

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class HistoricalActivityPublicationLedger(BaseModel):
    schema_version: Literal[1] = 1
    publications: dict[str, HistoricalActivityPublication] = Field(
        default_factory=dict
    )
    pending: dict[str, PendingPublicationIntent] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ownership_is_one_to_one(self) -> "HistoricalActivityPublicationLedger":
        for key, publication in self.publications.items():
            if key != publication.local_activity_id:
                raise ValueError("publication ledger key/local ID mismatch")
        for key, pending in self.pending.items():
            if key != pending.local_activity_id:
                raise ValueError("pending ledger key/local ID mismatch")
        active = [
            publication
            for publication in self.publications.values()
            if publication.status != PublicationStatus.ROLLED_BACK
        ]
        destination_ids = [item.destination_activity_id for item in active]
        external_ids = [item.ownership_external_id for item in active]
        if len(destination_ids) != len(set(destination_ids)):
            raise ValueError("destination activity ID is owned by multiple local records")
        if len(external_ids) != len(set(external_ids)):
            raise ValueError("ownership external ID is used by multiple local records")
        return self


class CanaryProof(BaseModel):
    schema_version: Literal[1] = 1
    plan_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    local_activity_id: str
    destination_activity_id: str
    ownership_external_id: str
    payload_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    readback_fingerprint_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    repeated_submission_activity_id: str
    matching_remote_count: Literal[1] = 1
    verified_at_utc: datetime
    canary_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class BackfillRunEnvelope(BaseModel):
    schema_version: Literal[1] = 1
    run_id: str
    phase: BackfillPhase
    plan_digest_sha256: Sha256 = Field(pattern=r"^[0-9a-f]{64}$")
    updated_at_utc: datetime
    completed_publications: int = 0
    pending_publications: int = 0
    rolled_back_publications: int = 0
    last_error: Optional[str] = None

    model_config = ConfigDict(extra="forbid", use_enum_values=True)
