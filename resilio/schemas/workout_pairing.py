"""Durable native Intervals activity/event pairing contracts."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.canonical import canonical_data_sha256
from resilio.schemas.plan_history import PlanWorkoutIdentity

RemotePairingAction = Literal["pair", "unpair"]
RemotePairingState = Literal["pending", "verified", "blocked"]
RemotePairingStatus = Literal[
    "ready_to_pair",
    "paired",
    "pairing_noop",
    "pairing_blocked",
    "ready_to_unpair",
    "unpaired",
]


def native_pair_operation_id(
    *,
    local_activity_id: str,
    intervals_icu_activity_id: str,
    workout_identity: PlanWorkoutIdentity,
    event_id: int,
    fulfillment_record_sha256: str,
) -> str:
    """Derive one ordinary pair-operation identity from immutable evidence."""
    payload = {
        "action": "pair",
        "local_activity_id": local_activity_id,
        "intervals_icu_activity_id": intervals_icu_activity_id,
        "workout_identity": workout_identity.model_dump(mode="json"),
        "event_id": event_id,
        "fulfillment_record_sha256": fulfillment_record_sha256,
    }
    return f"pairing_operation_{canonical_data_sha256(payload)[:16]}"


def restored_pair_operation_id(pairing_drift_token_sha256: str) -> str:
    """Derive a new operation identity for one athlete-authorized restoration."""
    return (
        "pairing_operation_"
        f"{canonical_data_sha256({'pairing_drift_token_sha256': pairing_drift_token_sha256})[:16]}"
    )


def native_unpair_operation_id(
    *,
    local_activity_id: str,
    event_id: int,
    revocation_id: str,
    fulfillment_record_sha256: str,
) -> str:
    """Derive one unpair-operation identity from its exact revocation."""
    payload = {
        "action": "unpair",
        "local_activity_id": local_activity_id,
        "event_id": event_id,
        "revocation_id": revocation_id,
        "fulfillment_record_sha256": fulfillment_record_sha256,
    }
    return f"pairing_operation_{canonical_data_sha256(payload)[:16]}"


class RemoteWorkoutPairingResult(BaseModel):
    """One presentation-neutral native pairing reconciliation result."""

    local_activity_id: str = Field(min_length=1)
    local_workout_id: str = Field(min_length=1)
    intervals_icu_activity_id: str = Field(min_length=1)
    event_id: int = Field(gt=0)
    status: RemotePairingStatus
    operation_id: str | None = Field(
        default=None,
        pattern=r"^pairing_operation_[0-9a-f]{16}$",
    )
    blocker_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{2,100}$")
    message: str | None = Field(default=None, min_length=1, max_length=500)
    pairing_drift_token_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def blocker_fields_match_status(self) -> "RemoteWorkoutPairingResult":
        blocked = self.status == "pairing_blocked"
        if blocked != (self.blocker_code is not None and self.message is not None):
            raise ValueError("pairing blocker fields must match pairing_blocked status")
        return self


class RemotePairingOperationsReport(BaseModel):
    """Results of draining durable native pairing-operation obligations."""

    results: list[RemoteWorkoutPairingResult] = Field(default_factory=list)
    partial: bool = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def partial_matches_blocked_results(self) -> "RemotePairingOperationsReport":
        blocked = any(result.status == "pairing_blocked" for result in self.results)
        if self.partial != blocked:
            raise ValueError("pairing operation report partial flag must match blockers")
        return self


class RemotePairingDriftResolution(BaseModel):
    """Athlete authority for one exact native-pair guard or removal drift."""

    pairing_drift_token_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pair_operation_snapshot: "RemoteWorkoutPairingOperation"
    observed_provider_activity_guard_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    athlete_confirmation_reference: str = Field(min_length=1, max_length=2_000)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def confirmation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pairing drift confirmation time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def authority_snapshot_matches_token(self) -> "RemotePairingDriftResolution":
        operation = self.pair_operation_snapshot
        if operation.action != "pair":
            raise ValueError("pairing drift authority requires a pair-operation snapshot")
        expected_token = remote_pairing_drift_token_sha256(
            operation,
            provider_activity_guard_sha256=(
                self.observed_provider_activity_guard_sha256
            ),
        )
        if self.pairing_drift_token_sha256 != expected_token:
            raise ValueError("pairing drift token does not match its evidence snapshot")
        authority_time_utc = operation.verified_at_utc or operation.requested_at_utc
        if self.confirmed_at_utc < authority_time_utc:
            raise ValueError("pairing drift confirmation cannot predate its operation")
        return self


class RemoteWorkoutPairingOperation(BaseModel):
    """Durable, evidence-bound intent for one Intervals native pairing mutation."""

    operation_id: str = Field(pattern=r"^pairing_operation_[0-9a-f]{16}$")
    action: RemotePairingAction
    state: RemotePairingState
    local_activity_id: str = Field(min_length=1)
    intervals_icu_activity_id: str = Field(min_length=1)
    workout_identity: PlanWorkoutIdentity
    event_id: int = Field(gt=0)
    activity_performance_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_provider_event_fingerprint_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    fulfillment_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    revocation_id: str | None = Field(
        default=None,
        pattern=r"^fulfillment_revocation_[0-9a-f]{16}$",
    )
    expected_paired_event_id_before: int | None = Field(default=None, gt=0)
    requested_at_utc: datetime
    expected_provider_activity_guard_sha256_before: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    provider_write_submitted_at_utc: datetime | None = None
    last_attempted_at_utc: datetime | None = None
    verified_at_utc: datetime | None = None
    provider_activity_guard_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    blocker_code: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]{2,100}$",
    )
    blocker_message: str | None = Field(default=None, min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "requested_at_utc",
        "provider_write_submitted_at_utc",
        "last_attempted_at_utc",
        "verified_at_utc",
    )
    @classmethod
    def lifecycle_times_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("remote pairing lifecycle timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def lifecycle_is_coherent(self) -> "RemoteWorkoutPairingOperation":
        if self.action == "pair":
            if self.expected_paired_event_id_before is not None or self.revocation_id is not None:
                raise ValueError("pair operation must start from an unpaired activity")
        elif (
            self.expected_paired_event_id_before != self.event_id
            or self.revocation_id is None
        ):
            raise ValueError("unpair operation requires its exact pair and revocation")
        if self.state == "verified":
            if (
                self.last_attempted_at_utc is None
                or self.verified_at_utc is None
                or self.expected_provider_activity_guard_sha256_before is None
                or self.provider_activity_guard_sha256 is None
            ):
                raise ValueError("verified pairing operation requires complete readback evidence")
            if self.blocker_code is not None or self.blocker_message is not None:
                raise ValueError("verified pairing operation cannot retain a blocker")
        elif self.state == "blocked":
            if (
                self.last_attempted_at_utc is None
                or self.blocker_code is None
                or self.blocker_message is None
                or self.verified_at_utc is not None
            ):
                raise ValueError("blocked pairing operation requires exact blocker evidence")
        elif any(
            value is not None
            for value in (
                self.verified_at_utc,
                self.provider_activity_guard_sha256,
                self.blocker_code,
                self.blocker_message,
            )
        ):
            raise ValueError("pending pairing operation cannot claim verification or blockage")
        for timestamp in (
            self.provider_write_submitted_at_utc,
            self.last_attempted_at_utc,
            self.verified_at_utc,
        ):
            if timestamp is not None and timestamp < self.requested_at_utc:
                raise ValueError("pairing operation lifecycle cannot predate its request")
        if (
            self.provider_write_submitted_at_utc is not None
            and self.expected_provider_activity_guard_sha256_before is None
        ):
            raise ValueError("submitted pairing operation requires its pre-write guard")
        if (
            self.verified_at_utc is not None
            and self.last_attempted_at_utc is not None
            and self.verified_at_utc < self.last_attempted_at_utc
        ):
            raise ValueError("pairing verification cannot predate its final attempt")
        return self

    @property
    def desired_paired_event_id(self) -> int | None:
        return self.event_id if self.action == "pair" else None


def remote_pairing_drift_token_sha256(
    operation: RemoteWorkoutPairingOperation,
    *,
    provider_activity_guard_sha256: str,
) -> str:
    """Bind one removed pair observation to its verified operation snapshot."""
    return canonical_data_sha256(
        {
            "operation": operation.model_dump(mode="json"),
            "observed_paired_event_id": None,
            "provider_activity_guard_sha256": provider_activity_guard_sha256,
        }
    )
