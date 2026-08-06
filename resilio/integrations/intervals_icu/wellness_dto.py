"""Validated Intervals.icu wellness transport contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WellnessExternalDTO(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class WellnessSportInfoDTO(WellnessExternalDTO):
    type: str
    estimated_ftp_watts: Optional[float] = Field(
        default=None,
        validation_alias="eftp",
        gt=0,
        allow_inf_nan=False,
    )
    estimated_w_prime_joules: Optional[float] = Field(
        default=None,
        validation_alias="wPrime",
        ge=0,
        allow_inf_nan=False,
    )
    estimated_pmax_watts: Optional[float] = Field(
        default=None,
        validation_alias="pMax",
        ge=0,
        allow_inf_nan=False,
    )


class WellnessDTO(WellnessExternalDTO):
    """Provider wellness data, including fields deliberately excluded downstream."""

    id: date
    ctl: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    atl: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    ramp_rate: Optional[float] = Field(
        default=None,
        validation_alias="rampRate",
        allow_inf_nan=False,
    )
    ctl_load: Optional[float] = Field(
        default=None,
        validation_alias="ctlLoad",
        ge=0,
        allow_inf_nan=False,
    )
    atl_load: Optional[float] = Field(
        default=None,
        validation_alias="atlLoad",
        ge=0,
        allow_inf_nan=False,
    )
    sport_info: list[WellnessSportInfoDTO] = Field(
        default_factory=list,
        validation_alias="sportInfo",
    )
    updated: Optional[datetime] = None
    weight: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    resting_hr: Optional[int] = Field(
        default=None,
        validation_alias="restingHR",
        ge=20,
        le=260,
    )
    hrv: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    hrv_sdnn: Optional[float] = Field(
        default=None,
        validation_alias="hrvSDNN",
        ge=0,
        allow_inf_nan=False,
    )
    menstrual_phase: Optional[
        Literal["PERIOD", "FOLLICULAR", "OVULATING", "LUTEAL", "NONE"]
    ] = Field(default=None, validation_alias="menstrualPhase")
    menstrual_phase_predicted: Optional[
        Literal["PERIOD", "FOLLICULAR", "OVULATING", "LUTEAL", "NONE"]
    ] = Field(default=None, validation_alias="menstrualPhasePredicted")
    kilocalories_consumed: Optional[int] = Field(
        default=None,
        validation_alias="kcalConsumed",
        ge=0,
    )
    sleep_seconds: Optional[int] = Field(
        default=None,
        validation_alias="sleepSecs",
        ge=0,
        le=172_800,
    )
    sleep_score: Optional[float] = Field(
        default=None,
        validation_alias="sleepScore",
        ge=0,
        allow_inf_nan=False,
    )
    sleep_quality: Optional[int] = Field(
        default=None,
        validation_alias="sleepQuality",
        ge=1,
        le=4,
    )
    average_sleeping_hr: Optional[float] = Field(
        default=None,
        validation_alias="avgSleepingHR",
        ge=20,
        le=260,
        allow_inf_nan=False,
    )
    soreness: Optional[int] = Field(default=None, ge=0, le=4)
    fatigue: Optional[int] = Field(default=None, ge=0, le=4)
    stress: Optional[int] = Field(default=None, ge=0, le=4)
    mood: Optional[int] = Field(default=None, ge=1, le=4)
    motivation: Optional[int] = Field(default=None, ge=1, le=4)
    injury: Optional[int] = Field(default=None, ge=1, le=4)
    hydration: Optional[int] = Field(default=None, ge=1, le=4)
    hydration_volume: Optional[float] = Field(
        default=None,
        validation_alias="hydrationVolume",
        ge=0,
        allow_inf_nan=False,
    )
    readiness: Optional[float] = Field(default=None, allow_inf_nan=False)
    oxygen_saturation_percent: Optional[float] = Field(
        default=None,
        validation_alias="spO2",
        ge=0,
        le=100,
        allow_inf_nan=False,
    )
    systolic_blood_pressure_mmhg: Optional[int] = Field(
        default=None,
        validation_alias="systolic",
        gt=0,
    )
    diastolic_blood_pressure_mmhg: Optional[int] = Field(
        default=None,
        validation_alias="diastolic",
        gt=0,
    )
    baevsky_stress_index: Optional[float] = Field(
        default=None,
        validation_alias="baevskySI",
        ge=0,
        allow_inf_nan=False,
    )
    blood_glucose_mmol_per_liter: Optional[float] = Field(
        default=None,
        validation_alias="bloodGlucose",
        ge=0,
        allow_inf_nan=False,
    )
    lactate_mmol_per_liter: Optional[float] = Field(
        default=None,
        validation_alias="lactate",
        ge=0,
        allow_inf_nan=False,
    )
    body_fat_percent: Optional[float] = Field(
        default=None,
        validation_alias="bodyFat",
        ge=0,
        le=100,
        allow_inf_nan=False,
    )
    abdomen_centimeters: Optional[float] = Field(
        default=None,
        validation_alias="abdomen",
        ge=0,
        allow_inf_nan=False,
    )
    vo2max: Optional[float] = Field(default=None, gt=0, le=100, allow_inf_nan=False)
    comments: Optional[str] = None
    steps: Optional[int] = Field(default=None, ge=0)
    respiration: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    carbohydrates_grams: Optional[float] = Field(
        default=None,
        validation_alias="carbohydrates",
        ge=0,
        allow_inf_nan=False,
    )
    protein_grams: Optional[float] = Field(
        default=None,
        validation_alias="protein",
        ge=0,
        allow_inf_nan=False,
    )
    total_fat_grams: Optional[float] = Field(
        default=None,
        validation_alias="fatTotal",
        ge=0,
        allow_inf_nan=False,
    )
    locked: Optional[bool] = None
    temporary_weight: bool = Field(default=False, validation_alias="tempWeight")
    temporary_resting_hr: bool = Field(
        default=False,
        validation_alias="tempRestingHR",
    )

    @field_validator("sport_info", mode="before")
    @classmethod
    def null_sport_info_is_empty(cls, value: Any) -> Any:
        return [] if value is None else value
