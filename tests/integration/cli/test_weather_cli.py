"""Integration tests for resilio weather CLI commands."""

import json
from datetime import date
from unittest.mock import patch

from typer.testing import CliRunner

from resilio.api.weather import WeatherError
from resilio.cli.commands.weather import app
from resilio.schemas.weather import (
    AdvisoryLevel,
    AdvisoryType,
    DailyWeatherForecast,
    WeatherAdvisory,
    WeatherAdvisorySignal,
    WeatherLocation,
    WeeklyWeatherForecast,
)

runner = CliRunner()


def _forecast(advisories: list | None = None) -> WeeklyWeatherForecast:
    return WeeklyWeatherForecast(
        start_date=date(2026, 2, 16),
        end_date=date(2026, 2, 22),
        location=WeatherLocation(
            location_query="Paris, France",
            resolved_name="Paris, France",
            latitude=48.853,
            longitude=2.3499,
            timezone="Europe/Paris",
        ),
        daily=[
            DailyWeatherForecast(
                date=date(2026, 2, 16),
                temperature_min_c=2,
                temperature_max_c=9,
                precipitation_mm=0,
                precipitation_probability_max_pct=10,
                wind_speed_max_kph=12,
                weather_code=1,
            )
        ],
        advisories=advisories or [],
        weekly_summary="No significant weather risks detected for this week.",
    )


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_success(mock_api):
    mock_api.return_value = _forecast()

    result = runner.invoke(app, ["week", "--start", "2026-02-16", "--location", "Paris, France"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["start_date"] == "2026-02-16"


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_success_message_uses_resolved_name(mock_api):
    """Success message must include resolved location name, not a hasattr guess."""
    mock_api.return_value = _forecast()

    result = runner.invoke(app, ["week", "--start", "2026-02-16", "--location", "Paris, France"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "Paris, France" in payload["message"]


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_error_does_not_use_location_from_error_object(mock_api):
    """When API returns a WeatherError, success message must not crash accessing .location."""
    mock_api.return_value = WeatherError(
        error_type="not_found",
        message="No location match found.",
    )

    result = runner.invoke(app, ["week", "--start", "2026-02-16", "--location", "nowhere"])

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    # Should not raise AttributeError on .location access
    assert payload["error_type"] == "not_found"


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_location_flag_is_passed_to_api(mock_api):
    """--location override must be forwarded to the API layer."""
    mock_api.return_value = _forecast()

    runner.invoke(app, ["week", "--start", "2026-02-16", "--location", "Tokyo, Japan"])

    mock_api.assert_called_once_with(start_date="2026-02-16", location="Tokyo, Japan")


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_no_location_flag_uses_profile(mock_api):
    """When --location is omitted, API must receive location=None (profile-based lookup)."""
    mock_api.return_value = _forecast()

    runner.invoke(app, ["week", "--start", "2026-02-16"])

    mock_api.assert_called_once_with(start_date="2026-02-16", location=None)


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_non_monday_validation_error(mock_api):
    mock_api.return_value = WeatherError(
        error_type="invalid_input",
        message="Week start must be Monday, got Tuesday (2026-02-17)",
    )

    result = runner.invoke(app, ["week", "--start", "2026-02-17"])

    assert result.exit_code == 5
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_type"] == "invalid_input"


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_missing_location_includes_next_steps(mock_api):
    mock_api.return_value = WeatherError(
        error_type="invalid_input",
        message="No weather location configured in profile.",
        next_steps='Run: resilio profile set --weather-location "City, Country"',
    )

    result = runner.invoke(app, ["week", "--start", "2026-02-16"])

    assert result.exit_code == 5
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "next_steps" in payload["data"]
    assert "weather-location" in payload["data"]["next_steps"]


@patch("resilio.cli.commands.weather.get_weekly_weather_forecast")
def test_weather_week_all_advisory_types_present_in_output(mock_api):
    """All four advisory types (heat, cold, wind, precipitation) should serialize correctly."""
    advisories = [
        WeatherAdvisory(
            date=date(2026, 2, 16),
            type=AdvisoryType.HEAT,
            level=AdvisoryLevel.HIGH,
            reason="Hot day forecast (32.0°C max)",
            signal=WeatherAdvisorySignal.HEAT_HIGH,
        ),
        WeatherAdvisory(
            date=date(2026, 2, 17),
            type=AdvisoryType.COLD,
            level=AdvisoryLevel.MODERATE,
            reason="Cold conditions (-2.0°C min)",
            signal=WeatherAdvisorySignal.COLD_MODERATE,
        ),
        WeatherAdvisory(
            date=date(2026, 2, 18),
            type=AdvisoryType.WIND,
            level=AdvisoryLevel.HIGH,
            reason="Strong wind forecast (38.0 km/h max)",
            signal=WeatherAdvisorySignal.WIND_HIGH,
        ),
        WeatherAdvisory(
            date=date(2026, 2, 19),
            type=AdvisoryType.PRECIPITATION,
            level=AdvisoryLevel.HIGH,
            reason="Precipitation risk (12 mm, 85% prob)",
            signal=WeatherAdvisorySignal.PRECIPITATION_HIGH,
        ),
    ]
    mock_api.return_value = _forecast(advisories=advisories)

    result = runner.invoke(app, ["week", "--start", "2026-02-16", "--location", "Paris, France"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    advisory_types = {a["type"] for a in payload["data"]["advisories"]}
    assert advisory_types == {"heat", "cold", "wind", "precipitation"}
    # All advisories should expose signal, not recommendation
    for advisory in payload["data"]["advisories"]:
        assert "signal" in advisory
        assert "recommendation" not in advisory
