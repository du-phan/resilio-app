"""Weather integration (Open-Meteo) for weekly planning context."""

import logging
from datetime import date
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from resilio.schemas.weather import (
    AdvisoryLevel,
    AdvisoryType,
    DailyWeatherForecast,
    WeatherAdvisory,
    WeatherAdvisorySignal,
    WeatherLocation,
    WeeklyWeatherForecast,
)

logger = logging.getLogger(__name__)

OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Advisory thresholds — represent moderate-climate defaults.
# A runner in Phoenix may tolerate heat at thresholds that are extreme for an Alaskan runner.
# Longer-term: consider configuring heat_tolerance per athlete profile.
_HEAT_HIGH_C = 30.0  # Above this max temp: serious heat stress in most climates
_HEAT_MODERATE_C = 26.0  # Above this max temp: warmer conditions requiring pacing adjustment
_COLD_HIGH_C = -5.0  # Below this min temp: risk of hypothermia / unsafe surfaces
_COLD_MODERATE_C = 0.0  # Below this min temp: freezing conditions requiring extended warm-up
_WIND_HIGH_KPH = 35.0  # Above this max wind: significant impact on pacing and safety
_WIND_MODERATE_KPH = 25.0  # Above this max wind: noticeable headwind impact
_PRECIP_HIGH_MM = 10.0  # Heavy precipitation threshold (mm/day)
_PRECIP_HIGH_PROB = 80  # High precipitation probability threshold (%)
_PRECIP_MODERATE_MM = 5.0
_PRECIP_MODERATE_PROB = 60


class WeatherCoreError(Exception):
    """Base weather integration error."""


class WeatherValidationError(WeatherCoreError):
    """Invalid input for weather lookup."""


class WeatherNotFoundError(WeatherCoreError):
    """No weather location match found."""


class WeatherNetworkError(WeatherCoreError):
    """Network-level weather request failure."""


class WeatherAPIError(WeatherCoreError):
    """Weather API request returned invalid/unexpected response."""


class WeatherRateLimitError(WeatherCoreError):
    """Open-Meteo rate limit hit (HTTP 429).

    Intentionally does NOT inherit from WeatherAPIError so Tenacity retry
    predicates can exclude it — retrying immediately on 429 ignores Retry-After
    and wastes quota.
    """


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type((httpx.HTTPError, WeatherNetworkError)),
    reraise=True,
)
def geocode_location(location_query: str) -> WeatherLocation:
    """Resolve a location query into coordinates via Open-Meteo geocoding."""
    query = (location_query or "").strip()
    if not query:
        raise WeatherValidationError("Location query is required")

    logger.debug("Geocoding location query: %r", query)
    try:
        with httpx.Client() as client:
            response = client.get(
                OPEN_METEO_GEOCODING_URL,
                params={
                    "name": query,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                },
                timeout=20.0,
            )
    except httpx.HTTPError as exc:
        raise WeatherNetworkError(f"Geocoding request failed: {exc}") from exc

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "unknown")
        logger.warning("Open-Meteo geocoding rate limit hit; Retry-After: %s", retry_after)
        raise WeatherRateLimitError(
            f"Open-Meteo geocoding rate limit exceeded (Retry-After: {retry_after})"
        )

    if response.status_code != 200:
        raise WeatherAPIError(
            f"Geocoding failed with status {response.status_code}: {response.text}"
        )

    payload = response.json()
    results = payload.get("results") or []
    if not results:
        raise WeatherNotFoundError(f"No location match found for '{query}'")

    best = results[0]
    location = WeatherLocation(
        location_query=query,
        resolved_name=_format_resolved_name(best),
        latitude=best.get("latitude"),
        longitude=best.get("longitude"),
        timezone=best.get("timezone"),
    )
    logger.debug(
        "Geocoded %r → %s (%.4f, %.4f)",
        query,
        location.resolved_name,
        location.latitude if location.latitude is not None else 0,
        location.longitude if location.longitude is not None else 0,
    )
    return location


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type((httpx.HTTPError, WeatherNetworkError)),
    reraise=True,
)
def fetch_weekly_forecast(
    latitude: float,
    longitude: float,
    week_start: date,
    week_end: date,
    timezone: str = "auto",
) -> dict[str, Any]:
    """Fetch 7-day daily forecast fields from Open-Meteo."""
    logger.debug(
        "Fetching forecast for (%.4f, %.4f) %s to %s (tz=%s)",
        latitude,
        longitude,
        week_start,
        week_end,
        timezone,
    )
    try:
        with httpx.Client() as client:
            response = client.get(
                OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone,
                    "start_date": week_start.isoformat(),
                    "end_date": week_end.isoformat(),
                    "daily": ",".join(
                        [
                            "temperature_2m_max",
                            "temperature_2m_min",
                            "precipitation_sum",
                            "precipitation_probability_max",
                            "wind_speed_10m_max",
                            "weather_code",
                        ]
                    ),
                },
                timeout=20.0,
            )
    except httpx.HTTPError as exc:
        raise WeatherNetworkError(f"Forecast request failed: {exc}") from exc

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "unknown")
        logger.warning("Open-Meteo forecast rate limit hit; Retry-After: %s", retry_after)
        raise WeatherRateLimitError(f"Open-Meteo rate limit exceeded (Retry-After: {retry_after})")

    if response.status_code != 200:
        raise WeatherAPIError(
            f"Forecast failed with status {response.status_code}: {response.text}"
        )

    raw_payload = response.json()
    if not isinstance(raw_payload, dict) or "daily" not in raw_payload:
        raise WeatherAPIError("Forecast response missing 'daily' field")
    payload: dict[str, Any] = raw_payload

    logger.debug("Forecast received with %d daily entries", len(payload["daily"].get("time", [])))
    return payload


