"""Narrow validated DTOs for operations Resilio actually uses."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from resilio.integrations.intervals_icu.wellness_dto import WellnessDTO as WellnessDTO
from resilio.integrations.intervals_icu.wellness_dto import (
    WellnessSportInfoDTO as WellnessSportInfoDTO,
)


class ExternalDTO(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


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
    def null_upload_filters_are_empty(cls, value: Any) -> Any:
        return [] if value is None else value


class ConnectionsDTO(ExternalDTO):
    id: str
    garmin_training_connected: bool = False
    wahoo_connected: bool = False


class PushErrorDTO(ExternalDTO):
    """One downstream workout-forwarding error reported by Intervals.icu."""

    service: str = Field(min_length=1)
    message: str = Field(min_length=1)
    date: Optional[datetime] = None


class SportSettingsDTO(ExternalDTO):
    id: int
    types: list[str] = Field(default_factory=list)
    ftp: Optional[int] = Field(default=None, gt=0)
    indoor_ftp: Optional[int] = Field(default=None, gt=0)
    power_zones: list[int] = Field(default_factory=list)
    power_zone_names: list[str] = Field(default_factory=list)
    lthr: Optional[int] = Field(default=None, gt=0, le=260)
    max_hr: Optional[int] = Field(default=None, gt=0, le=260)
    hr_zones: list[int] = Field(default_factory=list)
    hr_zone_names: list[str] = Field(default_factory=list)
    hr_load_type: Optional[str] = None
    threshold_speed_meters_per_second: Optional[float] = Field(
        default=None,
        validation_alias="threshold_pace",
        gt=0,
        allow_inf_nan=False,
    )
    pace_display_unit: Optional[str] = Field(
        default=None,
        validation_alias="pace_units",
    )
    pace_zones: list[float] = Field(default_factory=list)
    pace_zone_names: list[str] = Field(default_factory=list)
    pace_load_type: Optional[str] = None
    load_order: Optional[str] = None
    tiz_order: Optional[str] = None
    workout_order: Optional[str] = None
    default_workout_time: Optional[str] = None
    updated: Optional[datetime] = None

    @field_validator(
        "types",
        "power_zones",
        "power_zone_names",
        "hr_zones",
        "hr_zone_names",
        "pace_zones",
        "pace_zone_names",
        mode="before",
    )
    @classmethod
    def null_lists_are_empty(cls, value: Any) -> Any:
        return [] if value is None else value


class HiddenActivityDTO(ExternalDTO):
    id: str
    start_date_local: datetime
    source: Optional[str] = None
    note: str = Field(validation_alias="_note")


class ActivitySummaryDTO(ExternalDTO):
    """Identity and ordering fields required from the activity-list operation."""

    id: str
    type: str
    start_date_local: str


ZoneDurationSeconds = Annotated[int, Field(ge=0, le=2_678_400)]


class ZoneTimeDTO(ExternalDTO):
    """One Intervals.icu power-zone duration keyed by provider zone ID."""

    id: str = Field(min_length=1)
    duration_seconds: int = Field(
        validation_alias="secs",
        ge=0,
        le=2_147_483_647,
    )


class IntervalDTO(ExternalDTO):
    id: int
    type: Optional[str] = None
    start_time: int = Field(ge=0)
    end_time: Optional[int] = Field(default=None, ge=0)
    start_index: Optional[int] = Field(default=None, ge=0)
    end_index: Optional[int] = Field(default=None, ge=0)
    elapsed_time: int = Field(gt=0)
    moving_time: Optional[int] = Field(default=None, ge=0)
    distance: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    label: Optional[str] = None
    average_speed: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    min_speed: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_speed: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    average_heartrate: Optional[float] = Field(default=None, ge=20, le=260, allow_inf_nan=False)
    min_heartrate: Optional[float] = Field(default=None, ge=20, le=260, allow_inf_nan=False)
    max_heartrate: Optional[float] = Field(default=None, ge=20, le=260, allow_inf_nan=False)
    total_elevation_gain: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    average_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    weighted_average_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    average_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    min_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    intensity: Optional[float] = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    training_load: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    decoupling: Optional[float] = Field(
        default=None,
        ge=-100,
        le=1_000,
        allow_inf_nan=False,
    )
    average_gradient: Optional[float] = Field(default=None, allow_inf_nan=False)
    min_altitude: Optional[float] = Field(default=None, allow_inf_nan=False)
    max_altitude: Optional[float] = Field(default=None, allow_inf_nan=False)
    average_stride: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    zone: Optional[int] = Field(default=None, ge=0)
    joules: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    joules_above_ftp: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def moving_not_longer_than_elapsed(self) -> "IntervalDTO":
        if self.moving_time is not None and self.moving_time > self.elapsed_time:
            raise ValueError("interval moving_time cannot exceed elapsed_time")
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError("interval end_time cannot precede start_time")
        if self.start_index is not None and self.end_index is not None:
            is_no_stream_sentinel = self.start_index == 0 and self.end_index == 0
            if not is_no_stream_sentinel and self.end_index <= self.start_index:
                raise ValueError("interval end_index must be greater than start_index")
        return self


class HeartRateRecoveryDTO(ExternalDTO):
    """Intervals.icu HRRecovery payload; absent properties remain unknown."""

    start_index: Optional[int] = Field(default=None, ge=0)
    end_index: Optional[int] = Field(default=None, ge=0)
    start_time: Optional[int] = Field(default=None, ge=0)
    end_time: Optional[int] = Field(default=None, ge=0)
    start_bpm: Optional[int] = None
    end_bpm: Optional[int] = None
    average_watts: Optional[int] = None
    hrr: Optional[int] = None


class ActivityDTO(ExternalDTO):
    # Native pairing verifies that no provider-returned field except the pair
    # pointer changes across a write, including fields introduced by Intervals.
    model_config = ConfigDict(extra="allow", populate_by_name=True)

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
    total_elevation_gain: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    average_speed: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_speed: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    gap: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    average_stride: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    calories: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    carbs_ingested: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    carbs_used: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    compliance: Optional[float] = Field(default=None, allow_inf_nan=False)
    average_temp: Optional[float] = Field(default=None, allow_inf_nan=False)
    icu_weight: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    average_heartrate: Optional[float] = Field(default=None, ge=20, le=260, allow_inf_nan=False)
    max_heartrate: Optional[float] = Field(default=None, ge=20, le=260, allow_inf_nan=False)
    has_heartrate: Optional[bool] = None
    average_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    max_cadence: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_average_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    p_max: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_weighted_avg_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_training_load: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_training_load_edited: bool = False
    power_load: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    hr_load: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    pace_load: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    hr_load_type: Optional[str] = None
    pace_load_type: Optional[str] = None
    load_order: Optional[str] = None
    tiz_order: Optional[str] = None
    icu_intensity: Optional[float] = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    session_rpe: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    ftp: Optional[int] = Field(
        default=None,
        validation_alias="icu_ftp",
        gt=0,
    )
    lthr: Optional[int] = Field(default=None, gt=0, le=260)
    max_hr: Optional[int] = Field(
        default=None,
        validation_alias="athlete_max_hr",
        gt=0,
        le=260,
    )
    threshold_speed_meters_per_second: Optional[float] = Field(
        default=None,
        validation_alias="threshold_pace",
        gt=0,
        allow_inf_nan=False,
    )
    pace_display_unit: Optional[str] = Field(
        default=None,
        validation_alias="pace_units",
    )
    icu_power_zones: list[int] = Field(default_factory=list)
    power_zone_names: list[str] = Field(default_factory=list)
    hr_zones: list[int] = Field(
        default_factory=list,
        validation_alias="icu_hr_zones",
    )
    hr_zone_names: list[str] = Field(default_factory=list)
    pace_zones: list[float] = Field(default_factory=list)
    pace_zone_names: list[str] = Field(default_factory=list)
    icu_zone_times: list[ZoneTimeDTO] = Field(default_factory=list)
    icu_hr_zone_times: list[ZoneDurationSeconds] = Field(default_factory=list)
    pace_zone_times: list[ZoneDurationSeconds] = Field(default_factory=list)
    gap_zone_times: list[ZoneDurationSeconds] = Field(default_factory=list)
    use_gap_zone_times: Optional[bool] = None
    stream_types: list[str] = Field(default_factory=list)
    decoupling: Optional[float] = Field(
        default=None,
        ge=-100,
        le=1_000,
        allow_inf_nan=False,
    )
    polarization_index: Optional[float] = Field(default=None, allow_inf_nan=False)
    trimp: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_hrr: Optional[HeartRateRecoveryDTO] = None
    icu_ignore_time: Optional[bool] = None
    icu_ignore_power: Optional[bool] = None
    icu_ignore_hr: Optional[bool] = None
    ignore_velocity: Optional[bool] = None
    ignore_pace: Optional[bool] = None
    perceived_exertion: Optional[float] = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    icu_rpe: Optional[int] = Field(default=None, ge=1, le=10)
    feel: Optional[int] = Field(default=None, ge=1, le=5)
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

    @field_validator(
        "icu_intervals",
        "icu_power_zones",
        "power_zone_names",
        "hr_zones",
        "hr_zone_names",
        "pace_zones",
        "pace_zone_names",
        "icu_zone_times",
        "icu_hr_zone_times",
        "pace_zone_times",
        "gap_zone_times",
        "stream_types",
        mode="before",
    )
    @classmethod
    def null_collections_are_empty(cls, value: Any) -> Any:
        return [] if value is None else value

    @model_validator(mode="after")
    def moving_not_longer_than_elapsed(self) -> "ActivityDTO":
        if self.moving_time > self.elapsed_time:
            raise ValueError("moving_time cannot exceed elapsed_time")
        return self

    @model_validator(mode="after")
    def power_zone_ids_are_unique(self) -> "ActivityDTO":
        provider_zone_ids = [zone.id for zone in self.icu_zone_times]
        if len(provider_zone_ids) != len(set(provider_zone_ids)):
            raise ValueError("icu_zone_times contains duplicate provider zone IDs")
        return self


class ActivityPairingWriteDTO(BaseModel):
    """The complete payload Resilio is allowed to write on an activity."""

    paired_event_id: Optional[int] = Field(gt=0)

    model_config = ConfigDict(extra="forbid")


class WorkoutStepTargetDTO(ExternalDTO):
    """One provider workout-step target in its native units."""

    units: str
    value: Optional[float] = Field(default=None, allow_inf_nan=False)
    start: Optional[float] = Field(default=None, allow_inf_nan=False)
    end: Optional[float] = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def has_value_or_range(self) -> "WorkoutStepTargetDTO":
        if self.value is None and (self.start is None or self.end is None):
            raise ValueError("workout target requires a value or complete range")
        return self


class WorkoutDocumentStepDTO(ExternalDTO):
    """Narrow recursive projection of one parsed Intervals workout step."""

    text: Optional[str] = None
    intensity: Optional[str] = None
    warmup: bool = False
    cooldown: bool = False
    ramp: bool = False
    press_lap: bool = Field(
        default=False,
        validation_alias=AliasChoices("press_lap", "lap"),
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        validation_alias="duration",
        gt=0,
        allow_inf_nan=False,
    )
    distance_meters: Optional[float] = Field(
        default=None,
        validation_alias="distance",
        gt=0,
        allow_inf_nan=False,
    )
    repetitions: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("reps", "repetitions"),
        ge=2,
        le=100,
    )
    steps: list["WorkoutDocumentStepDTO"] = Field(default_factory=list)
    pace: Optional[WorkoutStepTargetDTO] = None
    heart_rate: Optional[WorkoutStepTargetDTO] = Field(
        default=None,
        validation_alias=AliasChoices("heartrate", "hr"),
    )
    power: Optional[WorkoutStepTargetDTO] = None
    cadence: Optional[WorkoutStepTargetDTO] = None


class WorkoutDocumentDTO(ExternalDTO):
    """Parsed provider workout document used for semantic verification."""

    steps: list[WorkoutDocumentStepDTO] = Field(default_factory=list)


WorkoutDocumentStepDTO.model_rebuild()


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
    workout_doc: Optional[WorkoutDocumentDTO] = None
    push_errors: list[PushErrorDTO] = Field(default_factory=list)
    icu_training_load: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    icu_intensity: Optional[float] = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    icu_ctl: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    icu_atl: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    updated: Optional[datetime] = None

    @field_validator("push_errors", mode="before")
    @classmethod
    def null_push_errors_are_empty(cls, value: Any) -> Any:
        return [] if value is None else value


class HeartRateCurveDTO(ExternalDTO):
    """Duration-to-heart-rate curve returned for one exact activity."""

    id: str
    secs: list[int] = Field(default_factory=list, max_length=1_000)
    values: list[int] = Field(default_factory=list, max_length=1_000)

    @model_validator(mode="after")
    def parallel_arrays_have_equal_length(self) -> "HeartRateCurveDTO":
        if len(self.secs) != len(self.values):
            raise ValueError(
                "HR curve duration and value arrays must have the same number of items"
            )
        if any(duration_seconds <= 0 for duration_seconds in self.secs):
            raise ValueError("HR curve durations must be positive seconds")
        if any(
            later_duration_seconds <= earlier_duration_seconds
            for earlier_duration_seconds, later_duration_seconds in zip(
                self.secs,
                self.secs[1:],
            )
        ):
            raise ValueError("HR curve durations must be strictly increasing")
        if any(heart_rate_bpm < 20 or heart_rate_bpm > 260 for heart_rate_bpm in self.values):
            raise ValueError("HR curve heart rates must be between 20 and 260 bpm")
        return self


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
