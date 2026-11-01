"""Athlete-confirmed calendar removal, independent of prescription history."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.publication import PublishedWorkout


class MissedWorkoutCalendarRemoval(BaseModel):
    athlete_id: str = Field(min_length=1)
    publication: PublishedWorkout
    observed_remote_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    athlete_confirmation_reference: str = Field(min_length=10, max_length=1000)
    requested_at_utc: datetime
    completed_at_utc: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("requested_at_utc", "completed_at_utc")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Calendar removal timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def completion_follows_request(self) -> "MissedWorkoutCalendarRemoval":
        if self.completed_at_utc is not None and self.completed_at_utc < self.requested_at_utc:
            raise ValueError("Calendar removal completion cannot predate its request")
        return self


class CalendarRemovalManifest(BaseModel):
    schema_version: Literal[1] = 1
    removals: dict[str, MissedWorkoutCalendarRemoval] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def record_keys_match_workout_identity(self) -> "CalendarRemovalManifest":
        for workout_id, record in self.removals.items():
            if record.publication.workout_identity.local_workout_id != workout_id:
                raise ValueError("Calendar removal key must match its qualified workout identity")
        return self
