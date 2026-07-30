"""Weather API for weekly training-planning context."""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional, Union

from resilio.api.profile import ProfileError, get_profile, update_profile
from resilio.core.weather import (
    WeatherAPIError,
    WeatherNetworkError,
    WeatherNotFoundError,
    WeatherRateLimitError,
    WeatherValidationError,
    get_weekly_forecast_for_location,
    get_weekly_forecast_for_query,
)
from resilio.schemas.weather import WeatherLocation, WeeklyWeatherForecast
from resilio.utils.dates import get_week_boundaries, validate_week_start

logger = logging.getLogger(__name__)


@dataclass
class WeatherError:
    """Error result from weather API operations."""

    error_type: str  # "invalid_input", "validation", "not_found", "network", "unknown"
    message: str
    next_steps: Optional[str] = None


def get_weekly_weather_forecast(
    start_date: str,
    location: Optional[str] = None,
) -> Union[WeeklyWeatherForecast, WeatherError]:
    """Get a 7-day weather forecast for a planning week (Monday-Sunday)."""
    try:
        week_start = date.fromisoformat(start_date)
    except ValueError:
        return WeatherError(
            error_type="invalid_input",
            message=f"Invalid date format '{start_date}'. Expected YYYY-MM-DD.",
        )

    if not validate_week_start(week_start):
        return WeatherError(
            error_type="invalid_input",
            message=(
                f"Week start must be Monday, got {week_start.strftime('%A')} "
                f"({week_start.isoformat()})"
            ),
        )

    _, week_end = get_week_boundaries(week_start)

    try:
        explicit_location = (location or "").strip()

        if explicit_location:
            return get_weekly_forecast_for_query(
                location_query=explicit_location,
                week_start=week_start,
                week_end=week_end,
            )

        profile_result = get_profile()
        if isinstance(profile_result, ProfileError):
            return _map_profile_error_to_weather_error(profile_result)

        weather_preferences = getattr(profile_result, "weather_preferences", None)
        if weather_preferences is None or not weather_preferences.location_query:
            return WeatherError(
                error_type="invalid_input",
                message="No weather location configured in profile.",
                next_steps=(
                    'Run: resilio profile set --weather-location "City, Country" '
                    "or pass --location to resilio weather week."
                ),
            )

        # Use cached coordinates when available, otherwise resolve by location query.
        if weather_preferences.latitude is not None and weather_preferences.longitude is not None:
            forecast = get_weekly_forecast_for_location(
                location=WeatherLocation(
                    location_query=weather_preferences.location_query,
                    resolved_name=weather_preferences.resolved_name,
                    latitude=weather_preferences.latitude,
                    longitude=weather_preferences.longitude,
                    timezone=weather_preferences.timezone,
                ),
                week_start=week_start,
                week_end=week_end,
            )
            _maybe_persist_weather_cache(profile_result, forecast.location)
            return forecast

        forecast = get_weekly_forecast_for_query(
            location_query=weather_preferences.location_query,
            week_start=week_start,
            week_end=week_end,
        )
        _maybe_persist_weather_cache(profile_result, forecast.location)
        return forecast

    except WeatherValidationError as exc:
        return WeatherError(error_type="invalid_input", message=str(exc))
    except WeatherNotFoundError as exc:
        return WeatherError(error_type="not_found", message=str(exc))
    except WeatherNetworkError as exc:
        return WeatherError(error_type="network", message=str(exc))
    except WeatherRateLimitError as exc:
        return WeatherError(error_type="rate_limit", message=str(exc))
    except WeatherAPIError as exc:
        return WeatherError(error_type="api_error", message=str(exc))
    except Exception as exc:
        return WeatherError(error_type="unknown", message=f"Unexpected error: {exc}")


def _map_profile_error_to_weather_error(profile_error: object) -> WeatherError:
    """Map profile API errors to weather API errors with actionable guidance."""
    error_type = getattr(profile_error, "error_type", "unknown")
    message = getattr(profile_error, "message", "Unknown profile error")

    if error_type == "not_found":
        return WeatherError(
            error_type="not_found",
            message=f"Cannot load profile for weather lookup: {message}",
            next_steps='Run: resilio profile create --name "Your Name" before weather lookup.',
        )

    if error_type == "validation":
        return WeatherError(
            error_type="validation",
            message=f"Profile validation error during weather lookup: {message}",
            next_steps=(
                "Run: resilio profile get to inspect profile data or use "
                "resilio profile edit to repair invalid fields."
            ),
        )

    return WeatherError(
        error_type="unknown",
        message=f"Profile error during weather lookup: {message}",
        next_steps="Retry after resolving profile/config issues.",
    )


def _maybe_persist_weather_cache(profile: object, resolved_location: WeatherLocation) -> None:
    """Best-effort cache enrichment for profile-based weather lookups."""
    current = getattr(profile, "weather_preferences", None)
    if current is None or not getattr(current, "location_query", None):
        return

    payload = {
        "location_query": current.location_query,
        "resolved_name": resolved_location.resolved_name,
        "latitude": resolved_location.latitude,
        "longitude": resolved_location.longitude,
        "timezone": resolved_location.timezone,
    }

    if not _weather_cache_changed(current, payload):
        return

    # Non-blocking cache update: weather result remains successful even if write fails.
    result = update_profile(weather_preferences=payload)
    if result is not None and isinstance(result, ProfileError):
        logger.debug(
            "Weather cache write failed (non-blocking): %s — %s",
            result.error_type,
            result.message,
        )


def _weather_cache_changed(
    current: object,
    payload: dict[str, object],
) -> bool:
    """Check if cache payload differs from current profile weather preferences.

    resolved_name is intentionally excluded: it can vary cosmetically between API calls
    (e.g., "Paris, France" vs "Paris, Ile-de-France, France") and should not trigger
    a cache write when coordinates and timezone are already accurate.
    """
    return any(
        getattr(current, key, None) != payload.get(key)
        for key in ["location_query", "latitude", "longitude", "timezone"]
    )
