"""
Unit tests for M5 - Strava Integration module.

Tests OAuth flow, activity fetching, deduplication, rate limiting,
and error handling. Uses mocking for API calls.
"""

import pytest
from datetime import date, datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import httpx

from sports_coach_engine.core.strava import (
    initiate_oauth,
    exchange_code_for_tokens,
    refresh_access_token,
    get_valid_token,
    fetch_activities,
    fetch_activity_details,
    map_strava_to_raw,
    check_duplicate,
    create_manual_activity,
    sync_strava,
    SyncResult,
    StravaAuthError,
    StravaRateLimitError,
    StravaAPIError,
)
from sports_coach_engine.schemas.activity import (
    ActivitySource,
    RawActivity,
)
from sports_coach_engine.schemas.config import Config, Secrets, Settings


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture
def mock_config():
    """Create mock configuration with Strava credentials."""
    from sports_coach_engine.schemas.config import StravaSecrets

    strava_secrets = StravaSecrets(
        client_id="test_client_id",
        client_secret="test_client_secret",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expires_at=int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()),
    )
    secrets = Secrets(strava=strava_secrets)
    settings = Settings()
    return Config(secrets=secrets, settings=settings, loaded_at=datetime.now(timezone.utc))


@pytest.fixture
def sample_strava_activity():
    """Sample Strava activity JSON response."""
    return {
        "id": 123456789,
        "name": "Morning Run",
        "sport_type": "Run",
        "type": "Run",
        "start_date": "2026-01-12T07:30:00Z",
        "start_date_local": "2026-01-12T07:30:00Z",
        "moving_time": 2700,
        "distance": 8000.0,
        "total_elevation_gain": 50.0,
        "average_heartrate": 155.0,
        "max_heartrate": 170.0,
        "has_heartrate": True,
        "description": "Great run",
        "private_note": "Felt strong",
        "workout_type": None,
        "suffer_score": 42,
        "perceived_exertion": None,
        "map": {"summary_polyline": "abc123"},
        "gear_id": "g123",
        "device_name": "Garmin Forerunner 945",
    }


# ============================================================
# OAUTH TESTS (4 tests)
# ============================================================


class TestOAuth:
    """Tests for OAuth flow."""

    def test_initiate_oauth_generates_correct_url(self):
        """Should generate properly formatted authorization URL."""
        url = initiate_oauth("test_client_123")

        assert "https://www.strava.com/oauth/authorize" in url
        assert "client_id=test_client_123" in url
        assert "response_type=code" in url
        assert "scope=activity:read_all,profile:read_all" in url
        assert "redirect_uri=http://localhost" in url

    @patch("sports_coach_engine.core.strava.httpx.Client")
    def test_exchange_code_for_tokens_success(self, mock_client_class):
        """Should successfully exchange code for tokens."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": 1735812000,
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        tokens = exchange_code_for_tokens(
            "client_id", "client_secret", "auth_code"
        )

        assert tokens["access_token"] == "new_access_token"
        assert tokens["refresh_token"] == "new_refresh_token"
        assert tokens["expires_at"] == 1735812000

    @patch("sports_coach_engine.core.strava.httpx.Client")
    def test_refresh_access_token_success(self, mock_client_class):
        """Should successfully refresh expired token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_token",
            "refresh_token": "new_refresh_token",
            "expires_at": 1735812000,
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        tokens = refresh_access_token(
            "client_id", "client_secret", "old_refresh_token"
        )

        assert tokens["access_token"] == "refreshed_token"

    @patch("sports_coach_engine.core.strava.store_tokens")
    @patch("sports_coach_engine.core.strava.httpx.Client")
    def test_token_refresh_on_expiration(self, mock_client_class, mock_store_tokens, mock_config):
        """Should refresh token when it expires soon."""
        # Set token to expire in 2 minutes
        mock_config.secrets.strava.token_expires_at = int(
            (datetime.now(timezone.utc) + timedelta(minutes=2)).timestamp()
        )

        # Mock refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_token",
            "refresh_token": "new_refresh_token",
            "expires_at": int(
                (datetime.now(timezone.utc) + timedelta(hours=6)).timestamp()
            ),
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        token = get_valid_token(mock_config)

        # Should have refreshed and returned new token
        assert token == "refreshed_token"
        # Should have called store_tokens
        assert mock_store_tokens.called


