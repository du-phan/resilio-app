"""Durable provider-operation contracts for workout publication."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.publication import PendingWorkoutPublication, PublishedWorkout


class PendingPublicationDeletionOperation(BaseModel):
    """Permanent ownership tombstone for an ambiguously submitted create."""

    operation_id: str = Field(pattern=r"^publication_deletion_[0-9a-f]{16}$")
    pending_publication: PendingWorkoutPublication
    previous_publication: Optional[PublishedWorkout] = None
    reason: Literal["workout_removed"] = "workout_removed"
    state: Literal["staged", "monitoring"] = "staged"
    requested_at_utc: datetime
    monitoring_started_at_utc: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("requested_at_utc", "monitoring_started_at_utc")
    @classmethod
    def requested_time_is_utc(cls, value: datetime) -> datetime:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("publication deletion request time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def monitoring_state_has_causal_timestamp(
        self,
    ) -> "PendingPublicationDeletionOperation":
        if (self.state == "monitoring") != (
            self.monitoring_started_at_utc is not None
        ):
            raise ValueError("publication deletion monitoring requires its timestamp")
        if (
            self.monitoring_started_at_utc is not None
            and self.monitoring_started_at_utc < self.requested_at_utc
        ):
            raise ValueError("publication deletion monitoring cannot predate its request")
        previous = self.previous_publication
        if previous is not None and (
            previous.workout_identity != self.pending_publication.workout_identity
            or previous.external_id != self.pending_publication.external_id
        ):
            raise ValueError(
                "publication deletion published and pending authority must share lineage"
            )
        return self


class PublicationDeletionDriftResolution(BaseModel):
    """Athlete authority to delete one exact drifted tombstone event."""

    operation_id: str = Field(pattern=r"^publication_deletion_[0-9a-f]{16}$")
    event_id: int = Field(gt=0)
    observed_remote_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    drift_resolution_token_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    athlete_confirmation_reference: str = Field(min_length=1)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def confirmation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("publication deletion confirmation must be timezone-aware")
        return value.astimezone(timezone.utc)


class PublicationDeletionManifest(BaseModel):
    schema_version: Literal[1] = 1
    operations: dict[str, PendingPublicationDeletionOperation] = Field(
        default_factory=dict
    )
    drift_resolutions: list[PublicationDeletionDriftResolution] = Field(
        default_factory=list
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def operation_keys_and_ownership_are_unique(self) -> "PublicationDeletionManifest":
        local_workout_owners: dict[str, str] = {}
        external_id_owners: dict[str, str] = {}
        for operation_id, operation in self.operations.items():
            if operation.operation_id != operation_id:
                raise ValueError("publication deletion key must match operation ID")
            local_workout_id = (
                operation.pending_publication.workout_identity.local_workout_id
            )
            prior_operation = local_workout_owners.setdefault(
                local_workout_id,
                operation_id,
            )
            if prior_operation != operation_id:
                raise ValueError(
                    "publication deletion workout identities must be unique"
                )
            external_id = operation.pending_publication.external_id
            prior_operation = external_id_owners.setdefault(external_id, operation_id)
            if prior_operation != operation_id:
                raise ValueError(
                    "publication deletion external identities must be unique"
                )
        resolution_tokens: set[str] = set()
        for resolution in self.drift_resolutions:
            resolved_operation = self.operations.get(resolution.operation_id)
            if resolved_operation is None:
                raise ValueError(
                    "publication deletion drift resolution lacks its operation"
                )
            if resolution.confirmed_at_utc < resolved_operation.requested_at_utc:
                raise ValueError(
                    "publication deletion drift resolution predates its operation"
                )
            if resolution.drift_resolution_token_sha256 in resolution_tokens:
                raise ValueError(
                    "publication deletion drift resolution tokens must be unique"
                )
            resolution_tokens.add(resolution.drift_resolution_token_sha256)
        return self


PublicationDeletionStatus = Literal["deletion_monitoring", "deleted", "error"]


class PublicationDeletionOperationItem(BaseModel):
    operation_id: str = Field(pattern=r"^publication_deletion_[0-9a-f]{16}$")
    local_workout_id: str = Field(min_length=1)
    occurrence_date: date
    provider_occurrence_date: date
    status: PublicationDeletionStatus
    event_id: Optional[int] = None
    error_type: Optional[str] = None
    message: Optional[str] = None
    drift_resolution_token_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    model_config = ConfigDict(extra="forbid")


class PublicationDeletionOperationsReport(BaseModel):
    reconciliation_safe: bool
    partial: bool = False
    items: list[PublicationDeletionOperationItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
