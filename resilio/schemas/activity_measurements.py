"""Reusable physical measurements for canonical completed activities."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]


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
    minimum_beats_per_minute: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )
    average_beats_per_minute: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )
    maximum_beats_per_minute: Optional[float] = Field(
        default=None, ge=20, le=260, allow_inf_nan=False
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def values_are_ordered(self) -> "HeartRateMeasurements":
        minimum = self.minimum_beats_per_minute
        average = self.average_beats_per_minute
        maximum = self.maximum_beats_per_minute
        if minimum is not None and average is not None and minimum > average:
            raise ValueError("minimum heart rate cannot exceed average heart rate")
        if average is not None and maximum is not None and average > maximum:
            raise ValueError("average heart rate cannot exceed maximum heart rate")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("minimum heart rate cannot exceed maximum heart rate")
        return self


class PowerMeasurements(BaseModel):
    average_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    maximum_watts: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    weighted_average_watts: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    model_config = ConfigDict(extra="forbid")


class CadenceMeasurements(BaseModel):
    """Provider cadence values whose running/cycling basis is not guaranteed."""

    minimum_cadence_per_minute: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    average_cadence_per_minute: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    maximum_cadence_per_minute: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    source_basis: Literal["provider_unspecified"] = "provider_unspecified"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def values_are_ordered(self) -> "CadenceMeasurements":
        minimum = self.minimum_cadence_per_minute
        average = self.average_cadence_per_minute
        maximum = self.maximum_cadence_per_minute
        if minimum is not None and average is not None and minimum > average:
            raise ValueError("minimum cadence cannot exceed average cadence")
        if average is not None and maximum is not None and average > maximum:
            raise ValueError("average cadence cannot exceed maximum cadence")
        return self


class ActivityExecutionSummary(BaseModel):
    """Provider activity summary in explicit native units."""

    average_speed_meters_per_second: Optional[NonNegativeFloat] = None
    maximum_speed_meters_per_second: Optional[NonNegativeFloat] = None
    gradient_adjusted_speed_meters_per_second: Optional[NonNegativeFloat] = None
    average_stride_meters: Optional[NonNegativeFloat] = None
    calories_kilocalories: Optional[NonNegativeFloat] = None
    carbohydrates_ingested_grams: Optional[NonNegativeFloat] = None
    provider_estimated_carbohydrates_used_grams: Optional[NonNegativeFloat] = None
    provider_compliance_percent: Optional[float] = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    average_temperature_celsius: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
    )
    analysis_weight_kilograms: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )

    model_config = ConfigDict(extra="forbid")