def get_weekly_forecast_for_query(
    location_query: str,
    week_start: date,
    week_end: date,
) -> WeeklyWeatherForecast:
    """Resolve location query and return weekly weather forecast with advisories."""
    if week_end < week_start:
        raise WeatherValidationError(f"week_end ({week_end}) must be >= week_start ({week_start})")
    location = geocode_location(location_query)
    return get_weekly_forecast_for_location(location, week_start=week_start, week_end=week_end)


def get_weekly_forecast_for_location(
    location: WeatherLocation,
    week_start: date,
    week_end: date,
) -> WeeklyWeatherForecast:
    """Return weekly weather forecast from coordinates or location query."""
    if week_end < week_start:
        raise WeatherValidationError(f"week_end ({week_end}) must be >= week_start ({week_start})")
    active_location = location
    if active_location.latitude is None or active_location.longitude is None:
        if not active_location.location_query:
            raise WeatherValidationError("Location requires latitude/longitude or a location query")
        active_location = geocode_location(active_location.location_query)
    latitude = active_location.latitude
    longitude = active_location.longitude
    if latitude is None or longitude is None:
        raise WeatherValidationError("Resolved weather location is missing latitude or longitude")

    payload = fetch_weekly_forecast(
        latitude=latitude,
        longitude=longitude,
        week_start=week_start,
        week_end=week_end,
        timezone=active_location.timezone or "auto",
    )

    daily_forecasts = _build_daily_forecasts(payload)
    advisories = _build_advisories(daily_forecasts)

    return WeeklyWeatherForecast(
        start_date=week_start,
        end_date=week_end,
        source="open-meteo",
        location=active_location,
        daily=daily_forecasts,
        advisories=advisories,
        weekly_summary=_build_weekly_summary(advisories, len(daily_forecasts)),
    )


def _build_daily_forecasts(payload: dict[str, Any]) -> list[DailyWeatherForecast]:
    daily = payload.get("daily", {})
    dates = daily.get("time") or []

    temperature_max = daily.get("temperature_2m_max") or []
    temperature_min = daily.get("temperature_2m_min") or []
    precipitation_sum = daily.get("precipitation_sum") or []
    precipitation_probability = daily.get("precipitation_probability_max") or []
    wind_speed_max = daily.get("wind_speed_10m_max") or []
    weather_code = daily.get("weather_code") or []

    rows: list[DailyWeatherForecast] = []
    for idx, day_str in enumerate(dates):
        rows.append(
            DailyWeatherForecast(
                date=date.fromisoformat(day_str),
                temperature_min_c=_safe_float(_array_value(temperature_min, idx)),
                temperature_max_c=_safe_float(_array_value(temperature_max, idx)),
                precipitation_mm=_safe_float(_array_value(precipitation_sum, idx)),
                precipitation_probability_max_pct=_safe_int(
                    _array_value(precipitation_probability, idx)
                ),
                wind_speed_max_kph=_safe_float(_array_value(wind_speed_max, idx)),
                weather_code=_safe_int(_array_value(weather_code, idx)),
            )
        )

    return rows