# ============================================================
# ACTIVITY FETCHING TESTS (5 tests)
# ============================================================


class TestActivityFetching:
    """Tests for activity fetching."""

    @patch("sports_coach_engine.core.strava.httpx.Client")
    @patch("sports_coach_engine.core.strava.get_valid_token")
    def test_fetch_activities_success(self, mock_get_token, mock_client_class, mock_config):
        """Should fetch activity list successfully."""
        mock_get_token.return_value = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "name": "Run 1"},
            {"id": 2, "name": "Run 2"},
        ]

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        activities = fetch_activities(mock_config)

        assert len(activities) == 2
        assert activities[0]["name"] == "Run 1"

    @patch("sports_coach_engine.core.strava.httpx.Client")
    @patch("sports_coach_engine.core.strava.get_valid_token")
    def test_fetch_activities_with_pagination(self, mock_get_token, mock_client_class, mock_config):
        """Should handle pagination parameters correctly."""
        mock_get_token.return_value = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        fetch_activities(mock_config, page=2, per_page=100)

        # Verify pagination params were passed
        call_kwargs = mock_client.__enter__.return_value.get.call_args[1]
        assert call_kwargs["params"]["page"] == 2
        assert call_kwargs["params"]["per_page"] == 100

    @patch("sports_coach_engine.core.strava.httpx.Client")
    @patch("sports_coach_engine.core.strava.get_valid_token")
    def test_fetch_activities_rate_limit_error(self, mock_get_token, mock_client_class, mock_config):
        """Should raise StravaRateLimitError on 429 response."""
        mock_get_token.return_value = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers.get.return_value = "60"

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Retry decorator will retry 3 times, so we need to ensure all attempts fail
        with pytest.raises(StravaRateLimitError) as exc_info:
            fetch_activities(mock_config)

        assert exc_info.value.retry_after == 60

    @patch("sports_coach_engine.core.strava.httpx.Client")
    @patch("sports_coach_engine.core.strava.get_valid_token")
    def test_fetch_activity_details_success(self, mock_get_token, mock_client_class, mock_config, sample_strava_activity):
        """Should fetch full activity details."""
        mock_get_token.return_value = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_strava_activity

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        activity = fetch_activity_details(mock_config, "123456789")

        assert activity["id"] == 123456789
        assert activity["private_note"] == "Felt strong"

    @patch("sports_coach_engine.core.strava.httpx.Client")
    @patch("sports_coach_engine.core.strava.get_valid_token")
    def test_fetch_activities_auth_error(self, mock_get_token, mock_client_class, mock_config):
        """Should raise StravaAuthError on 401 response."""
        mock_get_token.return_value = "invalid_token"

        mock_response = Mock()
        mock_response.status_code = 401

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(StravaAuthError):
            fetch_activities(mock_config)


# ============================================================
# MAPPING TESTS (3 tests)
# ============================================================


