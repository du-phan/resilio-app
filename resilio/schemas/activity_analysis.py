"""Provider-native activity analysis and time-in-zone contracts."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class NativePolarizationObservation(BaseModel):
    value: float = Field(allow_inf_nan=False)
    aggregation_scope: Literal["activity"] = "activity"
    primary_zone_measurement_method: Optional[str] = None
    analysis_settings_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    evidence_status: Literal[
        "linked_to_primary_zone_evidence",
        "unlinked",
    ]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def linkage_fields_are_coherent(
        self,
    ) -> "NativePolarizationObservation":
        linked = self.evidence_status == "linked_to_primary_zone_evidence"
        has_link = (
            self.primary_zone_measurement_method is not None
            and self.analysis_settings_sha256 is not None
        )
        if linked != has_link:
            raise ValueError(
                "linked polarization requires a primary zone method and " "analysis settings hash"
            )
        return self


class NativeDecouplingObservation(BaseModel):
    value_percent: float = Field(allow_inf_nan=False)
    aggregation_scope: Literal["activity", "provider_interval"]
    coupling_basis: Literal[
        "power_to_heart_rate",
        "pace_to_heart_rate",
        "provider_unknown",
    ] = "provider_unknown"

    model_config = ConfigDict(extra="forbid")


class HeartRateRecoveryObservation(BaseModel):
    """Provider-selected heart-rate recovery interval and raw observation."""

    start_sample_index: Optional[int] = Field(default=None, ge=0)
    end_sample_index: Optional[int] = Field(default=None, ge=0)
    start_offset_seconds: Optional[int] = Field(default=None, ge=0)
    end_offset_seconds: Optional[int] = Field(default=None, ge=0)
    start_heart_rate_bpm: Optional[int] = None
    end_heart_rate_bpm: Optional[int] = None
    average_power_watts: Optional[int] = None
    heart_rate_recovery_bpm: Optional[int] = None
    source: Literal["intervals_icu"] = "intervals_icu"

    model_config = ConfigDict(extra="forbid")


class NativeActivityAnalysis(BaseModel):
    """Provider-computed activity analysis that Resilio must not reconstruct."""

    aerobic_decoupling: Optional[NativeDecouplingObservation] = None
    polarization: Optional[NativePolarizationObservation] = None
    trimp_load_points: Optional[NonNegativeFloat] = None
    heart_rate_recovery: Optional[HeartRateRecoveryObservation] = None
    source: Literal["intervals_icu"] = "intervals_icu"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def at_least_one_metric_is_present(self) -> "NativeActivityAnalysis":
        if (
            self.aerobic_decoupling is None
            and self.polarization is None
            and self.trimp_load_points is None
            and self.heart_rate_recovery is None
        ):
            raise ValueError("native activity analysis requires at least one metric")
        return self


class NativeAnalysisApplicability(BaseModel):
    """Provider flags controlling which activity facts enter its analysis."""

    exclude_time: Optional[bool] = None
    exclude_power: Optional[bool] = None
    exclude_heart_rate: Optional[bool] = None
    exclude_velocity: Optional[bool] = None
    exclude_pace: Optional[bool] = None
    source: Literal["intervals_icu"] = "intervals_icu"

    model_config = ConfigDict(extra="forbid")


class ActivityAnalysisThresholds(BaseModel):
    functional_threshold_power_watts: Optional[int] = Field(default=None, gt=0)
    lactate_threshold_hr_bpm: Optional[int] = Field(
        default=None,
        gt=0,
        le=260,
    )
    maximum_hr_bpm: Optional[int] = Field(default=None, gt=0, le=260)
    threshold_speed_meters_per_second: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    pace_display_unit: Optional[str] = None
    power_zone_upper_bounds_watts: list[int] = Field(default_factory=list)
    heart_rate_zone_upper_bounds_bpm: list[int] = Field(default_factory=list)
    pace_zone_upper_bounds_percent: list[float] = Field(default_factory=list)
    power_zone_names: list[str] = Field(default_factory=list)
    heart_rate_zone_names: list[str] = Field(default_factory=list)
    pace_zone_names: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ZoneMeasurementMethod(str, Enum):
    POWER = "power"
    HEART_RATE = "heart_rate"
    PACE = "pace"
    GRADE_ADJUSTED_PACE = "grade_adjusted_pace"


class ActivityZoneTime(BaseModel):
    zone_index: Optional[int] = Field(default=None, ge=1)
    provider_zone_id: Optional[str] = Field(default=None, min_length=1)
    name: Optional[str] = None
    duration_seconds: int = Field(ge=0)
    lower_bound: Optional[float] = Field(default=None, allow_inf_nan=False)
    upper_bound: Optional[float] = Field(default=None, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def bucket_identity_is_present(self) -> "ActivityZoneTime":
        if self.zone_index is None and self.provider_zone_id is None:
            raise ValueError("zone bucket requires an ordinal index or provider zone ID")
        return self


class ZoneTimeDistribution(BaseModel):
    measurement_method: ZoneMeasurementMethod
    zones: list[ActivityZoneTime]
    covered_duration_seconds: int = Field(ge=0)
    analysis_source_moving_duration_seconds: int = Field(
        ge=0,
        le=2_678_400,
    )
    moving_time_coverage_percent: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    is_primary_time_in_zones_method: bool = False
    measurement_unit: Literal["watts", "beats_per_minute", "percent"]
    analysis_settings_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    @model_validator(mode="after")
    def coverage_matches_source_duration(self) -> "ZoneTimeDistribution":
        if self.measurement_method == ZoneMeasurementMethod.POWER and any(
            zone.provider_zone_id is None for zone in self.zones
        ):
            raise ValueError("power zone buckets require provider zone IDs")
        zone_sum_seconds = sum(zone.duration_seconds for zone in self.zones)
        if self.covered_duration_seconds != zone_sum_seconds:
            raise ValueError("covered zone duration must equal the sum of zone buckets")
        source_seconds = self.analysis_source_moving_duration_seconds
        if source_seconds == 0:
            if self.moving_time_coverage_percent is not None:
                raise ValueError(
                    "zone coverage percent is undefined when source moving " "duration is zero"
                )
            return self
        expected_percent = self.covered_duration_seconds / source_seconds * 100
        if (
            self.moving_time_coverage_percent is None
            or abs(self.moving_time_coverage_percent - expected_percent) > 1e-9
        ):
            raise ValueError(
                "zone coverage percent must equal covered duration divided by "
                "analysis source moving duration"
            )
        return self
