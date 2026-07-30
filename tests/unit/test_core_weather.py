"""Unit tests for weather core integration (core/weather.py)."""

from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pytest

from resilio.core.weather import (
    WeatherAPIError,
    WeatherNotFoundError,
    WeatherRateLimitError,
    WeatherValidationError,
    fetch_weekly_forecast,
    geocode_location,
    get_weekly_forecast_for_location,
    get_weekly_forecast_for_query,
)
from resilio.schemas.weather import AdvisoryLevel, AdvisoryType, WeatherLocation


@patch("resilio.core.weather.httpx.Client")
def test_geocode_location_success(mock_client_cls):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "name": "Paris",
                "admin1": "Ile-de-France",
                "country": "France",
                "latitude": 48.853,
                "longitude": 2.3499,
                "timezone": "Europe/Paris",
            }
        ]
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    location = geocode_location("Paris, France")

    assert location.latitude == 48.853
    assert location.longitude == 2.3499
    assert location.resolved_name == "Paris, Ile-de-France, France"


@patch("resilio.core.weather.httpx.Client")
def test_geocode_location_not_found(mock_client_cls):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    with pytest.raises(WeatherNotFoundError):
        geocode_location("nowhere")


@patch("resilio.core.weather.fetch_weekly_forecast")
def test_get_weekly_forecast_generates_advisories(mock_fetch):
    mock_fetch.return_value = {
        "daily": {
            "time": [
                "2026-02-16",
                "2026-02-17",
            ],
            "temperature_2m_max": [31.0, 12.0],
            "temperature_2m_min": [24.0, -1.0],
            "precipitation_sum": [0.0, 11.0],
            "precipitation_probability_max": [20, 90],
            "wind_speed_10m_max": [38.0, 10.0],
            "weather_code": [1, 61],
        }
    }

    forecast = get_weekly_forecast_for_location(
        location=WeatherLocation(
            location_query="Paris, France",
            resolved_name="Paris, France",
            latitude=48.853,
            longitude=2.3499,
            timezone="Europe/Paris",
        ),
        week_start=date(2026, 2, 16),
        week_end=date(2026, 2, 22),
    )

    assert len(forecast.daily) == 2
    assert any(
        advisory.type == AdvisoryType.HEAT and advisory.level == AdvisoryLevel.HIGH
        for advisory in forecast.advisories
    )
    assert any(
        advisory.type == AdvisoryType.WIND and advisory.level == AdvisoryLevel.HIGH
        for advisory in forecast.advisories
    )
    assert any(
        a.type == AdvisoryType.PRECIPITATION and a.level == AdvisoryLevel.HIGH
        for a in forecast.advisories
    )
    assert "high-risk days" in forecast.weekly_summary


@patch("resilio.core.weather.httpx.Client")
def test_fetch_weekly_forecast_missing_daily_raises(mock_client_cls):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"timezone": "Europe/Paris"}

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    with pytest.raises(WeatherAPIError):
        fetch_weekly_forecast(
            latitude=48.853,
            longitude=2.3499,
            week_start=date(2026, 2, 16),
            week_end=date(2026, 2, 22),
            timezone="Europe/Paris",
        )


def test_inverted_dates_raise_validation_error():
    """week_end < week_start should raise immediately, not silently return empty forecast."""
    location = WeatherLocation(
        location_query="Paris, France",
        latitude=48.853,
        longitude=2.3499,
        timezone="Europe/Paris",
    )
    with pytest.raises(WeatherValidationError, match="week_end"):
        get_weekly_forecast_for_location(
            location=location,
            week_start=date(2026, 2, 22),
            week_end=date(2026, 2, 16),  # inverted
        )


def test_inverted_dates_raise_in_query_path():
    with pytest.raises(WeatherValidationError, match="week_end"):
        get_weekly_forecast_for_query(
            location_query="Paris, France",
            week_start=date(2026, 2, 22),
            week_end=date(2026, 2, 16),
        )


@patch("resilio.core.weather.fetch_weekly_forecast")
def test_cold_advisory_generated_below_zero(mock_fetch):
    """Temperatures between -5°C and 0°C trigger a COLD_MODERATE advisory."""
    mock_fetch.return_value = {
        "daily": {
            "time": ["2026-02-16"],
            "temperature_2m_max": [5.0],
            "temperature_2m_min": [-2.0],  # -5 < -2 <= 0 → COLD_MODERATE
            "precipitation_sum": [0.0],
            "precipitation_probability_max": [10],
            "wind_speed_10m_max": [8.0],
            "weather_code": [1],
        }
    }

    forecast = get_weekly_forecast_for_location(
        location=WeatherLocation(
            location_query="Helsinki, Finland",
            latitude=60.169,
            longitude=24.938,
            timezone="Europe/Helsinki",
        ),
        week_start=date(2026, 2, 16),
        week_end=date(2026, 2, 22),
    )

    cold_advisories = [a for a in forecast.advisories if a.type == AdvisoryType.COLD]
    assert len(cold_advisories) == 1
    assert cold_advisories[0].level == AdvisoryLevel.MODERATE
    assert cold_advisories[0].signal == "COLD_MODERATE"


@patch("resilio.core.weather.fetch_weekly_forecast")
def test_advisory_signals_are_labels_not_recommendations(mock_fetch):
    """Advisory signal field must be a short label, not an English coaching recommendation."""
    mock_fetch.return_value = {
        "daily": {
            "time": ["2026-02-16"],
            "temperature_2m_max": [32.0],
            "temperature_2m_min": [22.0],
            "precipitation_sum": [0.0],
            "precipitation_probability_max": [10],
            "wind_speed_10m_max": [40.0],
            "weather_code": [1],
        }
    }

    forecast = get_weekly_forecast_for_location(
        location=WeatherLocation(
            location_query="Dubai, UAE",
            latitude=25.2,
            longitude=55.3,
            timezone="Asia/Dubai",
        ),
        week_start=date(2026, 2, 16),
        week_end=date(2026, 2, 22),
    )

    for advisory in forecast.advisories:
        # signal must be an uppercase label (e.g. HEAT_HIGH), not a prose sentence
        assert advisory.signal.isupper(), f"Signal should be uppercase label: {advisory.signal!r}"
        assert (
            len(advisory.signal.split()) == 1
        ), f"Signal should be a single label token, not prose: {advisory.signal!r}"


@patch("resilio.core.weather.httpx.Client")
def test_fetch_weekly_forecast_429_raises_rate_limit_error(mock_client_cls):
    """HTTP 429 from Open-Meteo should raise WeatherRateLimitError (not WeatherAPIError).

    WeatherRateLimitError is intentionally excluded from Tenacity retry predicates
    so that rate-limited requests are not retried immediately (ignoring Retry-After).
    """
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "60"}

    mock_client = MagicMock()
    mock_client.__enter__.return_value.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    with pytest.raises(WeatherRateLimitError, match="rate limit"):
        fetch_weekly_forecast(
            latitude=48.853,
            longitude=2.3499,
            week_start=date(2026, 2, 16),
            week_end=date(2026, 2, 22),
        )

    # 429 must NOT be retried — only one HTTP call should be made
    assert mock_client_cls.call_count == 1
