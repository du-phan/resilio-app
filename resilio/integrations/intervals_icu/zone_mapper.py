"""Map Intervals.icu zone-duration arrays with their captured settings."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Literal, cast

from resilio.integrations.intervals_icu.dto import ActivityDTO, ZoneTimeDTO
from resilio.schemas.activity import (
    ActivityAnalysisThresholds,
    ActivityZoneTime,
    ZoneMeasurementMethod,
    ZoneTimeDistribution,
)


def map_analysis_thresholds(
    activity: ActivityDTO,
) -> ActivityAnalysisThresholds | None:
    """Preserve the threshold and zone settings attached to one activity."""
    values = (
        activity.ftp,
        activity.lthr,
        activity.max_hr,
        activity.threshold_speed_meters_per_second,
        activity.icu_power_zones,
        activity.hr_zones,
        activity.pace_zones,
    )
    if not any(value for value in values):
        return None
    return ActivityAnalysisThresholds(
        functional_threshold_power_watts=activity.ftp,
        lactate_threshold_hr_bpm=activity.lthr,
        maximum_hr_bpm=activity.max_hr,
        threshold_speed_meters_per_second=(activity.threshold_speed_meters_per_second),
        pace_display_unit=activity.pace_display_unit,
        power_zone_upper_bounds_watts=activity.icu_power_zones,
        heart_rate_zone_upper_bounds_bpm=activity.hr_zones,
        pace_zone_upper_bounds_percent=activity.pace_zones,
        power_zone_names=activity.power_zone_names,
        heart_rate_zone_names=activity.hr_zone_names,
        pace_zone_names=activity.pace_zone_names,
    )


def _zone_time(
    *,
    zone_index: int,
    duration_seconds: int,
    upper_bounds: Sequence[float | int],
    names: Sequence[str],
) -> ActivityZoneTime:
    upper_bound = float(upper_bounds[zone_index - 1]) if zone_index <= len(upper_bounds) else None
    lower_bound = (
        float(upper_bounds[zone_index - 2])
        if zone_index > 1 and zone_index - 1 <= len(upper_bounds)
        else None
    )
    return ActivityZoneTime(
        zone_index=zone_index,
        name=names[zone_index - 1] if zone_index <= len(names) else None,
        duration_seconds=duration_seconds,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )


def _zone_distribution(
    duration_seconds_by_zone: list[int],
    method: ZoneMeasurementMethod,
    moving_seconds: int,
    is_primary_method: bool,
    analysis_settings_sha256: str | None,
    upper_bounds: Sequence[float | int],
    names: Sequence[str],
) -> ZoneTimeDistribution | None:
    if not duration_seconds_by_zone:
        return None
    covered_seconds = sum(duration_seconds_by_zone)
    coverage_percent = covered_seconds / moving_seconds * 100 if moving_seconds > 0 else None
    measurement_unit = cast(
        Literal["watts", "beats_per_minute", "percent"],
        {
            ZoneMeasurementMethod.POWER: "watts",
            ZoneMeasurementMethod.HEART_RATE: "beats_per_minute",
            ZoneMeasurementMethod.PACE: "percent",
            ZoneMeasurementMethod.GRADE_ADJUSTED_PACE: "percent",
        }[method],
    )
    return ZoneTimeDistribution(
        measurement_method=method,
        zones=[
            _zone_time(
                zone_index=zone_index,
                duration_seconds=duration_seconds,
                upper_bounds=upper_bounds,
                names=names,
            )
            for zone_index, duration_seconds in enumerate(
                duration_seconds_by_zone,
                start=1,
            )
        ],
        covered_duration_seconds=covered_seconds,
        analysis_source_moving_duration_seconds=moving_seconds,
        moving_time_coverage_percent=coverage_percent,
        is_primary_time_in_zones_method=is_primary_method,
        measurement_unit=measurement_unit,
        analysis_settings_sha256=analysis_settings_sha256,
    )


def _power_zone_index(
    provider_zone_id: str,
    names: Sequence[str],
) -> int | None:
    """Resolve only an exact, unambiguous provider-ID/name match."""
    matching_indexes = [
        index
        for index, name in enumerate(names, start=1)
        if name == provider_zone_id
    ]
    return matching_indexes[0] if len(matching_indexes) == 1 else None


def _power_zone_time(
    source: ZoneTimeDTO,
    upper_bounds: Sequence[int],
    names: Sequence[str],
) -> ActivityZoneTime:
    zone_index = _power_zone_index(source.id, names)
    if zone_index is None:
        return ActivityZoneTime(
            provider_zone_id=source.id,
            duration_seconds=source.duration_seconds,
        )
    return ActivityZoneTime(
        zone_index=zone_index,
        provider_zone_id=source.id,
        name=names[zone_index - 1],
        duration_seconds=source.duration_seconds,
        lower_bound=(
            float(upper_bounds[zone_index - 2])
            if zone_index > 1 and zone_index - 1 <= len(upper_bounds)
            else None
        ),
        upper_bound=(
            float(upper_bounds[zone_index - 1])
            if zone_index <= len(upper_bounds)
            else None
        ),
    )


def _power_zone_distribution(
    source_zones: list[ZoneTimeDTO],
    moving_seconds: int,
    is_primary_method: bool,
    analysis_settings_sha256: str | None,
    upper_bounds: Sequence[int],
    names: Sequence[str],
) -> ZoneTimeDistribution | None:
    if not source_zones:
        return None
    zones = [
        _power_zone_time(source, upper_bounds, names)
        for source in source_zones
    ]
    zones.sort(
        key=lambda zone: (
            zone.zone_index is None,
            zone.zone_index or 0,
            zone.provider_zone_id or "",
        )
    )
    covered_seconds = sum(zone.duration_seconds for zone in zones)
    coverage_percent = (
        covered_seconds / moving_seconds * 100
        if moving_seconds > 0
        else None
    )
    return ZoneTimeDistribution(
        measurement_method=ZoneMeasurementMethod.POWER,
        zones=zones,
        covered_duration_seconds=covered_seconds,
        analysis_source_moving_duration_seconds=moving_seconds,
        moving_time_coverage_percent=coverage_percent,
        is_primary_time_in_zones_method=is_primary_method,
        measurement_unit="watts",
        analysis_settings_sha256=analysis_settings_sha256,
    )


def _selected_primary_method(
    activity: ActivityDTO,
) -> ZoneMeasurementMethod | None:
    """Return the first configured time-in-zones method with source data."""
    available = {
        "POWER": (ZoneMeasurementMethod.POWER if activity.icu_zone_times else None),
        "HR": (ZoneMeasurementMethod.HEART_RATE if activity.icu_hr_zone_times else None),
        "PACE": (
            ZoneMeasurementMethod.GRADE_ADJUSTED_PACE
            if activity.use_gap_zone_times and activity.gap_zone_times
            else (
                ZoneMeasurementMethod.PACE
                if activity.pace_zone_times
                else (
                    ZoneMeasurementMethod.GRADE_ADJUSTED_PACE if activity.gap_zone_times else None
                )
            )
        ),
    }
    for token in (activity.tiz_order or "").upper().split("_"):
        selected = available.get(token)
        if selected is not None:
            return selected
    return None


def map_zone_time_distributions(
    activity: ActivityDTO,
) -> list[ZoneTimeDistribution]:
    """Bind native duration arrays to the activity's exact zone snapshot."""
    thresholds = map_analysis_thresholds(activity)
    settings_sha256 = (
        hashlib.sha256(
            json.dumps(
                thresholds.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        if thresholds is not None
        else None
    )
    primary_method = _selected_primary_method(activity)
    candidates = (
        (
            activity.icu_hr_zone_times,
            ZoneMeasurementMethod.HEART_RATE,
            activity.hr_zones,
            activity.hr_zone_names,
        ),
        (
            activity.pace_zone_times,
            ZoneMeasurementMethod.PACE,
            activity.pace_zones,
            activity.pace_zone_names,
        ),
        (
            activity.gap_zone_times,
            ZoneMeasurementMethod.GRADE_ADJUSTED_PACE,
            activity.pace_zones,
            activity.pace_zone_names,
        ),
    )
    result: list[ZoneTimeDistribution] = []
    power_distribution = _power_zone_distribution(
        activity.icu_zone_times,
        activity.moving_time,
        primary_method == ZoneMeasurementMethod.POWER,
        settings_sha256,
        activity.icu_power_zones,
        activity.power_zone_names,
    )
    if power_distribution is not None:
        result.append(power_distribution)
    for source, method, upper_bounds, names in candidates:
        mapped = _zone_distribution(
            source,
            method,
            activity.moving_time,
            method == primary_method,
            settings_sha256,
            upper_bounds,
            names,
        )
        if mapped is not None:
            result.append(mapped)
    return result
