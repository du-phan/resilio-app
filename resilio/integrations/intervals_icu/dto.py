"""Narrow validated DTOs for operations Resilio actually uses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class ExternalDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ActivityFilterDTO(ExternalDTO):
    """Intervals activity/workout forwarding filter."""

    field_id: str
    code: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    not_: bool = Field(default=False, validation_alias="not")


class AthleteDTO(ExternalDTO):
    id: str
    name: Optional[str] = None
    timezone: Optional[str] = None
    garmin_upload_filters: list[ActivityFilterDTO] = Field(
        default_factory=list,
        validation_alias="icu_garmin_upload_filters",
    )
    garmin_upload_workouts: Optional[bool] = Field(
        default=None,
        validation_alias="icu_garmin_upload_workouts",
    )
    wahoo_upload_workouts: Optional[bool] = None

    @field_validator("garmin_upload_filters", mode="before")
    @classmethod
    def null_upload_filters_are_empty(cls, value):
        return [] if value is None else value


class ConnectionsDTO(ExternalDTO):
    id: str
    garmin_training_connected: bool = False
    wahoo_connected: bool = False


class SportSettingsDTO(ExternalDTO):
    id: int
    types: list[str] = Field(default_factory=list)
    ftp: Optional[int] = Field(default=None, gt=0)
    lthr: Optional[int] = Field(default=None, gt=0, le=260)
    max_hr: Optional[int] = Field(default=None, gt=0, le=260)
    threshold_pace: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    pace_zones: list[float] = Field(default_factory=list)
    default_workout_time: Optional[str] = None
    updated: Optional[datetime] = None

    @field_validator("types", "pace_zones", mode="before")
    @classmethod
    def null_lists_are_empty(cls, value):
        return [] if value is None else value


class HiddenActivityDTO(ExternalDTO):
    id: str
    start_date_local: str
    source: Optional[str] = None
    note: str = Field(validation_alias="_note")


class IntervalDTO(ExternalDTO):
    id: int
    start_time: int = Field(ge=0)
    elapsed_time: int = Field(gt=0)
    moving_time: Optional[int] = Field(default=None, ge=0)
    distance: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    label: Optional[str] = None
    average_speed: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_speed: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    average_heartrate: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )
    max_heartrate: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )
    total_elevation_gain: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    average_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    weighted_average_watts: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    average_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def moving_not_longer_than_elapsed(self) -> "IntervalDTO":
        if self.moving_time is not None and self.moving_time > self.elapsed_time:
            raise ValueError("interval moving_time cannot exceed elapsed_time")
        return self


class ActivityDTO(ExternalDTO):
    id: str
    type: str
    name: str
    start_date: datetime
    start_date_local: datetime
    elapsed_time: int = Field(gt=0)
    moving_time: int = Field(ge=0)
    timezone: Optional[str] = None
    sub_type: Optional[str] = None
    description: Optional[str] = None
    distance: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    total_elevation_gain: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    average_heartrate: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )
    max_heartrate: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )
    has_heartrate: Optional[bool] = None
    average_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_average_watts: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    p_max: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_weighted_avg_watts: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    icu_training_load: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    perceived_exertion: Optional[float] = Field(
        default=None, ge=0, le=10, allow_inf_nan=False
    )
    icu_rpe: Optional[int] = Field(default=None, ge=1, le=10)
    device_name: Optional[str] = None
    external_id: Optional[str] = None
    file_type: Optional[str] = None
    source: Optional[str] = None
    created: Optional[datetime] = None
    icu_sync_date: Optional[datetime] = None
    paired_event_id: Optional[int] = None
    icu_intervals: list[IntervalDTO] = Field(default_factory=list)

    @field_validator("start_date")
    @classmethod
    def utc_start_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_date must include a UTC offset")
        return value

    @field_validator("start_date_local")
    @classmethod
    def local_start_must_be_aware(cls, value: datetime) -> datetime:
        # The live API returns local wall time without an offset. The mapper
        # attaches the athlete/activity timezone before this enters the domain.
        return value

    @field_validator("icu_intervals", mode="before")
    @classmethod
    def null_intervals_are_empty(cls, value):
        return [] if value is None else value

    @model_validator(mode="after")
    def moving_not_longer_than_elapsed(self) -> "ActivityDTO":
        if self.moving_time > self.elapsed_time:
            raise ValueError("moving_time cannot exceed elapsed_time")
        return self


class EventDTO(ExternalDTO):
    id: int
    uid: Optional[str] = None
    external_id: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    start_date_local: Optional[str] = None
    target: Optional[str] = None
    workout_doc: Optional[dict[str, Any]] = None
    updated: Optional[datetime] = None


class EventWriteDTO(BaseModel):
    uid: str
    external_id: str
    category: str = "WORKOUT"
    type: str
    name: str
    description: str
    start_date_local: str
    target: Literal["AUTO", "POWER", "HR", "PACE"] = "AUTO"

    model_config = ConfigDict(extra="forbid")


class ManualActivityWriteDTO(BaseModel):
    """Strict write contract for Resilio-owned historical bouldering."""

    external_id: str = Field(
        pattern=r"^resilio:v1:historical-activity:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
    )
    type: Literal["RockClimbing"] = "RockClimbing"
    name: str = Field(min_length=1, max_length=500)
    start_date: datetime
    start_date_local: datetime
    timezone: str = Field(min_length=1, max_length=120)
    elapsed_time: int = Field(gt=0, le=2_678_400)
    moving_time: int = Field(ge=0, le=2_678_400)
    description: Optional[str] = None
    icu_rpe: Optional[int] = Field(default=None, ge=1, le=10)
    distance: Optional[float] = Field(
        default=None,
        gt=0,
        le=10_000_000,
        allow_inf_nan=False,
    )
    total_elevation_gain: Optional[float] = Field(
        default=None,
        gt=0,
        le=100_000,
        allow_inf_nan=False,
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("start_date")
    @classmethod
    def start_date_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_date must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("start_date_local")
    @classmethod
    def local_start_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_date_local must be timezone-aware")
        return value

    @field_serializer("start_date_local", when_used="json")
    def serialize_local_wall_time(self, value: datetime) -> str:
        """Intervals accepts local wall time without an embedded UTC offset."""
        return value.replace(tzinfo=None).isoformat()

    @model_validator(mode="after")
    def moving_not_longer_than_elapsed(self) -> "ManualActivityWriteDTO":
        if self.moving_time > self.elapsed_time:
            raise ValueError("moving_time cannot exceed elapsed_time")
        if self.start_date_local.astimezone(timezone.utc) != self.start_date:
            raise ValueError("local and UTC start times must describe one instant")
        return self
