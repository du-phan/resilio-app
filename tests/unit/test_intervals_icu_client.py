"""Typed HTTP boundary tests; every request uses MockTransport."""

from datetime import date, datetime, timezone

import httpx
import pytest

from resilio.integrations.intervals_icu.client import IntervalsIcuClient
from resilio.integrations.intervals_icu.dto import EventWriteDTO
from resilio.integrations.intervals_icu.errors import (
    IntervalsAuthenticationError,
    IntervalsAuthorizationError,
    IntervalsInvalidPayloadError,
    IntervalsRateLimitError,
    IntervalsTransportError,
)
from resilio.schemas.config import Config, Settings


def _config() -> Config:
    return Config(
        settings=Settings(),
        intervals_icu_api_key="never-log-this-test-key",
        loaded_at=datetime.now(timezone.utc),
    )


def test_account_request_uses_stable_agent_and_basic_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/athlete/0"
        assert request.headers["User-Agent"].startswith("Resilio/")
        assert request.headers["Authorization"].startswith("Basic ")
        return httpx.Response(
            200,
            json={"id": "athlete-1", "name": "Athlete", "timezone": "Europe/Paris"},
        )

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as client:
        athlete = client.get_athlete()

    assert athlete.id == "athlete-1"
    assert athlete.timezone == "Europe/Paris"


def test_nullable_upload_filters_follow_live_contract() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "id": "athlete-1",
                "timezone": "Europe/Paris",
                "icu_garmin_upload_filters": None,
            },
        )
    )
    with IntervalsIcuClient(_config(), transport=transport) as client:
        athlete = client.get_athlete()

    assert athlete.garmin_upload_filters == []


def test_structured_upload_filter_follows_openapi_contract() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "id": "athlete-1",
                "timezone": "Europe/Paris",
                "icu_garmin_upload_filters": [
                    {
                        "id": 3,
                        "field_id": "type",
                        "operator": "=",
                        "value": {"value": "Run"},
                        "not": False,
                    }
                ],
            },
        )
    )
    with IntervalsIcuClient(_config(), transport=transport) as client:
        athlete = client.get_athlete()

    assert athlete.garmin_upload_filters[0].field_id == "type"
    assert athlete.garmin_upload_filters[0].value == {"value": "Run"}


def test_nullable_sport_setting_zones_follow_live_contract() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "types": ["Ride"],
                    "ftp": 250,
                    "pace_zones": None,
                }
            ],
        )
    )
    with IntervalsIcuClient(_config(), transport=transport) as client:
        settings = client.get_sport_settings()

    assert settings[0].pace_zones == []


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, IntervalsAuthenticationError),
        (403, IntervalsAuthorizationError),
        (422, IntervalsInvalidPayloadError),
    ],
)
def test_http_failures_are_distinct_and_secret_safe(status, error) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            status,
            text="never-log-this-test-key personal response body",
            headers={"X-Request-ID": "request-123"},
        )
    )
    with IntervalsIcuClient(_config(), transport=transport) as client:
        with pytest.raises(error) as captured:
            client.get_athlete()

    rendered = str(captured.value)
    assert "never-log-this-test-key" not in rendered
    assert "personal response body" not in rendered
    assert "request-123" in rendered


def test_rate_limit_honors_retry_after_and_then_succeeds() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(
            200,
            json={"id": "athlete-1", "timezone": "Europe/Paris"},
        )

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
        sleeper=sleeps.append,
        jitter=lambda _start, _end: 0,
    ) as client:
        assert client.get_athlete().id == "athlete-1"

    assert calls == 2
    assert sleeps == [3.0]


def test_exhausted_rate_limit_exposes_retry_without_body() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            429,
            text="private payload",
            headers={"Retry-After": "7"},
        )
    )
    sleeps: list[float] = []
    with IntervalsIcuClient(
        _config(),
        transport=transport,
        sleeper=sleeps.append,
        jitter=lambda _start, _end: 0,
    ) as client:
        with pytest.raises(IntervalsRateLimitError) as captured:
            client.get_athlete()

    assert captured.value.retry_after_seconds == 7
    assert "private payload" not in str(captured.value)
    assert sleeps == [7.0, 7.0, 7.0]


def test_http_date_retry_after_is_honored() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                headers={
                    "Date": "Tue, 28 Jul 2026 08:00:00 GMT",
                    "Retry-After": "Tue, 28 Jul 2026 08:00:05 GMT",
                },
            )
        return httpx.Response(200, json={"id": "athlete-1"})

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
        sleeper=sleeps.append,
        jitter=lambda _start, _end: 0,
    ) as client:
        assert client.get_athlete().id == "athlete-1"

    assert sleeps == [5.0]


