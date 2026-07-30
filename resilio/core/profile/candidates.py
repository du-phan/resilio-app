"""Read-only projection of provider physiology observations."""

from __future__ import annotations

from datetime import date, datetime

from resilio.schemas.training_state import (
    ProviderProfileCandidate,
    ProviderProfileCandidates,
    ProviderProfileMetric,
    SportSettings,
    SportSettingsSnapshot,
    WellnessDay,
)


def _setting_candidates(setting: SportSettings) -> list[ProviderProfileCandidate]:
    values: list[tuple[ProviderProfileMetric, float | int | None, str]] = [
        (
            ProviderProfileMetric.FUNCTIONAL_THRESHOLD_POWER,
            setting.functional_threshold_power_watts,
            "watts",
        ),
        (
            ProviderProfileMetric.INDOOR_FUNCTIONAL_THRESHOLD_POWER,
            setting.indoor_functional_threshold_power_watts,
            "watts",
        ),
        (
            ProviderProfileMetric.LACTATE_THRESHOLD_HEART_RATE,
            setting.lactate_threshold_hr_bpm,
            "bpm",
        ),
        (
            ProviderProfileMetric.MAXIMUM_HEART_RATE,
            setting.maximum_hr_bpm,
            "bpm",
        ),
        (
            ProviderProfileMetric.THRESHOLD_SPEED,
            setting.threshold_speed_meters_per_second,
            "meters_per_second",
        ),
    ]
    return [
        ProviderProfileCandidate(
            metric_name=metric_name,
            value=float(value),
            unit=unit,
            source_sport_types=setting.source_sport_types,
            provider_settings_id=setting.provider_settings_id,
            provider_updated_at=setting.provider_updated_at,
        )
        for metric_name, value, unit in values
        if value is not None
    ]


def _latest_wellness_candidate(
    wellness: dict[date, WellnessDay],
    *,
    as_of_date: date,
    metric_name: ProviderProfileMetric,
    attribute_name: str,
    unit: str,
) -> ProviderProfileCandidate | None:
    eligible = [
        row
        for day, row in wellness.items()
        if day <= as_of_date and getattr(row, attribute_name) is not None
    ]
    if not eligible:
        return None
    latest = max(eligible, key=lambda row: row.local_date)
    value = getattr(latest, attribute_name)
    assert value is not None
    return ProviderProfileCandidate(
        metric_name=metric_name,
        value=float(value),
        unit=unit,
        observed_on=latest.local_date,
        is_temporary=(
            latest.resting_hr_is_temporary
            if metric_name is ProviderProfileMetric.RESTING_HEART_RATE
            else False
        ),
    )


def build_provider_profile_candidates(
    settings: SportSettingsSnapshot | None,
    wellness: dict[date, WellnessDay],
    *,
    as_of_date: date,
    generated_at_utc: datetime,
) -> ProviderProfileCandidates:
    """Expose available provider values without filling or applying them."""
    if generated_at_utc.tzinfo is None:
        raise ValueError("generated_at_utc must be timezone-aware")
    candidates = [
        candidate
        for setting in (settings.settings if settings is not None else [])
        for candidate in _setting_candidates(setting)
    ]
    for metric_name, attribute_name, unit in [
        (
            ProviderProfileMetric.RESTING_HEART_RATE,
            "resting_hr_bpm",
            "bpm",
        ),
        (
            ProviderProfileMetric.PROVIDER_VO2_MAX,
            "vo2_max_ml_per_kg_per_min",
            "milliliters_per_kilogram_per_minute",
        ),
    ]:
        candidate = _latest_wellness_candidate(
            wellness,
            as_of_date=as_of_date,
            metric_name=metric_name,
            attribute_name=attribute_name,
            unit=unit,
        )
        if candidate is not None:
            candidates.append(candidate)
    candidates.sort(
        key=lambda candidate: (
            str(candidate.metric_name),
            candidate.provider_settings_id or -1,
            candidate.observed_on or date.min,
        )
    )
    return ProviderProfileCandidates(
        as_of_date=as_of_date,
        generated_at_utc=generated_at_utc,
        sport_settings_fingerprint_sha256=(
            settings.fingerprint_sha256 if settings is not None else None
        ),
        candidates=candidates,
    )
