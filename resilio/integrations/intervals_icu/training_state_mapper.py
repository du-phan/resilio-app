"""Pure Intervals wellness and sport-settings domain mapping."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from resilio.integrations.intervals_icu.dto import SportSettingsDTO, WellnessDTO
from resilio.schemas.training_state import (
    LoadMeasurementMethod,
    SportPerformanceEstimate,
    SportSettings,
    SportSettingsSnapshot,
    WellnessDay,
)

_METHODS = {
    "POWER": LoadMeasurementMethod.POWER,
    "HR": LoadMeasurementMethod.HEART_RATE,
    "PACE": LoadMeasurementMethod.PACE,
}


def _priority(value: str | None) -> list[LoadMeasurementMethod]:
    if not value:
        return []
    result: list[LoadMeasurementMethod] = []
    for token in value.split("_"):
        method = _METHODS.get(token.upper())
        if method is not None and method not in result:
            result.append(method)
    return result


def _wellness_without_fingerprint(source: WellnessDTO) -> WellnessDay:
    return WellnessDay(
        local_date=source.id,
        provider_updated_at_utc=source.updated,
        fitness_load_points=source.ctl,
        fatigue_load_points=source.atl,
        ramp_load_points_per_week=source.ramp_rate,
        fitness_contribution_load_points=source.ctl_load,
        fatigue_contribution_load_points=source.atl_load,
        resting_hr_bpm=source.resting_hr,
        hrv_rmssd_ms=source.hrv,
        hrv_sdnn_ms=source.hrv_sdnn,
        sleep_duration_seconds=source.sleep_seconds,
        sleep_score=source.sleep_score,
        sleep_quality=source.sleep_quality,
        average_sleeping_hr_bpm=source.average_sleeping_hr,
        soreness=source.soreness,
        subjective_fatigue=source.fatigue,
        stress=source.stress,
        mood=source.mood,
        motivation=source.motivation,
        injury=source.injury,
        hydration=source.hydration,
        hydration_volume_liters=source.hydration_volume,
        provider_readiness_value=source.readiness,
        vo2_max_ml_per_kg_per_min=source.vo2max,
        step_count=source.steps,
        weight_kilograms=source.weight,
        weight_is_temporary=source.temporary_weight,
        oxygen_saturation_percent=source.oxygen_saturation_percent,
        provider_respiration_value=source.respiration,
        provider_baevsky_stress_index=source.baevsky_stress_index,
        athlete_comments=source.comments,
        sport_performance_estimates=sorted(
            (
                SportPerformanceEstimate(
                    source_sport_type=item.type,
                    estimated_ftp_watts=item.estimated_ftp_watts,
                    estimated_w_prime_joules=item.estimated_w_prime_joules,
                    estimated_pmax_watts=item.estimated_pmax_watts,
                )
                for item in source.sport_info
            ),
            key=lambda item: item.source_sport_type,
        ),
        resting_hr_is_temporary=source.temporary_resting_hr,
    )


def map_wellness(source: WellnessDTO) -> WellnessDay:
    """Map one provider day without filling or normalizing missing values."""
    mapped = _wellness_without_fingerprint(source)
    fingerprint_payload = mapped.model_dump(
        mode="json",
        exclude={
            "schema_version",
            "mapping_version",
            "provider_snapshot_sha256",
            "source",
        },
    )
    canonical = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
    return mapped.model_copy(
        update={
            "provider_snapshot_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        }
    )


def _mapped_setting(source: SportSettingsDTO) -> SportSettings:
    return SportSettings(
        provider_settings_id=source.id,
        source_sport_types=sorted(source.types),
        functional_threshold_power_watts=source.ftp,
        indoor_functional_threshold_power_watts=source.indoor_ftp,
        lactate_threshold_hr_bpm=source.lthr,
        maximum_hr_bpm=source.max_hr,
        threshold_speed_meters_per_second=(source.threshold_speed_meters_per_second),
        pace_display_unit=source.pace_display_unit,
        power_zone_upper_bounds_watts=source.power_zones,
        heart_rate_zone_upper_bounds_bpm=source.hr_zones,
        pace_zone_upper_bounds_percent=source.pace_zones,
        power_zone_names=source.power_zone_names,
        heart_rate_zone_names=source.hr_zone_names,
        pace_zone_names=source.pace_zone_names,
        heart_rate_load_type=source.hr_load_type,
        pace_load_type=source.pace_load_type,
        load_priority=_priority(source.load_order),
        time_in_zones_priority=_priority(source.tiz_order),
        workout_priority=_priority(source.workout_order),
        default_workout_time_local=source.default_workout_time,
        provider_updated_at=source.updated,
    )


def map_sport_settings(
    source_settings: Iterable[SportSettingsDTO | dict[str, object]],
) -> SportSettingsSnapshot:
    """Return a stable snapshot independent of provider row ordering."""
    validated = [
        item if isinstance(item, SportSettingsDTO) else SportSettingsDTO.model_validate(item)
        for item in source_settings
    ]
    settings = sorted(
        (_mapped_setting(item) for item in validated),
        key=lambda item: item.provider_settings_id,
    )
    payload = [item.model_dump(mode="json", exclude_none=False) for item in settings]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return SportSettingsSnapshot(
        fingerprint_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
        settings=settings,
    )
