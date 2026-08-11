"""Owned external workout publication state."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.workout_pairing import RemotePairingStatus


class PublicationPushError(BaseModel):
    service: str = Field(min_length=1)
    message: str = Field(min_length=1)
    observed_at_utc: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")


GarminForwardingStatus = Literal[
    "eligible_unverified",
    "not_configured",
    "provider_error_observed",
]


class PublishedWorkout(BaseModel):
    workout_identity: PlanWorkoutIdentity
    applied_week_approval_id: str = Field(pattern=r"^week_approval_[a-f0-9]{16}$")
    applied_running_workouts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workout_prescription_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_timezone: str = Field(min_length=1)
    event_id: int
    requested_uid: str
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_event_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: Literal["run"]
    occurrence_date: date
    approved_start_time_local: Optional[time] = None
    provider_start_date_local: str
    garmin_forwarding_status: GarminForwardingStatus
    provider_push_errors: list[PublicationPushError] = Field(default_factory=list)
    provider_computed_aerobic_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_relative_intensity_percent: Optional[float] = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    provider_fitness_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_fatigue_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    verified_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class HistoricalLegacyWorkoutPublication(BaseModel):
    """Read-only v6 ownership retained when applied authority is unavailable."""

    workout_identity: PlanWorkoutIdentity
    event_id: int
    requested_uid: str
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_event_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: Literal["run"]
    occurrence_date: date
    approved_start_time_local: Optional[time] = None
    provider_start_date_local: str
    garmin_forwarding_status: GarminForwardingStatus
    provider_push_errors: list[PublicationPushError] = Field(default_factory=list)
    provider_computed_aerobic_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_relative_intensity_percent: Optional[float] = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    provider_fitness_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_fatigue_load_points: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    verified_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class PendingWorkoutPublication(BaseModel):
    """Durable local intent written before any remote event mutation."""

    workout_identity: PlanWorkoutIdentity
    applied_week_approval_id: str = Field(pattern=r"^week_approval_[a-f0-9]{16}$")
    applied_running_workouts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    workout_prescription_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_timezone: str = Field(min_length=1)
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: Literal["run"]
    occurrence_date: date
    approved_start_time_local: Optional[time] = None
    provider_start_date_local: str
    prepared_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class ConfirmedPublicationDriftTarget(BaseModel):
    """Exact remote bytes the athlete authorized Resilio to replace or retire."""

    local_workout_id: str = Field(min_length=1)
    event_id: int = Field(gt=0)
    observed_remote_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class PublicationDriftResolution(BaseModel):
    """Athlete-confirmed authority used to replace owned remote drift."""

    plan_id: str
    plan_revision_id: str
    week_number: int = Field(ge=1)
    strategy: Literal["restore_local"] = "restore_local"
    confirmed_targets: list[ConfirmedPublicationDriftTarget] = Field(default_factory=list)
    athlete_confirmation_reference: str = Field(min_length=1)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def confirmation_has_exact_targets(self) -> "PublicationDriftResolution":
        if not self.confirmed_targets:
            raise ValueError("drift resolution requires exact confirmed targets")
        target_ids = [target.local_workout_id for target in self.confirmed_targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("confirmed drift target workout IDs must be unique")
        return self


class HistoricalFulfillmentRetirementConfirmation(BaseModel):
    """Historical athlete authority for a deletion the v1 workflow performed."""

    plan_id: str
    plan_revision_id: str
    week_number: int = Field(ge=1)
    strategy: Literal["retire_fulfilled"] = "retire_fulfilled"
    confirmed_targets: list[ConfirmedPublicationDriftTarget] = Field(min_length=1)
    athlete_confirmation_reference: str = Field(min_length=1)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("historical retirement confirmation must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def confirmed_workout_ids_are_unique(
        self,
    ) -> "HistoricalFulfillmentRetirementConfirmation":
        workout_ids = [target.local_workout_id for target in self.confirmed_targets]
        if len(workout_ids) != len(set(workout_ids)):
            raise ValueError("historical confirmed workout IDs must be unique")
        return self


class HistoricalLegacyPublicationDriftResolution(BaseModel):
    """Pre-token drift authority retained for audit but never reusable."""

    plan_id: str
    plan_revision_id: str
    week_number: int = Field(ge=1)
    strategy: Literal["restore_local"] = "restore_local"
    athlete_confirmation_reference: str = Field(min_length=1)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)


class RetiredWorkoutPublication(BaseModel):
    """Historical audit of an event removed by the superseded v1 workflow."""

    publication: PublishedWorkout
    retirement_reason: Literal["fulfilled_early"] = "fulfilled_early"
    fulfilling_local_activity_id: str = Field(min_length=1)
    fulfillment_record_sha256_at_retirement: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_local_date_at_retirement: date
    schedule_offset_days_at_retirement: int = Field(lt=0)
    provider_deletion_status: Literal["deleted", "already_absent"]
    retired_at_utc: datetime
    reopened_by_fulfillment_revocation_id: Optional[str] = Field(
        default=None,
        pattern=r"^fulfillment_revocation_[0-9a-f]{16}$",
    )
    reopened_at_utc: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("retired_at_utc", "reopened_at_utc")
    @classmethod
    def retirement_time_is_utc(cls, value: datetime) -> datetime:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retirement timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def reopening_fields_are_coherent(self) -> "RetiredWorkoutPublication":
        if (self.reopened_at_utc is None) != (self.reopened_by_fulfillment_revocation_id is None):
            raise ValueError("retirement reopening requires an ID and timestamp")
        return self


class RetiredPendingWorkoutPublication(BaseModel):
    """Historical audit of a pending intent removed by the v1 workflow."""

    pending_publication: PendingWorkoutPublication
    fulfilling_local_activity_id: str = Field(min_length=1)
    fulfillment_record_sha256_at_retirement: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_local_date_at_retirement: date
    schedule_offset_days_at_retirement: int = Field(lt=0)
    provider_deletion_status: Literal["deleted", "no_remote_event"]
    remote_event_id: Optional[int] = Field(default=None, gt=0)
    retired_at_utc: datetime
    reopened_by_fulfillment_revocation_id: Optional[str] = Field(
        default=None,
        pattern=r"^fulfillment_revocation_[0-9a-f]{16}$",
    )
    reopened_at_utc: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def event_id_matches_status(self) -> "RetiredPendingWorkoutPublication":
        if (self.remote_event_id is not None) != (self.provider_deletion_status == "deleted"):
            raise ValueError("pending retirement event ID must match deletion status")
        if (self.reopened_at_utc is None) != (self.reopened_by_fulfillment_revocation_id is None):
            raise ValueError("pending retirement reopening requires an ID and timestamp")
        return self

    @field_validator("retired_at_utc", "reopened_at_utc")
    @classmethod
    def retirement_time_is_utc(cls, value: datetime) -> datetime:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retirement timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)


class PublicationManifest(BaseModel):
    schema_version: Literal[8] = 8
    workouts: dict[str, PublishedWorkout] = Field(default_factory=dict)
    pending: dict[str, PendingWorkoutPublication] = Field(default_factory=dict)
    historical_fulfillment_event_retirements: list[RetiredWorkoutPublication] = Field(
        default_factory=list
    )
    historical_fulfillment_pending_retirements: list[
        RetiredPendingWorkoutPublication
    ] = Field(default_factory=list)
    historical_legacy_workouts: dict[
        str,
        HistoricalLegacyWorkoutPublication,
    ] = Field(default_factory=dict)
    drift_resolutions: list[PublicationDriftResolution] = Field(default_factory=list)
    historical_legacy_drift_resolutions: list[HistoricalLegacyPublicationDriftResolution] = Field(
        default_factory=list
    )
    historical_fulfillment_retirement_confirmations: list[
        HistoricalFulfillmentRetirementConfirmation
    ] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ownership_identities_are_unique(self) -> "PublicationManifest":
        event_owners: dict[int, str] = {}
        identity_owners: dict[tuple[str, str], str] = {}
        for local_id, record in self.workouts.items():
            if record.workout_identity.local_workout_id != local_id:
                raise ValueError("publication manifest key must match local workout ID")
            prior_event_owner = event_owners.setdefault(
                record.event_id,
                local_id,
            )
            if prior_event_owner != local_id:
                raise ValueError("publication manifest event IDs must be unique")
            for field_name, value in (
                ("requested_uid", record.requested_uid),
                ("uid", record.uid),
                ("external_id", record.external_id),
            ):
                prior_owner = identity_owners.setdefault(
                    (field_name, value),
                    local_id,
                )
                if prior_owner != local_id:
                    raise ValueError("publication manifest ownership identities must be unique")
        for local_id, pending_record in self.pending.items():
            if pending_record.workout_identity.local_workout_id != local_id:
                raise ValueError("pending publication key must match local workout ID")
            published_record = self.workouts.get(local_id)
            if (
                published_record is not None
                and published_record.workout_identity != pending_record.workout_identity
            ):
                raise ValueError(
                    "pending publication lineage must match the published workout lineage"
                )
            for field_name, value in (
                ("uid", pending_record.uid),
                ("external_id", pending_record.external_id),
            ):
                prior_owner = identity_owners.setdefault(
                    (field_name, value),
                    local_id,
                )
                if prior_owner != local_id:
                    raise ValueError("publication manifest ownership identities must be unique")
        for local_id, historical_record in self.historical_legacy_workouts.items():
            if historical_record.workout_identity.local_workout_id != local_id:
                raise ValueError("historical publication key must match local workout ID")
            if (
                local_id in self.workouts
                or local_id in self.pending
            ):
                raise ValueError("historical publication cannot remain active")
            prior_event_owner = event_owners.setdefault(
                historical_record.event_id,
                local_id,
            )
            if prior_event_owner != local_id:
                raise ValueError("publication manifest event IDs must be unique")
        return self


PublicationAction = Literal[
    "created",
    "updated",
    "noop",
    "recovered",
    "deleted",
    "recovered_deleted",
    "deletion_monitoring",
]


class PublicationResult(BaseModel):
    action: PublicationAction
    local_workout_id: str
    event_id: Optional[int] = None
    uid: str
    external_id: str
    fingerprint_sha256: Optional[str] = None
    provider_occurrence_date: Optional[date] = None
    garmin_forwarding_status: GarminForwardingStatus = "not_configured"
    provider_push_errors: list[PublicationPushError] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RunWorkoutSynchronizationPreferences(BaseModel):
    """Athlete-confirmed automation policy for external run publication."""

    schema_version: Literal[2] = 2
    run_synchronization_mode: Literal["disabled", "after_weekly_apply"] = "disabled"
    untimed_run_policy: Literal["calendar_day"] = "calendar_day"
    requested_downstream_device: Literal["garmin"] = "garmin"
    athlete_confirmation_reference: Optional[str] = Field(default=None, min_length=1)
    confirmed_at_utc: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def confirmation_timestamp_is_utc(
        cls,
        value: Optional[datetime],
    ) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def enabled_automation_has_confirmation(
        self,
    ) -> "RunWorkoutSynchronizationPreferences":
        if self.run_synchronization_mode == "after_weekly_apply" and (
            self.athlete_confirmation_reference is None or self.confirmed_at_utc is None
        ):
            raise ValueError("automatic run publication requires athlete confirmation evidence")
        return self


class RunSynchronizationCapabilities(BaseModel):
    """Read-only Intervals and Garmin readiness for running prescriptions."""

    athlete_id: str
    athlete_timezone: str
    run_sport_settings_id: int
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    intervals_calendar_ready: bool
    garmin_connected: bool
    garmin_workout_forwarding_enabled: bool
    garmin_run_filter_allows: bool
    garmin_forwarding_eligible: bool
    targetless_workouts_ready: bool
    absolute_heart_rate_targets_ready: bool
    percent_lthr_targets_ready: bool
    percent_max_heart_rate_targets_ready: bool
    pace_targets_ready: bool
    lactate_threshold_heart_rate_beats_per_minute: Optional[int] = None
    maximum_heart_rate_beats_per_minute: Optional[int] = None
    heart_rate_zone_count: int = Field(ge=0)
    threshold_pace_seconds_per_kilometer: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    pace_zone_count: int = Field(ge=0)
    limitations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class WeekSynchronizationItem(BaseModel):
    local_workout_id: str
    occurrence_date: date
    provider_occurrence_date: Optional[date] = None
    status: Literal[
        "ready",
        "created",
        "updated",
        "noop",
        "recovered",
        "skipped_past",
        "error",
        "deleted",
        "recovered_deleted",
        "deletion_monitoring",
    ]
    event_id: Optional[int] = None
    error_type: Optional[str] = None
    message: Optional[str] = None
    drift_resolution_token_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    local_activity_id: Optional[str] = None
    remote_pairing_status: Optional[RemotePairingStatus] = None
    remote_pairing_operation_id: Optional[str] = Field(
        default=None,
        pattern=r"^pairing_operation_[0-9a-f]{16}$",
    )
    remote_pairing_blocker_code: Optional[str] = None
    pairing_drift_token_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    garmin_forwarding_status: Optional[GarminForwardingStatus] = None
    provider_push_errors: list[PublicationPushError] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RunWeekSynchronizationReport(BaseModel):
    week_number: int = Field(ge=1)
    as_of_date: date
    operation: Literal[
        "status",
        "reconcile",
        "restore_local",
        "resolve_pairing_drift",
    ]
    reconciliation_safe: bool
    run_workouts_considered: int = Field(ge=0)
    desired_future_run_workouts: int = Field(ge=0)
    partial: bool = False
    capabilities: RunSynchronizationCapabilities
    items: list[WeekSynchronizationItem] = Field(default_factory=list)
    owned_future_deletion_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
