"""Owned external workout publication state."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.plan_history import PlanWorkoutIdentity


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
    event_id: int
    requested_uid: str
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_event_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: str
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
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: str
    occurrence_date: date
    approved_start_time_local: Optional[time] = None
    provider_start_date_local: str
    prepared_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class PublicationDriftResolution(BaseModel):
    """Athlete-confirmed authority used to replace owned remote drift."""

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


class PublicationManifest(BaseModel):
    schema_version: Literal[5] = 5
    workouts: dict[str, PublishedWorkout] = Field(default_factory=dict)
    pending: dict[str, PendingWorkoutPublication] = Field(default_factory=dict)
    drift_resolutions: list[PublicationDriftResolution] = Field(default_factory=list)

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
        return self


PublicationAction = Literal[
    "created",
    "updated",
    "noop",
    "recovered",
    "deleted",
    "recovered_deleted",
]


class PublicationResult(BaseModel):
    action: PublicationAction
    local_workout_id: str
    event_id: Optional[int] = None
    uid: str
    external_id: str
    fingerprint_sha256: Optional[str] = None
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
    status: Literal[
        "ready",
        "created",
        "updated",
        "noop",
        "recovered",
        "skipped_past",
        "skipped_completed",
        "error",
        "deleted",
        "recovered_deleted",
    ]
    event_id: Optional[int] = None
    error_type: Optional[str] = None
    message: Optional[str] = None
    garmin_forwarding_status: Optional[GarminForwardingStatus] = None
    provider_push_errors: list[PublicationPushError] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class RunWeekSynchronizationReport(BaseModel):
    week_number: int = Field(ge=1)
    as_of_date: date
    operation: Literal["status", "reconcile", "restore_local"]
    reconciliation_safe: bool
    run_workouts_considered: int = Field(ge=0)
    desired_future_run_workouts: int = Field(ge=0)
    ignored_non_run_workouts: int = Field(ge=0)
    partial: bool = False
    capabilities: RunSynchronizationCapabilities
    items: list[WeekSynchronizationItem] = Field(default_factory=list)
    owned_future_deletion_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class WorkoutCompletionMatch(BaseModel):
    local_activity_id: str
    workout_identity: PlanWorkoutIdentity
    match_method: str = Field(pattern=r"^paired_event_id$")
    matched_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class WorkoutCompletionManifest(BaseModel):
    schema_version: Literal[3] = 3
    matches: dict[str, WorkoutCompletionMatch] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def completion_identities_are_unique(
        self,
    ) -> "WorkoutCompletionManifest":
        workout_owners: dict[tuple[str, str, int, str], str] = {}
        for local_activity_id, match in self.matches.items():
            if match.local_activity_id != local_activity_id:
                raise ValueError("completion manifest key must match local activity ID")
            identity = match.workout_identity
            prior_activity = workout_owners.setdefault(
                (
                    identity.plan_id,
                    identity.plan_revision_id,
                    identity.week_number,
                    identity.local_workout_id,
                ),
                local_activity_id,
            )
            if prior_activity != local_activity_id:
                raise ValueError("a local workout cannot match multiple activities")
        return self
