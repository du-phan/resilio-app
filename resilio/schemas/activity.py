"""Provider-neutral completed-activity contracts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from resilio.schemas.activity_analysis import (
    ActivityAnalysisThresholds as ActivityAnalysisThresholds,
)
from resilio.schemas.activity_analysis import (
    ActivityZoneTime as ActivityZoneTime,
)
from resilio.schemas.activity_analysis import (
    HeartRateRecoveryObservation as HeartRateRecoveryObservation,
)
from resilio.schemas.activity_analysis import (
    NativeActivityAnalysis as NativeActivityAnalysis,
)
from resilio.schemas.activity_analysis import (
    NativeAnalysisApplicability as NativeAnalysisApplicability,
)
from resilio.schemas.activity_analysis import (
    NativeDecouplingObservation as NativeDecouplingObservation,
)
from resilio.schemas.activity_analysis import (
    NativePolarizationObservation as NativePolarizationObservation,
)
from resilio.schemas.activity_analysis import (
    ZoneMeasurementMethod as ZoneMeasurementMethod,
)
from resilio.schemas.activity_analysis import (
    ZoneTimeDistribution as ZoneTimeDistribution,
)
from resilio.schemas.activity_feedback import ActivityFeedback as ActivityFeedback
from resilio.schemas.activity_feedback import (
    ActivityFeelObservation as ActivityFeelObservation,
)
from resilio.schemas.activity_feedback import (
    SubjectiveEffortProvenance as SubjectiveEffortProvenance,
)
from resilio.schemas.activity_feedback import (
    SubjectiveSessionEffort as SubjectiveSessionEffort,
)
from resilio.schemas.activity_measurements import (
    ActivityDuration as ActivityDuration,
)
from resilio.schemas.activity_measurements import (
    ActivityExecutionSummary as ActivityExecutionSummary,
)
from resilio.schemas.activity_measurements import (
    CadenceMeasurements as CadenceMeasurements,
)
from resilio.schemas.activity_measurements import (
    HeartRateMeasurements as HeartRateMeasurements,
)
from resilio.schemas.activity_measurements import PowerMeasurements as PowerMeasurements

NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
ACTIVITY_CANONICAL_MAPPING_VERSION: Literal[9] = 9


class SportType(str, Enum):
    """Canonical sport types used by every downstream calculation."""

    RUN = "run"
    TRAIL_RUN = "trail_run"
    TREADMILL_RUN = "treadmill_run"
    TRACK_RUN = "track_run"
    CYCLE = "cycle"
    SWIM = "swim"
    ROW = "row"
    PADDLE = "paddle"
    SKI = "ski"
    SKATE = "skate"
    WATER_SPORT = "water_sport"
    SNOW_SPORT = "snow_sport"
    TEAM_SPORT = "team_sport"
    RACQUET_SPORT = "racquet_sport"
    CARDIO_MACHINE = "cardio_machine"
    WHEELCHAIR = "wheelchair"
    GOLF = "golf"
    CLIMB = "climb"
    STRENGTH = "strength"
    CROSSFIT = "crossfit"
    HIGH_INTENSITY_INTERVAL_TRAINING = "high_intensity_interval_training"
    YOGA = "yoga"
    PILATES = "pilates"
    SKATEBOARD = "skateboard"
    TRANSITION = "transition"
    HIKE = "hike"
    WALK = "walk"
    OTHER = "other"


RUNNING_SPORT_TYPES = frozenset(
    {
        SportType.RUN,
        SportType.TRAIL_RUN,
        SportType.TREADMILL_RUN,
        SportType.TRACK_RUN,
    }
)
RUNNING_SPORT_VALUES = frozenset(sport.value for sport in RUNNING_SPORT_TYPES)


def is_running_sport(value: SportType | str) -> bool:
    """Return whether a canonical sport is one of the running variants."""
    try:
        return SportType(value) in RUNNING_SPORT_TYPES
    except ValueError:
        return False


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
    version: int = Field(default=5, frozen=True)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_activity_v5(self) -> "SchemaDescriptor":
        if self.name != "resilio.activity" or self.version != 5:
            raise ValueError("activity archive requires _schema name=resilio.activity version=5")
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
            offset = value.utcoffset()
            if value.tzinfo is None or offset is None:
                raise ValueError("start_time_utc must be timezone-aware")
            if offset.total_seconds() != 0:
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


class AerobicLoadCalculationMethod(str, Enum):
    POWER = "power"
    HEART_RATE = "heart_rate"
    PACE = "pace"
    MANUAL = "manual"
    PROVIDER_UNKNOWN = "provider_unknown"


class AerobicLoad(BaseModel):
    """Provider-computed aerobic training load; values are load points."""

    aerobic_load_points: NonNegativeFloat
    calculation_method: AerobicLoadCalculationMethod
    power_load_points: Optional[NonNegativeFloat] = None
    heart_rate_load_points: Optional[NonNegativeFloat] = None
    pace_load_points: Optional[NonNegativeFloat] = None
    relative_intensity_percent: Optional[float] = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    heart_rate_load_type: Optional[str] = None
    pace_load_type: Optional[str] = None
    provider_edited: bool = False
    source: str = Field(default="intervals_icu", frozen=True)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class DataCompleteness(BaseModel):
    has_location_stream: bool = False
    has_heart_rate_data: bool = False
    has_power_data: bool = False
    has_cadence_data: bool = False
    has_interval_data: bool = False
    has_native_aerobic_load: bool = False
    has_zone_time_data: bool = False
    has_native_activity_analysis: bool = False

    model_config = ConfigDict(extra="forbid")


class IntervalKind(str, Enum):
    WORK = "work"
    RECOVERY = "recovery"
    OTHER = "other"


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
    moving_seconds: Optional[int] = Field(default=None, ge=0, le=2_678_400)
    distance_meters: Optional[NonNegativeFloat] = None
    start_time_utc: Optional[datetime] = None
    start_time_local: Optional[datetime] = None
    source_start_index: Optional[int] = Field(default=None, ge=0)
    source_end_index_exclusive: Optional[int] = Field(default=None, ge=1)
    end_offset_seconds: Optional[int] = Field(default=None, ge=0)
    minimum_speed_meters_per_second: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    average_speed_meters_per_second: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    maximum_speed_meters_per_second: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    heart_rate: Optional[HeartRateMeasurements] = None
    elevation_gain_meters: Optional[NonNegativeFloat] = None
    power: Optional[PowerMeasurements] = None
    cadence: Optional[CadenceMeasurements] = None
    average_gradient_percent: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    minimum_altitude_meters: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    maximum_altitude_meters: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    average_stride_meters: Optional[NonNegativeFloat] = None
    provider_zone_index: Optional[int] = Field(default=None, ge=0)
    work_joules: Optional[NonNegativeFloat] = None
    work_above_ftp_joules: Optional[NonNegativeFloat] = None
    interval_kind: IntervalKind = IntervalKind.OTHER
    relative_intensity_percent: Optional[float] = Field(
        default=None,
        ge=0,
        le=1_000,
        allow_inf_nan=False,
    )
    aerobic_load_points: Optional[NonNegativeFloat] = None
    decoupling: Optional[NativeDecouplingObservation] = None

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def validate_duration(self) -> "ActivitySegment":
        if self.moving_seconds is not None and self.moving_seconds > self.elapsed_seconds:
            raise ValueError("segment moving_seconds cannot exceed elapsed_seconds")
        if (
            self.source_start_index is not None
            and self.source_end_index_exclusive is not None
            and self.source_end_index_exclusive <= self.source_start_index
        ):
            raise ValueError("segment source index range must be ascending")
        if (
            self.minimum_altitude_meters is not None
            and self.maximum_altitude_meters is not None
            and self.minimum_altitude_meters > self.maximum_altitude_meters
        ):
            raise ValueError("segment minimum altitude cannot exceed maximum altitude")
        return self


class ActivityOrigin(BaseModel):
    kind: ActivityOriginKind
    recording_provider: RecordingProvider = RecordingProvider.UNKNOWN
    source_recording_provider: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.:-]{1,120}$",
    )
    intervals_icu_activity_id: Optional[str] = None
    upstream_external_id: Optional[str] = None
    original_file_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")

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
    provider_snapshot_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    performance_evidence_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    canonical_mapping_version: Optional[Literal[9]] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("imported_at_utc", "external_created_at_utc", "external_sync_at_utc")
    @classmethod
    def audit_timestamps_are_aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("audit timestamps must be timezone-aware")
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def mapping_version_matches_fingerprints(self) -> "ActivityAudit":
        fingerprints_present = (
            self.provider_snapshot_sha256 is not None
            and self.performance_evidence_sha256 is not None
        )
        if fingerprints_present != (self.canonical_mapping_version is not None):
            raise ValueError(
                "provider/performance fingerprints and canonical mapping version must "
                "be present together"
            )
        if (self.provider_snapshot_sha256 is None) != (self.performance_evidence_sha256 is None):
            raise ValueError("provider and performance fingerprints must be present together")
        return self


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
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    elevation_gain_meters: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    heart_rate: Optional[HeartRateMeasurements] = None
    power: Optional[PowerMeasurements] = None
    cadence: Optional[CadenceMeasurements] = None
    execution_summary: ActivityExecutionSummary = Field(default_factory=ActivityExecutionSummary)
    feedback: ActivityFeedback = Field(default_factory=ActivityFeedback)
    aerobic_load: Optional[AerobicLoad] = None
    native_analysis: Optional[NativeActivityAnalysis] = None
    native_analysis_applicability: Optional[NativeAnalysisApplicability] = None
    analysis_thresholds: Optional[ActivityAnalysisThresholds] = None
    zone_time_distributions: list[ZoneTimeDistribution] = Field(default_factory=list)
    data_completeness: DataCompleteness = Field(default_factory=DataCompleteness)
    device: ActivityDevice = Field(default_factory=ActivityDevice)
    classification: ActivityClassification = Field(default_factory=ActivityClassification)
    segments: list[ActivitySegment] = Field(default_factory=list)
    origin: ActivityOrigin
    audit: ActivityAudit

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_non_v5_persisted_records(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "schema_metadata" in value:
            raise ValueError("legacy activity schema is not readable as CanonicalActivity v5")
        schema = value.get("_schema")
        if schema is not None:
            if not isinstance(schema, dict) or schema.get("name") != "resilio.activity":
                raise ValueError("invalid activity _schema name")
            if schema.get("version") != 5:
                raise ValueError("activity archive requires schema version 5")
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

    @model_validator(mode="after")
    def completeness_matches_canonical_facts(self) -> "CanonicalActivity":
        required_true = {
            "has_heart_rate_data": self.heart_rate is not None,
            "has_power_data": self.power is not None,
            "has_cadence_data": self.cadence is not None,
            "has_interval_data": bool(self.segments),
        }
        mismatches = [
            name
            for name, fact_is_present in required_true.items()
            if fact_is_present and not getattr(self.data_completeness, name)
        ]
        exact = {
            "has_native_aerobic_load": self.aerobic_load is not None,
            "has_zone_time_data": bool(self.zone_time_distributions),
            "has_native_activity_analysis": self.native_analysis is not None,
        }
        mismatches.extend(
            name
            for name, expected_value in exact.items()
            if getattr(self.data_completeness, name) != expected_value
        )
        if mismatches:
            raise ValueError(
                "data completeness disagrees with canonical facts: " + ", ".join(mismatches)
            )
        if self.data_completeness.has_location_stream != self.classification.has_gps_data:
            raise ValueError("location-stream completeness must match GPS classification")
        return self