def test_transient_transport_and_server_errors_retry_reads() -> None:
    outcomes: list[str] = ["connect", "server", "ok"]
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        outcome = outcomes.pop(0)
        if outcome == "connect":
            raise httpx.ConnectError("temporary", request=request)
        if outcome == "server":
            return httpx.Response(503)
        return httpx.Response(200, json={"id": "athlete-1"})

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
        sleeper=sleeps.append,
        jitter=lambda _start, _end: 0,
    ) as client:
        assert client.get_athlete().id == "athlete-1"

    assert outcomes == []
    assert sleeps == [0.5, 1.0]


def test_mutating_request_is_never_retried_blindly() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    event = EventWriteDTO(
        uid="uid-1",
        external_id="resilio:v1:workout:test",
        type="Run",
        name="Test",
        description="- 10m easy",
        start_date_local="2026-07-28T07:00:00",
    )
    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(IntervalsTransportError):
            client.upsert_event(event)

    assert calls == 1


def test_exact_event_delete_explicitly_disables_related_deletion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/api/v1/athlete/0/events/42"
        assert request.url.params["others"] == "false"
        return httpx.Response(200, json={})

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as client:
        client.delete_event(42)


def test_exact_activity_delete_is_single_target_and_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "DELETE"
        assert request.url.path == "/api/v1/activity/manual-1"
        return httpx.Response(503, text="private body")

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(IntervalsTransportError) as captured:
            client.delete_activity("manual-1")

    assert calls == 1
    assert "private body" not in str(captured.value)


def test_malformed_activity_payload_is_rejected() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json=[{"id": "i1", "type": "Run", "elapsed_time": -1}],
        )
    )
    with IntervalsIcuClient(_config(), transport=transport) as client:
        with pytest.raises(IntervalsInvalidPayloadError):
            client.list_activities(date(2026, 1, 1), date(2026, 1, 2))


def test_original_file_is_binary_and_empty_content_is_rejected() -> None:
    responses = [httpx.Response(200, content=b"fixture-fit"), httpx.Response(200)]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/activity/a1/file"
        return responses.pop(0)

    with IntervalsIcuClient(
        _config(),
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.get_original_file("a1") == b"fixture-fit"
        with pytest.raises(IntervalsInvalidPayloadError, match="empty"):
            client.get_original_file("a1")


def test_hidden_activity_variant_is_explicit() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json=[
                {
                    "id": "hidden-1",
                    "start_date_local": "2026-01-02T08:00:00+01:00",
                    "_note": "Unavailable through this API",
                }
            ],
        )
    )
    with IntervalsIcuClient(_config(), transport=transport) as client:
        rows = client.list_activities(
            date(2026, 1, 1),
            date(2026, 1, 2),
        )

    assert rows[0].id == "hidden-1"
    assert rows[0].note == "Unavailable through this API"


def test_activity_list_accepts_summary_zone_duration_arrays() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json=[
                {
                    "id": "a1",
                    "type": "Run",
                    "name": "Run",
                    "start_date": "2026-07-28T05:00:00Z",
                    "start_date_local": "2026-07-28T07:00:00",
                    "elapsed_time": 3600,
                    "moving_time": 3500,
                    "icu_hr_zone_times": [600, 900, 1200, 800, 0, 0, 0],
                    "polarization_index": -0.34,
                }
            ],
        )
    )

    with IntervalsIcuClient(_config(), transport=transport) as client:
        rows = client.list_activities(
            date(2026, 7, 28),
            date(2026, 7, 28),
        )

    assert rows[0].id == "a1"
    assert rows[0].start_date_local == "2026-07-28T07:00:00"


def test_nullable_activity_intervals_follow_live_contract() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json=[
                {
                    "id": "a1",
                    "type": "Ride",
                    "name": "Ride",
                    "start_date": "2026-07-28T05:00:00Z",
                    "start_date_local": "2026-07-28T07:00:00",
                    "elapsed_time": 3600,
                    "moving_time": 3500,
                    "has_heartrate": None,
                    "icu_intervals": None,
                }
            ],
        )
    )
    with IntervalsIcuClient(_config(), transport=transport) as client:
        activities = client.get_activities(["a1"])

    assert activities[0].icu_intervals == []