class TestMapping:
    """Tests for Strava to RawActivity mapping."""

    def test_map_strava_to_raw_complete_activity(self, sample_strava_activity):
        """Should map all Strava fields to RawActivity."""
        raw = map_strava_to_raw(sample_strava_activity)

        assert raw.id == "strava_123456789"
        assert raw.source == ActivitySource.STRAVA
        assert raw.sport_type == "Run"
        assert raw.name == "Morning Run"
        assert raw.duration_seconds == 2700
        assert raw.distance_meters == 8000.0
        assert raw.average_hr == 155.0
        assert raw.has_hr_data is True
        assert raw.description == "Great run"
        assert raw.private_note == "Felt strong"
        assert raw.has_polyline is True

    def test_map_strava_to_raw_minimal_activity(self):
        """Should handle activity with minimal fields."""
        minimal_activity = {
            "id": 999,
            "name": "Short Run",
            "sport_type": "Run",
            "start_date": "2026-01-12T07:30:00Z",
            "start_date_local": "2026-01-12T07:30:00Z",
            "moving_time": 1800,
        }

        raw = map_strava_to_raw(minimal_activity)

        assert raw.id == "strava_999"
        assert raw.duration_seconds == 1800
        assert raw.distance_meters is None
        assert raw.average_hr is None
        assert raw.has_hr_data is False

    def test_map_strava_preserves_timestamps(self, sample_strava_activity):
        """Should correctly parse and preserve timestamps."""
        raw = map_strava_to_raw(sample_strava_activity)

        assert raw.date == date(2026, 1, 12)
        assert raw.start_time.hour == 7
        assert raw.start_time.minute == 30


# ============================================================
# DEDUPLICATION TESTS (4 tests)
# ============================================================


class TestDeduplication:
    """Tests for activity deduplication."""

    def test_duplicate_detection_primary_key_match(self):
        """Should detect duplicate by primary key (source, id)."""
        activity1 = RawActivity(
            id="strava_123",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Run",
            date=date(2026, 1, 12),
            duration_seconds=1800,
        )

        activity2 = RawActivity(
            id="strava_123",  # Same ID
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Different Name",  # Different name
            date=date(2026, 1, 12),
            duration_seconds=1900,  # Different duration
        )

        duplicate = check_duplicate(activity2, [activity1])
        assert duplicate is activity1

    def test_duplicate_detection_fuzzy_match(self):
        """Should detect duplicate by fuzzy matching."""
        activity1 = RawActivity(
            id="manual_abc",
            source=ActivitySource.MANUAL,
            sport_type="Run",
            name="Morning Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 7, 30, tzinfo=timezone.utc),
            duration_seconds=1800,
        )

        # Similar activity from different source
        activity2 = RawActivity(
            id="strava_456",  # Different ID
            source=ActivitySource.STRAVA,  # Different source
            sport_type="Run",
            name="Run",
            date=date(2026, 1, 12),  # Same date
            start_time=datetime(2026, 1, 12, 7, 35, tzinfo=timezone.utc),  # Within 30min
            duration_seconds=1850,  # Within 5min (50sec difference)
        )

        duplicate = check_duplicate(activity2, [activity1])
        assert duplicate is activity1

    def test_no_duplicate_different_date(self):
        """Should not match activities on different dates."""
        activity1 = RawActivity(
            id="run_1",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Run",
            date=date(2026, 1, 12),
            duration_seconds=1800,
        )

        activity2 = RawActivity(
            id="run_2",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Run",
            date=date(2026, 1, 13),  # Different date
            duration_seconds=1800,
        )

        duplicate = check_duplicate(activity2, [activity1])
        assert duplicate is None

    def test_no_duplicate_time_difference_too_large(self):
        """Should not match if start time difference >30 minutes."""
        activity1 = RawActivity(
            id="run_1",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 7, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
        )

        activity2 = RawActivity(
            id="run_2",
            source=ActivitySource.MANUAL,
            sport_type="Run",
            name="Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 8, 0, tzinfo=timezone.utc),  # 60min difference
            duration_seconds=1800,
        )

        duplicate = check_duplicate(activity2, [activity1])
        assert duplicate is None


# ============================================================
# MANUAL ACTIVITY TESTS (3 tests)
# ============================================================


