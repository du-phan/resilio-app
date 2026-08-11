"""Strict removed contracts used only by the one-shot fulfillment cutover."""

from datetime import date, datetime, time, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.plan_history import PlanWorkoutIdentity
from resilio.schemas.publication import (
    ConfirmedPublicationDriftTarget,
    GarminForwardingStatus,
    HistoricalLegacyPublicationDriftResolution,
    HistoricalLegacyWorkoutPublication,
    PendingWorkoutPublication,
    PublicationPushError,
    PublishedWorkout,
    RetiredPendingWorkoutPublication,
    RetiredWorkoutPublication,
)


class LegacyPublishedWorkout(BaseModel):
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
    approved_start_time_local: time | None = None
    provider_start_date_local: str
    garmin_forwarding_status: GarminForwardingStatus
    provider_push_errors: list[PublicationPushError] = Field(default_factory=list)
    provider_computed_aerobic_load_points: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_relative_intensity_percent: float | None = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    provider_fitness_load_points: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    provider_fatigue_load_points: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    verified_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class LegacyPendingWorkoutPublication(BaseModel):
    workout_identity: PlanWorkoutIdentity
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: Literal["run"]
    occurrence_date: date
    approved_start_time_local: time | None = None
    provider_start_date_local: str
    prepared_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class LegacyPublicationDriftResolution(BaseModel):
    plan_id: str
    plan_revision_id: str
    week_number: int = Field(ge=1)
    strategy: Literal["restore_local"] = "restore_local"
    athlete_confirmation_reference: str = Field(min_length=1)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class LegacyPublicationManifest(BaseModel):
    schema_version: Literal[6] = 6
    workouts: dict[str, LegacyPublishedWorkout] = Field(default_factory=dict)
    pending: dict[str, LegacyPendingWorkoutPublication] = Field(default_factory=dict)
    drift_resolutions: list[LegacyPublicationDriftResolution] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ownership_identities_are_unique(self) -> "LegacyPublicationManifest":
        event_owners: dict[int, str] = {}
        identity_owners: dict[tuple[str, str], str] = {}
        for local_id, published_record in self.workouts.items():
            if published_record.workout_identity.local_workout_id != local_id:
                raise ValueError("publication manifest key must match local workout ID")
            if event_owners.setdefault(published_record.event_id, local_id) != local_id:
                raise ValueError("publication manifest event IDs must be unique")
            for field_name, value in (
                ("requested_uid", published_record.requested_uid),
                ("uid", published_record.uid),
                ("external_id", published_record.external_id),
            ):
                if identity_owners.setdefault((field_name, value), local_id) != local_id:
                    raise ValueError("publication ownership identities must be unique")
        for local_id, pending_record in self.pending.items():
            if pending_record.workout_identity.local_workout_id != local_id:
                raise ValueError("pending publication key must match local workout ID")
            published = self.workouts.get(local_id)
            if (
                published is not None
                and published.workout_identity != pending_record.workout_identity
            ):
                raise ValueError("pending publication lineage must match publication lineage")
            for field_name, value in (
                ("uid", pending_record.uid),
                ("external_id", pending_record.external_id),
            ):
                if identity_owners.setdefault((field_name, value), local_id) != local_id:
                    raise ValueError("publication ownership identities must be unique")
        return self


class LegacyV7PublicationDriftResolution(BaseModel):
    """Exact v7 drift authority, including the removed retirement strategy."""

    plan_id: str
    plan_revision_id: str
    week_number: int = Field(ge=1)
    strategy: Literal["restore_local", "retire_fulfilled"]
    confirmed_targets: list[ConfirmedPublicationDriftTarget]
    athlete_confirmation_reference: str = Field(min_length=1)
    confirmed_at_utc: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("confirmed_at_utc")
    @classmethod
    def confirmation_time_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("legacy drift confirmation time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def confirmed_workout_ids_are_unique(
        self,
    ) -> "LegacyV7PublicationDriftResolution":
        if not self.confirmed_targets:
            raise ValueError("legacy drift resolution requires exact confirmed targets")
        workout_ids = [target.local_workout_id for target in self.confirmed_targets]
        if len(workout_ids) != len(set(workout_ids)):
            raise ValueError("legacy confirmed workout IDs must be unique")
        return self


