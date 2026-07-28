"""Provider-neutral activity, analysis, and training-load contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class SportType(str, Enum):
    """Canonical sport types used by every downstream calculation."""

    RUN = "run"
    TRAIL_RUN = "trail_run"
    TREADMILL_RUN = "treadmill_run"
    TRACK_RUN = "track_run"
    CYCLE = "cycle"
    SWIM = "swim"
    CLIMB = "climb"
    STRENGTH = "strength"
    CROSSFIT = "crossfit"
    YOGA = "yoga"
    HIKE = "hike"
    WALK = "walk"
    OTHER = "other"


class SurfaceType(str, Enum):
    ROAD = "road"
    TRAIL = "trail"
    TRACK = "track"
    TREADMILL = "treadmill"
    GRASS = "grass"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DataQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TREADMILL = "treadmill"


class ActivityStatus(str, Enum):
    ACTIVE = "active"
    EXTERNAL_DELETED = "external_deleted"


class ActivityOriginKind(str, Enum):
    INTERVALS_ICU = "intervals_icu"
    HISTORICAL_IMPORT = "historical_import"


class RecordingProvider(str, Enum):
    GARMIN = "garmin"
    WAHOO = "wahoo"
    MANUAL = "manual"
    UPLOAD = "upload"
    OTHER = "other"
    UNKNOWN = "unknown"


class SegmentOriginKind(str, Enum):
    HISTORICAL_SEGMENT = "historical_segment"
    INTERVALS_ICU_INTERVAL = "intervals_icu_interval"


class SchemaDescriptor(BaseModel):
    name: str = Field(default="resilio.activity", frozen=True)
    version: int = Field(default=2, frozen=True)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_activity_v2(self) -> "SchemaDescriptor":
        if self.name != "resilio.activity" or self.version != 2:
            raise ValueError("activity archive requires _schema name=resilio.activity version=2")
        return self


class ActivityOccurrence(BaseModel):
    local_date: date
    start_time_utc: Optional[datetime] = None
    start_time_local: Optional[datetime] = None
    timezone: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("start_time_utc")
    @classmethod
    def utc_must_be_aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("start_time_utc must be timezone-aware")
            if value.utcoffset().total_seconds() != 0:
                value = value.astimezone(timezone.utc)
        return value

    @field_validator("start_time_local")
    @classmethod
    def local_time_must_be_aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("start_time_local must be timezone-aware")
        return value

    @model_validator(mode="after")
    def local_date_matches_timestamp(self) -> "ActivityOccurrence":
        if self.start_time_local is not None and self.start_time_local.date() != self.local_date:
            raise ValueError("local_date must match start_time_local")
        return self


class ActivityDuration(BaseModel):
    elapsed_seconds: int = Field(gt=0, le=2_678_400)
    moving_seconds: int = Field(ge=0, le=2_678_400)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def moving_not_longer_than_elapsed(self) -> "ActivityDuration":
        if self.moving_seconds > self.elapsed_seconds:
            raise ValueError("moving_seconds cannot exceed elapsed_seconds")
        return self


class HeartRateMeasurements(BaseModel):
    average_beats_per_minute: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )
    maximum_beats_per_minute: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def average_not_above_maximum(self) -> "HeartRateMeasurements":
        if (
            self.average_beats_per_minute is not None
            and self.maximum_beats_per_minute is not None
            and self.average_beats_per_minute > self.maximum_beats_per_minute
        ):
            raise ValueError("average heart rate cannot exceed maximum heart rate")
        return self


class PowerMeasurements(BaseModel):
    average_watts: Optional[float] = Field(default=None, ge=0, le=3_000, allow_inf_nan=False)
    maximum_watts: Optional[float] = Field(default=None, ge=0, le=5_000, allow_inf_nan=False)
    weighted_average_watts: Optional[float] = Field(
        default=None, ge=0, le=3_000, allow_inf_nan=False
    )

    model_config = ConfigDict(extra="forbid")


class CadenceMeasurements(BaseModel):
    average_revolutions_per_minute: Optional[float] = Field(
        default=None, ge=0, le=300, allow_inf_nan=False
    )
    maximum_revolutions_per_minute: Optional[float] = Field(
        default=None, ge=0, le=400, allow_inf_nan=False
    )

    model_config = ConfigDict(extra="forbid")


class ActivityNotes(BaseModel):
    description: Optional[str] = None
    private_note: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class PerceivedEffortSource(str, Enum):
    ATHLETE = "athlete"
    HISTORICAL_RELATIVE_EFFORT = "historical_relative_effort"
    INFERRED = "inferred"


class PerceivedEffort(BaseModel):
    value: int = Field(ge=1, le=10)
    source: PerceivedEffortSource

    model_config = ConfigDict(extra="forbid")


class ActivityDevice(BaseModel):
    name: Optional[str] = None
    gear_external_id: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ActivityClassification(BaseModel):
    surface: SurfaceType = SurfaceType.UNKNOWN
    data_quality: DataQuality = DataQuality.MEDIUM
    has_gps_data: bool = False

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ActivitySegment(BaseModel):
    index: int = Field(ge=1)
    name: Optional[str] = None
    origin_kind: SegmentOriginKind
    elapsed_seconds: int = Field(gt=0, le=2_678_400)
    moving_seconds: int = Field(ge=0, le=2_678_400)
    distance_meters: NonNegativeFloat = 0.0
    start_time_utc: Optional[datetime] = None
    start_time_local: Optional[datetime] = None
    average_speed_meters_per_second: Optional[float] = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    maximum_speed_meters_per_second: Optional[float] = Field(
        default=None, ge=0, le=150, allow_inf_nan=False
    )
    heart_rate: Optional[HeartRateMeasurements] = None
    elevation_gain_meters: Optional[NonNegativeFloat] = None
    power: Optional[PowerMeasurements] = None
    cadence: Optional[CadenceMeasurements] = None

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def validate_duration(self) -> "ActivitySegment":
        if self.moving_seconds > self.elapsed_seconds:
            raise ValueError("segment moving_seconds cannot exceed elapsed_seconds")
        return self

    # Provider-neutral computed views used by lap/segment presentation.
    @property
    def lap_index(self) -> int:
        return self.index

    @property
    def elapsed_time_seconds(self) -> int:
        return self.elapsed_seconds

    @property
    def moving_time_seconds(self) -> int:
        return self.moving_seconds

    @property
    def average_speed_mps(self) -> Optional[float]:
        return self.average_speed_meters_per_second

    @property
    def max_speed_mps(self) -> Optional[float]:
        return self.maximum_speed_meters_per_second

    @property
    def pace_per_km(self) -> Optional[str]:
        speed = self.average_speed_meters_per_second
        if not speed:
            return None
        seconds = int(round(1000 / speed))
        return f"{seconds // 60}:{seconds % 60:02d}"

    @property
    def average_hr(self) -> Optional[float]:
        return self.heart_rate.average_beats_per_minute if self.heart_rate else None

    @property
    def max_hr(self) -> Optional[float]:
        return self.heart_rate.maximum_beats_per_minute if self.heart_rate else None

    @property
    def total_elevation_gain_meters(self) -> Optional[float]:
        return self.elevation_gain_meters

    @property
    def average_watts(self) -> Optional[float]:
        return self.power.average_watts if self.power else None

    @property
    def max_watts(self) -> Optional[float]:
        return self.power.maximum_watts if self.power else None

    @property
    def average_cadence(self) -> Optional[float]:
        return self.cadence.average_revolutions_per_minute if self.cadence else None


class ActivityOrigin(BaseModel):
    kind: ActivityOriginKind
    recording_provider: RecordingProvider = RecordingProvider.UNKNOWN
    intervals_icu_activity_id: Optional[str] = None
    upstream_external_id: Optional[str] = None
    original_file_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def external_origin_requires_id(self) -> "ActivityOrigin":
        if self.kind == ActivityOriginKind.INTERVALS_ICU and not self.intervals_icu_activity_id:
            raise ValueError("intervals_icu origin requires intervals_icu_activity_id")
        return self


class ActivityAudit(BaseModel):
    imported_at_utc: datetime
    external_created_at_utc: Optional[datetime] = None
    external_sync_at_utc: Optional[datetime] = None
    external_fingerprint_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("imported_at_utc", "external_created_at_utc", "external_sync_at_utc")
    @classmethod
    def audit_timestamps_are_aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("audit timestamps must be timezone-aware")
        return value.astimezone(timezone.utc) if value is not None else None


class SessionType(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    QUALITY = "quality"
    RACE = "race"


class LoadCalculation(BaseModel):
    """Provider-neutral load result; only base SI duration is persisted."""

    activity_id: str
    duration_seconds: int = Field(gt=0, le=2_678_400)
    estimated_rpe: int = Field(ge=1, le=10)
    sport: str
    surface: Optional[str] = None
    base_effort_au: NonNegativeFloat
    systemic_multiplier: float = Field(ge=0, le=3, allow_inf_nan=False)
    lower_body_multiplier: float = Field(ge=0, le=3, allow_inf_nan=False)
    adjustments: list[str] = Field(default_factory=list)
    systemic_load_au: NonNegativeFloat
    lower_body_load_au: NonNegativeFloat
    session_type: SessionType
    algorithm_version: str = "resilio-load-v1"

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="before")
    @classmethod
    def accept_computation_views(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "duration_seconds" not in data and "duration_minutes" in data:
            data["duration_seconds"] = int(data.pop("duration_minutes")) * 60
        if "sport" not in data and "sport_type" in data:
            data["sport"] = data.pop("sport_type")
        if "surface" not in data and "surface_type" in data:
            data["surface"] = data.pop("surface_type")
        if "adjustments" not in data and "multiplier_adjustments" in data:
            data["adjustments"] = data.pop("multiplier_adjustments")
        return data

    @property
    def duration_minutes(self) -> int:
        return self.duration_seconds // 60

    @property
    def sport_type(self) -> str:
        return self.sport

    @property
    def surface_type(self) -> Optional[str]:
        return self.surface

    @property
    def multiplier_adjustments(self) -> list[str]:
        return self.adjustments


class CanonicalActivity(BaseModel):
    """The only persisted completed-activity schema."""

    schema_info: SchemaDescriptor = Field(
        default_factory=SchemaDescriptor,
        validation_alias="_schema",
        serialization_alias="_schema",
    )
    local_activity_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    status: ActivityStatus = ActivityStatus.ACTIVE
    sport: SportType
    source_sport_type: str = Field(min_length=1, max_length=120)
    source_sport_subtype: Optional[str] = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=500)
    occurrence: ActivityOccurrence
    duration: ActivityDuration
    distance_meters: Optional[float] = Field(
        default=None, ge=0, le=10_000_000, allow_inf_nan=False
    )
    elevation_gain_meters: Optional[float] = Field(
        default=None, ge=0, le=100_000, allow_inf_nan=False
    )
    heart_rate: Optional[HeartRateMeasurements] = None
    power: Optional[PowerMeasurements] = None
    cadence: Optional[CadenceMeasurements] = None
    notes: ActivityNotes = Field(default_factory=ActivityNotes)
    perceived_effort: Optional[PerceivedEffort] = None
    device: ActivityDevice = Field(default_factory=ActivityDevice)
    classification: ActivityClassification = Field(default_factory=ActivityClassification)
    segments: list[ActivitySegment] = Field(default_factory=list)
    origin: ActivityOrigin
    audit: ActivityAudit
    calculated_load: Optional[LoadCalculation] = None

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_non_v2_persisted_records(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "schema_metadata" in value:
            raise ValueError("legacy activity schema is not readable as CanonicalActivity v2")
        schema = value.get("_schema")
        if schema is not None:
            if not isinstance(schema, dict) or schema.get("name") != "resilio.activity":
                raise ValueError("invalid activity _schema name")
            if schema.get("version") != 2:
                raise ValueError("activity archive requires schema version 2")
        return value

    @model_validator(mode="after")
    def validate_external_identity(self) -> "CanonicalActivity":
        if self.origin.kind == ActivityOriginKind.INTERVALS_ICU:
            if not self.local_activity_id.startswith("act_i_"):
                raise ValueError("new Intervals.icu activities require an act_i_ local ID")
        if self.status == ActivityStatus.EXTERNAL_DELETED:
            if self.origin.intervals_icu_activity_id is None:
                raise ValueError("only externally linked activities can be external_deleted")
        return self

    # Provider-neutral computed views for calculations/presentation. These are
    # intentionally not Pydantic computed fields, so they are never persisted.
    @property
    def id(self) -> str:
        return self.local_activity_id

    @property
    def sport_type(self) -> str:
        return str(self.sport)

    @property
    def sub_type(self) -> Optional[str]:
        return self.source_sport_subtype

    @property
    def date(self) -> date:
        return self.occurrence.local_date

    @property
    def day_of_week(self) -> int:
        return self.date.weekday()

    @property
    def day_of_week_name(self) -> str:
        return self.date.strftime("%A")

    @property
    def start_time(self) -> Optional[datetime]:
        return self.occurrence.start_time_local or self.occurrence.start_time_utc

    @property
    def duration_seconds(self) -> int:
        return self.duration.elapsed_seconds

    @property
    def duration_minutes(self) -> int:
        return self.duration.elapsed_seconds // 60

    @property
    def distance_km(self) -> Optional[float]:
        return self.distance_meters / 1000 if self.distance_meters is not None else None

    @property
    def elevation_gain_m(self) -> Optional[float]:
        return self.elevation_gain_meters

    @property
    def average_hr(self) -> Optional[float]:
        return self.heart_rate.average_beats_per_minute if self.heart_rate else None

    @property
    def max_hr(self) -> Optional[float]:
        return self.heart_rate.maximum_beats_per_minute if self.heart_rate else None

    @property
    def has_hr_data(self) -> bool:
        return self.heart_rate is not None and (
            self.heart_rate.average_beats_per_minute is not None
            or self.heart_rate.maximum_beats_per_minute is not None
        )

    @property
    def description(self) -> Optional[str]:
        return self.notes.description

    @property
    def private_note(self) -> Optional[str]:
        return self.notes.private_note

    @property
    def perceived_exertion(self) -> Optional[int]:
        return self.perceived_effort.value if self.perceived_effort else None

    @property
    def surface_type(self) -> str:
        return str(self.classification.surface)

    @property
    def data_quality(self) -> str:
        return str(self.classification.data_quality)

    @property
    def has_gps_data(self) -> bool:
        return self.classification.has_gps_data

    @property
    def laps(self) -> list[ActivitySegment]:
        return self.segments

    @property
    def has_laps(self) -> bool:
        return bool(self.segments)

    @property
    def gear_id(self) -> Optional[str]:
        return self.device.gear_external_id

    @property
    def created_at(self) -> datetime:
        return self.audit.external_created_at_utc or self.audit.imported_at_utc

    @property
    def updated_at(self) -> datetime:
        return self.audit.external_sync_at_utc or self.audit.imported_at_utc

    @property
    def synced_at(self) -> Optional[datetime]:
        return self.audit.external_sync_at_utc

    @property
    def calculated(self) -> Optional[LoadCalculation]:
        return self.calculated_load


class RPESource(str, Enum):
    USER_INPUT = "user_input"
    HR_BASED = "hr_based"
    PACE_BASED = "pace_based"
    TEXT_BASED = "text_based"
    HISTORICAL_RELATIVE_EFFORT = "historical_relative_effort"
    DURATION_HEURISTIC = "duration_heuristic"


class FlagSeverity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class BodyPart(str, Enum):
    KNEE = "knee"
    ANKLE = "ankle"
    CALF = "calf"
    SHIN = "shin"
    HIP = "hip"
    HAMSTRING = "hamstring"
    QUAD = "quad"
    ACHILLES = "achilles"
    FOOT = "foot"
    BACK = "back"
    SHOULDER = "shoulder"
    GENERAL = "general"


class RPEEstimate(BaseModel):
    value: int = Field(ge=1, le=10)
    source: RPESource
    confidence: str
    reasoning: str


class RPEConflict(BaseModel):
    estimates: list[RPEEstimate]
    spread: int
    resolved_value: int
    resolution_method: str


class TreadmillDetection(BaseModel):
    is_treadmill: bool
    confidence: str
    signals: list[str] = Field(default_factory=list)


class InjuryFlag(BaseModel):
    body_part: BodyPart
    severity: FlagSeverity
    keywords_found: list[str] = Field(default_factory=list)
    source_text: str
    requires_rest: bool


class IllnessFlag(BaseModel):
    severity: FlagSeverity
    symptoms: list[str] = Field(default_factory=list)
    keywords_found: list[str] = Field(default_factory=list)
    source_text: str
    rest_days_recommended: int


class ContextualFactors(BaseModel):
    is_fasted: bool = False
    heat_mentioned: bool = False
    cold_mentioned: bool = False
    altitude_mentioned: bool = False
    travel_mentioned: bool = False
    after_work: bool = False
    early_morning: bool = False


class AnalysisResult(BaseModel):
    activity_id: str
    rpe_estimates: list[RPEEstimate] = Field(default_factory=list)
    treadmill_detection: TreadmillDetection
    analyzed_at: datetime
    notes_present: bool


class SportMultipliers(BaseModel):
    sport: str
    systemic: float
    lower_body: float
    description: str


class MultiplierAdjustment(BaseModel):
    reason: str
    channel: str
    original: float
    adjusted: float