def _build_advisories(days: list[DailyWeatherForecast]) -> list[WeatherAdvisory]:
    advisories: list[WeatherAdvisory] = []

    for day in days:
        if day.temperature_max_c is not None:
            if day.temperature_max_c >= _HEAT_HIGH_C:
                advisories.append(
                    _advisory(
                        day,
                        AdvisoryType.HEAT,
                        AdvisoryLevel.HIGH,
                        reason=f"Hot day forecast ({day.temperature_max_c:.1f}°C max)",
                    )
                )
            elif day.temperature_max_c >= _HEAT_MODERATE_C:
                advisories.append(
                    _advisory(
                        day,
                        AdvisoryType.HEAT,
                        AdvisoryLevel.MODERATE,
                        reason=f"Warm day forecast ({day.temperature_max_c:.1f}°C max)",
                    )
                )

        if day.temperature_min_c is not None:
            if day.temperature_min_c <= _COLD_HIGH_C:
                advisories.append(
                    _advisory(
                        day,
                        AdvisoryType.COLD,
                        AdvisoryLevel.HIGH,
                        reason=f"Very cold conditions ({day.temperature_min_c:.1f}°C min)",
                    )
                )
            elif day.temperature_min_c <= _COLD_MODERATE_C:
                advisories.append(
                    _advisory(
                        day,
                        AdvisoryType.COLD,
                        AdvisoryLevel.MODERATE,
                        reason=f"Cold conditions ({day.temperature_min_c:.1f}°C min)",
                    )
                )

        if day.wind_speed_max_kph is not None:
            if day.wind_speed_max_kph >= _WIND_HIGH_KPH:
                advisories.append(
                    _advisory(
                        day,
                        AdvisoryType.WIND,
                        AdvisoryLevel.HIGH,
                        reason=f"Strong wind forecast ({day.wind_speed_max_kph:.1f} km/h max)",
                    )
                )
            elif day.wind_speed_max_kph >= _WIND_MODERATE_KPH:
                advisories.append(
                    _advisory(
                        day,
                        AdvisoryType.WIND,
                        AdvisoryLevel.MODERATE,
                        reason=f"Windy conditions ({day.wind_speed_max_kph:.1f} km/h max)",
                    )
                )

        precipitation_level = _precipitation_level(day)
        if precipitation_level is not None:
            advisories.append(
                _advisory(
                    day,
                    AdvisoryType.PRECIPITATION,
                    precipitation_level,
                    reason=(
                        f"Precipitation risk ({_value_str(day.precipitation_mm)} mm, "
                        f"{_value_str(day.precipitation_probability_max_pct)}% prob)"
                    ),
                )
            )

    return advisories


def _precipitation_level(day: DailyWeatherForecast) -> Optional[AdvisoryLevel]:
    # Treat missing data as truly unknown — not as zero precipitation.
    # Both fields must be absent to return None (no advisory signal at all).
    if day.precipitation_mm is None and day.precipitation_probability_max_pct is None:
        return None

    precip_mm = day.precipitation_mm if day.precipitation_mm is not None else 0.0
    precip_prob = (
        day.precipitation_probability_max_pct
        if day.precipitation_probability_max_pct is not None
        else 0
    )

    if precip_mm >= _PRECIP_HIGH_MM or precip_prob >= _PRECIP_HIGH_PROB:
        return AdvisoryLevel.HIGH
    if precip_mm >= _PRECIP_MODERATE_MM or precip_prob >= _PRECIP_MODERATE_PROB:
        return AdvisoryLevel.MODERATE
    return None


def _make_signal(advisory_type: AdvisoryType, level: AdvisoryLevel) -> WeatherAdvisorySignal:
    """Derive the canonical signal label from advisory type and level.

    Raises KeyError if the combination has no registered entry in WeatherAdvisorySignal.
    Adding a new AdvisoryType requires a corresponding pair of entries in the enum.
    """
    key = f"{advisory_type.value.upper()}_{level.value.upper()}"
    return WeatherAdvisorySignal[key]


def _advisory(
    day: DailyWeatherForecast,
    advisory_type: AdvisoryType,
    level: AdvisoryLevel,
    reason: str,
) -> WeatherAdvisory:
    return WeatherAdvisory(
        date=day.date,
        type=advisory_type,
        level=level,
        reason=reason,
        signal=_make_signal(advisory_type, level),
    )


def _build_weekly_summary(advisories: list[WeatherAdvisory], total_days: int) -> str:
    if not advisories:
        return "No significant weather risks detected for this week."

    high_days = {a.date for a in advisories if a.level == AdvisoryLevel.HIGH}
    moderate_days = {a.date for a in advisories if a.level == AdvisoryLevel.MODERATE}
    affected_days = {a.date for a in advisories}

    return (
        f"Weather advisories for {len(affected_days)}/{total_days} days "
        f"(high-risk days: {len(high_days)}, moderate-risk days: {len(moderate_days)})."
    )


def _format_resolved_name(raw: dict[str, Any]) -> str:
    parts = [
        raw.get("name"),
        raw.get("admin1"),
        raw.get("country"),
    ]
    return ", ".join([part for part in parts if part])


def _array_value(values: list[Any], idx: int) -> Any:
    if idx < len(values):
        return values[idx]
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _value_str(value: Optional[float | int]) -> str:
    if value is None:
        return "n/a"
    return str(value)