class TestManualActivity:
    """Tests for manual activity creation."""

    def test_create_manual_activity_with_datetime(self):
        """Should create manual activity from datetime."""
        start_time = datetime(2026, 1, 12, 7, 30, tzinfo=timezone.utc)

        activity = create_manual_activity(
            sport_type="Run",
            date=start_time,
            duration_minutes=45,
            distance_km=8.0,
            perceived_exertion=6,
            description="Good run",
        )

        assert activity.source == ActivitySource.MANUAL
        assert activity.id.startswith("manual_")
        assert activity.sport_type == "Run"
        assert activity.duration_seconds == 2700  # 45 * 60
        assert activity.distance_meters == 8000.0  # 8.0 km * 1000
        assert activity.perceived_exertion == 6
        assert activity.description == "Good run"
        assert activity.has_hr_data is False
        assert activity.has_polyline is False

    def test_create_manual_activity_with_date(self):
        """Should create manual activity from date only."""
        activity_date = date(2026, 1, 12)

        activity = create_manual_activity(
            sport_type="Climb",
            date=activity_date,
            duration_minutes=120,
        )

        assert activity.date == activity_date
        assert activity.start_time.date() == activity_date
        assert activity.duration_seconds == 7200

    def test_manual_activity_generates_unique_ids(self):
        """Should generate unique IDs for each manual activity."""
        activity1 = create_manual_activity(
            sport_type="Run",
            date=date(2026, 1, 12),
            duration_minutes=30,
        )

        activity2 = create_manual_activity(
            sport_type="Run",
            date=date(2026, 1, 12),
            duration_minutes=30,
        )

        assert activity1.id != activity2.id
        assert activity1.id.startswith("manual_")
        assert activity2.id.startswith("manual_")


# ============================================================
# ERROR HANDLING TESTS (3 tests)
# ============================================================


class TestErrorHandling:
    """Tests for error handling."""

    @patch("sports_coach_engine.core.strava.httpx.Client")
    def test_token_exchange_failure(self, mock_client_class):
        """Should raise StravaAuthError on failed token exchange."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(StravaAuthError, match="Token exchange failed"):
            exchange_code_for_tokens("client_id", "client_secret", "bad_code")

    @patch("sports_coach_engine.core.strava.httpx.Client")
    def test_token_refresh_failure(self, mock_client_class):
        """Should raise StravaAuthError on failed token refresh."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(StravaAuthError, match="Token refresh failed"):
            refresh_access_token("client_id", "client_secret", "bad_refresh")

    @patch("sports_coach_engine.core.strava.httpx.Client")
    @patch("sports_coach_engine.core.strava.get_valid_token")
    def test_api_error_on_non_200_response(self, mock_get_token, mock_client_class, mock_config):
        """Should raise error on non-200 response (wrapped in RetryError after retries)."""
        from tenacity import RetryError

        mock_get_token.return_value = "valid_token"

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Retry decorator will retry 3 times, then wrap in RetryError
        with pytest.raises(RetryError):
            fetch_activities(mock_config)

    @patch("sports_coach_engine.core.strava.httpx.Client")
    def test_http_error_during_token_exchange(self, mock_client_class):
        """Should raise StravaAuthError on HTTP errors during token exchange."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.side_effect = httpx.HTTPError("Network error")
        mock_client_class.return_value = mock_client

        with pytest.raises(StravaAuthError, match="HTTP error during token exchange"):
            exchange_code_for_tokens("client_id", "client_secret", "code")

    @patch("sports_coach_engine.core.strava.httpx.Client")
    def test_http_error_during_token_refresh(self, mock_client_class):
        """Should raise StravaAuthError on HTTP errors during token refresh."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.side_effect = httpx.HTTPError("Network error")
        mock_client_class.return_value = mock_client

        with pytest.raises(StravaAuthError, match="HTTP error during token refresh"):
            refresh_access_token("client_id", "client_secret", "refresh_token")


# ============================================================
# SYNC TESTS
# ============================================================


