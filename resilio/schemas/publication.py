"""Owned external workout publication state."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublishedWorkout(BaseModel):
    local_workout_id: str
    event_id: int
    requested_uid: str
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: str
    occurrence_date: date
    start_date_local: str
    verified_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class PendingWorkoutPublication(BaseModel):
    """Durable local intent written before any remote event mutation."""

    local_workout_id: str
    uid: str
    external_id: str
    publication_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rendered_workout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport_settings_version_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sport: str
    occurrence_date: date
    start_date_local: str
    prepared_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class PublicationManifest(BaseModel):
    schema_version: int = 1
    workouts: dict[str, PublishedWorkout] = Field(default_factory=dict)
    pending: dict[str, PendingWorkoutPublication] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ownership_identities_are_unique(self) -> "PublicationManifest":
        event_owners: dict[int, str] = {}
        identity_owners: dict[tuple[str, str], str] = {}
        for local_id, record in self.workouts.items():
            if record.local_workout_id != local_id:
                raise ValueError(
                    "publication manifest key must match local workout ID"
                )
            prior_event_owner = event_owners.setdefault(
                record.event_id,
                local_id,
            )
            if prior_event_owner != local_id:
                raise ValueError(
                    "publication manifest event IDs must be unique"
                )
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
                    raise ValueError(
                        "publication manifest ownership identities must be unique"
                    )
        for local_id, record in self.pending.items():
            if record.local_workout_id != local_id:
                raise ValueError(
                    "pending publication key must match local workout ID"
                )
            for field_name, value in (
                ("uid", record.uid),
                ("external_id", record.external_id),
            ):
                prior_owner = identity_owners.setdefault(
                    (field_name, value),
                    local_id,
                )
                if prior_owner != local_id:
                    raise ValueError(
                        "publication manifest ownership identities must be unique"
                    )
        return self


class PublicationResult(BaseModel):
    action: str
    local_workout_id: str
    event_id: Optional[int] = None
    uid: str
    external_id: str
    fingerprint_sha256: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class PlanPublicationItem(BaseModel):
    local_workout_id: str
    occurrence_date: date
    status: Literal[
        "created",
        "updated",
        "noop",
        "recovered",
        "skipped_rest",
        "skipped_unstructured",
        "error",
    ]
    event_id: Optional[int] = None
    error_type: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class PlanPublicationReport(BaseModel):
    from_date: date
    workouts_considered: int = 0
    eligible_workouts: int = 0
    partial: bool = False
    items: list[PlanPublicationItem] = Field(default_factory=list)
    stale_manifest_workout_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class WorkoutCompletionMatch(BaseModel):
    local_activity_id: str
    local_workout_id: str
    match_method: str = Field(pattern=r"^paired_event_id$")
    matched_at_utc: datetime

    model_config = ConfigDict(extra="forbid")


class WorkoutCompletionManifest(BaseModel):
    schema_version: int = 1
    matches: dict[str, WorkoutCompletionMatch] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def completion_identities_are_unique(
        self,
    ) -> "WorkoutCompletionManifest":
        workout_owners: dict[str, str] = {}
        for local_activity_id, match in self.matches.items():
            if match.local_activity_id != local_activity_id:
                raise ValueError(
                    "completion manifest key must match local activity ID"
                )
            prior_activity = workout_owners.setdefault(
                match.local_workout_id,
                local_activity_id,
            )
            if prior_activity != local_activity_id:
                raise ValueError(
                    "a local workout cannot match multiple activities"
                )
        return self