class LegacyV7PublicationManifest(BaseModel):
    """Strict publication v7 contract consumed only by the v2 cutover."""

    schema_version: Literal[7] = 7
    workouts: dict[str, PublishedWorkout] = Field(default_factory=dict)
    pending: dict[str, PendingWorkoutPublication] = Field(default_factory=dict)
    retired: dict[str, RetiredWorkoutPublication] = Field(default_factory=dict)
    retired_pending: dict[str, RetiredPendingWorkoutPublication] = Field(default_factory=dict)
    retirement_history: list[RetiredWorkoutPublication] = Field(default_factory=list)
    pending_retirement_history: list[RetiredPendingWorkoutPublication] = Field(
        default_factory=list
    )
    historical_legacy_workouts: dict[
        str, HistoricalLegacyWorkoutPublication
    ] = Field(default_factory=dict)
    drift_resolutions: list[LegacyV7PublicationDriftResolution] = Field(
        default_factory=list
    )
    historical_legacy_drift_resolutions: list[
        HistoricalLegacyPublicationDriftResolution
    ] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def keys_match_workout_identities(self) -> "LegacyV7PublicationManifest":
        event_owners: dict[int, str] = {}
        identity_owners: dict[tuple[str, str], str] = {}
        for local_id, record in self.workouts.items():
            if record.workout_identity.local_workout_id != local_id:
                raise ValueError("publication manifest key must match local workout ID")
            if event_owners.setdefault(record.event_id, local_id) != local_id:
                raise ValueError("publication manifest event IDs must be unique")
            for field_name, value in (
                ("requested_uid", record.requested_uid),
                ("uid", record.uid),
                ("external_id", record.external_id),
            ):
                if identity_owners.setdefault((field_name, value), local_id) != local_id:
                    raise ValueError("publication ownership identities must be unique")
        for local_id, pending_record in self.pending.items():
            if pending_record.workout_identity.local_workout_id != local_id:
                raise ValueError("pending publication key must match local workout ID")
            published_record = self.workouts.get(local_id)
            if (
                published_record is not None
                and published_record.workout_identity != pending_record.workout_identity
            ):
                raise ValueError("pending publication lineage must match publication lineage")
            for field_name, value in (
                ("uid", pending_record.uid),
                ("external_id", pending_record.external_id),
            ):
                if identity_owners.setdefault((field_name, value), local_id) != local_id:
                    raise ValueError("publication ownership identities must be unique")
        for local_id, retired_event_record in self.retired.items():
            if retired_event_record.publication.workout_identity.local_workout_id != local_id:
                raise ValueError("retired publication key must match local workout ID")
            if (
                local_id in self.workouts or local_id in self.pending
            ) and retired_event_record.reopened_at_utc is None:
                raise ValueError("retired publication cannot remain active or pending")
        for local_id, retired_pending_record in self.retired_pending.items():
            if (
                retired_pending_record.pending_publication.workout_identity.local_workout_id
                != local_id
            ):
                raise ValueError("retired pending key must match local workout ID")
            if (
                local_id in self.workouts or local_id in self.pending
            ) and retired_pending_record.reopened_at_utc is None:
                raise ValueError("retired pending publication cannot remain active")
        for local_id, historical_record in self.historical_legacy_workouts.items():
            if historical_record.workout_identity.local_workout_id != local_id:
                raise ValueError("historical publication key must match local workout ID")
            if (
                local_id in self.workouts
                or local_id in self.pending
                or local_id in self.retired
                or local_id in self.retired_pending
            ):
                raise ValueError("historical publication cannot remain active or retired")
            if event_owners.setdefault(historical_record.event_id, local_id) != local_id:
                raise ValueError("publication manifest event IDs must be unique")
        return self


class LegacyWorkoutCompletionMatch(BaseModel):
    local_activity_id: str
    workout_identity: PlanWorkoutIdentity
    match_method: Literal["paired_event_id"]
    matched_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class LegacyWorkoutCompletionManifest(BaseModel):
    schema_version: Literal[3] = 3
    matches: dict[str, LegacyWorkoutCompletionMatch] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def completion_identities_are_unique(self) -> "LegacyWorkoutCompletionManifest":
        workout_owners: dict[tuple[str, str, int, str], str] = {}
        for local_activity_id, match in self.matches.items():
            if match.local_activity_id != local_activity_id:
                raise ValueError("completion manifest key must match local activity ID")
            identity = match.workout_identity
            identity_key = (
                identity.plan_id,
                identity.plan_revision_id,
                identity.week_number,
                identity.local_workout_id,
            )
            if workout_owners.setdefault(identity_key, local_activity_id) != local_activity_id:
                raise ValueError("a local workout cannot match multiple activities")
        return self