class TestSync:
    """Tests for sync workflow."""

    @patch("sports_coach_engine.core.strava.fetch_activity_details")
    @patch("sports_coach_engine.core.strava.fetch_activities")
    @patch("sports_coach_engine.core.strava.time.sleep")
    def test_sync_strava_success(
        self, mock_sleep, mock_fetch_activities, mock_fetch_details, mock_config
    ):
        """Should successfully sync activities from Strava."""
        # Mock fetch_activities to return 2 activities on first page, empty on second
        mock_fetch_activities.side_effect = [
            [
                {"id": 123, "name": "Morning Run", "sport_type": "Run"},
                {"id": 456, "name": "Evening Climb", "sport_type": "RockClimbing"},
            ],
            [],  # Empty second page
        ]

        # Mock fetch_activity_details to return full details
        mock_fetch_details.side_effect = [
            {
                "id": 123,
                "name": "Morning Run",
                "sport_type": "Run",
                "type": "Run",
                "start_date": "2026-01-12T07:30:00Z",
                "start_date_local": "2026-01-12T07:30:00Z",
                "moving_time": 2700,
                "distance": 8000.0,
            },
            {
                "id": 456,
                "name": "Evening Climb",
                "sport_type": "RockClimbing",
                "type": "RockClimbing",
                "start_date": "2026-01-12T19:00:00Z",
                "start_date_local": "2026-01-12T19:00:00Z",
                "moving_time": 5400,
            },
        ]

        activities, result = sync_strava(mock_config, lookback_days=30)

        assert len(activities) == 2
        assert result.activities_fetched == 2
        assert result.activities_new == 2
        assert result.activities_skipped == 0
        assert len(result.errors) == 0

    @patch("sports_coach_engine.core.strava.fetch_activity_details")
    @patch("sports_coach_engine.core.strava.fetch_activities")
    @patch("sports_coach_engine.core.strava.time.sleep")
    def test_sync_strava_with_errors(
        self, mock_sleep, mock_fetch_activities, mock_fetch_details, mock_config
    ):
        """Should handle errors gracefully and continue sync."""
        mock_fetch_activities.side_effect = [
            [
                {"id": 123, "name": "Good Activity", "sport_type": "Run"},
                {"id": 456, "name": "Bad Activity", "sport_type": "Run"},
            ],
            [],
        ]

        # First activity succeeds, second fails
        mock_fetch_details.side_effect = [
            {
                "id": 123,
                "name": "Good Activity",
                "sport_type": "Run",
                "type": "Run",
                "start_date": "2026-01-12T07:30:00Z",
                "start_date_local": "2026-01-12T07:30:00Z",
                "moving_time": 2700,
            },
            Exception("API error"),
        ]

        activities, result = sync_strava(mock_config)

        assert len(activities) == 1  # Only successful activity
        assert result.activities_fetched == 2
        assert result.activities_new == 1
        assert result.activities_skipped == 1
        assert len(result.errors) == 1
        assert "456" in result.errors[0]

    @patch("sports_coach_engine.core.strava.load_config")
    def test_sync_strava_loads_config_if_not_provided(self, mock_load_config, mock_config):
        """Should load config if not provided."""
        mock_load_config.return_value = mock_config

        with patch("sports_coach_engine.core.strava.fetch_activities") as mock_fetch:
            mock_fetch.return_value = []
            sync_strava(config=None)
            mock_load_config.assert_called_once()


# ============================================================
# TOKEN STORAGE TESTS
# ============================================================


class TestTokenStorage:
    """Tests for token storage."""

    def test_store_tokens_updates_config(self, mock_config):
        """Should update config object with new tokens."""
        from sports_coach_engine.core.strava import store_tokens

        tokens = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_at": 1735900000,
        }

        store_tokens(mock_config, tokens)

        assert mock_config.secrets.strava.access_token == "new_access"
        assert mock_config.secrets.strava.refresh_token == "new_refresh"
        assert mock_config.secrets.strava.token_expires_at == 1735900000
