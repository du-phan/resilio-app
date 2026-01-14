"""
Unit tests for API - Sync Operations (api/sync.py).

Tests sync_strava() and log_activity() with mocked workflows.
"""

import pytest
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock

from sports_coach_engine.api.sync import (
    sync_strava,
    log_activity,
    SyncError,
)
from sports_coach_engine.core.workflows import SyncWorkflowResult, ManualActivityResult
from sports_coach_engine.schemas.enrichment import SyncSummary
from sports_coach_engine.schemas.activity import NormalizedActivity
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_activity():
    """Mock NormalizedActivity with calculated loads."""
    activity = Mock(spec=NormalizedActivity)
    activity.sport_type = "Run"
    activity.duration_minutes = 45
    activity.date = date.today()
    activity.calculated = Mock()
    activity.calculated.systemic_load_au = 300.0
    activity.calculated.lower_body_load_au = 300.0
    return activity


@pytest.fixture
def mock_sync_result(mock_activity):
    """Mock successful sync workflow result."""
    result = Mock(spec=SyncWorkflowResult)
    result.success = True
    result.warnings = []
    result.partial_failure = False
    result.activities_imported = [mock_activity]
    result.activities_failed = 0
    result.metrics_updated = Mock()
    result.suggestions_generated = []
    result.memories_extracted = []
    return result


@pytest.fixture
def mock_manual_result(mock_activity):
    """Mock successful manual activity result."""
    result = Mock(spec=ManualActivityResult)
    result.success = True
    result.warnings = []
    result.activity = mock_activity
    result.metrics_updated = Mock()
    return result


# ============================================================
# SYNC_STRAVA TESTS
# ============================================================


class TestSyncStrava:
    """Test sync_strava() function."""

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    @patch("sports_coach_engine.api.sync.run_sync_workflow")
    @patch("sports_coach_engine.api.sync.enrich_metrics")
    def test_sync_strava_success(
        self, mock_enrich, mock_workflow, mock_config, mock_log, mock_sync_result
    ):
        """Test successful Strava sync."""
        # Mock config
        mock_config.return_value = Mock()

        # Mock successful workflow
        mock_workflow.return_value = mock_sync_result

        # Mock enrichment
        mock_enrich.return_value = Mock()

        result = sync_strava()

        # Should return SyncSummary
        assert isinstance(result, SyncSummary)
        assert result.activities_imported == 1
        assert result.activities_failed == 0

        # Verify workflow was called
        mock_workflow.assert_called_once()

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    def test_sync_strava_config_error(self, mock_config, mock_log):
        """Test sync failure due to config error."""
        # Mock config error
        mock_config.return_value = RepoError(RepoErrorType.FILE_NOT_FOUND, "Config not found")

        result = sync_strava()

        # Should return SyncError
        assert isinstance(result, SyncError)
        assert result.error_type == "config"
        assert "Config" in result.message

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    @patch("sports_coach_engine.api.sync.run_sync_workflow")
    def test_sync_strava_workflow_failure(self, mock_workflow, mock_config, mock_log):
        """Test sync failure in workflow."""
        # Mock config
        mock_config.return_value = Mock()

        # Mock workflow failure
        failed_result = Mock()
        failed_result.success = False
        failed_result.warnings = ["API rate limit"]
        failed_result.partial_failure = False
        failed_result.activities_imported = []
        failed_result.activities_failed = 0

        mock_workflow.return_value = failed_result

        result = sync_strava()

        # Should return SyncError
        assert isinstance(result, SyncError)
        assert result.error_type in ["partial", "unknown"]

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    @patch("sports_coach_engine.api.sync.run_sync_workflow")
    def test_sync_strava_with_since_parameter(self, mock_workflow, mock_config, mock_log, mock_sync_result):
        """Test sync with 'since' parameter."""
        mock_config.return_value = Mock()
        mock_workflow.return_value = mock_sync_result

        since_date = datetime(2024, 1, 1)
        result = sync_strava(since=since_date)

        # Verify 'since' was passed to workflow
        mock_workflow.assert_called_once()
        call_args = mock_workflow.call_args
        assert call_args.kwargs.get("since") == since_date

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    @patch("sports_coach_engine.api.sync.run_sync_workflow")
    @patch("sports_coach_engine.api.sync.enrich_metrics")
    def test_sync_strava_enrichment_failure_fallback(
        self, mock_enrich, mock_workflow, mock_config, mock_log, mock_sync_result
    ):
        """Test sync falls back to basic summary if enrichment fails."""
        mock_config.return_value = Mock()
        mock_workflow.return_value = mock_sync_result
        mock_enrich.side_effect = Exception("Enrichment failed")

        result = sync_strava()

        # Should still return SyncSummary (basic version)
        assert isinstance(result, SyncSummary)
        # Metrics won't be enriched but basic data should be present
        assert result.activities_imported == 1


# ============================================================
# LOG_ACTIVITY TESTS
# ============================================================


class TestLogActivity:
    """Test log_activity() function."""

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.run_manual_activity_workflow")
    def test_log_activity_success(self, mock_workflow, mock_log, mock_manual_result):
        """Test successful manual activity logging."""
        mock_workflow.return_value = mock_manual_result

        result = log_activity(
            sport_type="run",
            duration_minutes=45,
            rpe=6,
            notes="Felt good",
        )

        # Should return NormalizedActivity
        assert isinstance(result, NormalizedActivity)
        assert result.sport_type == "Run"

        # Verify workflow was called with correct params
        mock_workflow.assert_called_once()
        call_args = mock_workflow.call_args
        assert call_args.kwargs["sport_type"] == "run"
        assert call_args.kwargs["duration_minutes"] == 45
        assert call_args.kwargs["rpe"] == 6

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.run_manual_activity_workflow")
    def test_log_activity_with_distance(self, mock_workflow, mock_log, mock_manual_result):
        """Test logging activity with distance."""
        mock_workflow.return_value = mock_manual_result

        result = log_activity(
            sport_type="run",
            duration_minutes=45,
            distance_km=10.5,
        )

        # Verify distance was passed
        call_args = mock_workflow.call_args
        assert call_args.kwargs["distance_km"] == 10.5

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.run_manual_activity_workflow")
    def test_log_activity_defaults_to_today(self, mock_workflow, mock_log, mock_manual_result):
        """Test that activity date defaults to today."""
        mock_workflow.return_value = mock_manual_result

        result = log_activity(
            sport_type="run",
            duration_minutes=45,
        )

        # Verify date defaults to today
        call_args = mock_workflow.call_args
        assert call_args.kwargs["activity_date"] == date.today()

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.run_manual_activity_workflow")
    def test_log_activity_workflow_failure(self, mock_workflow, mock_log):
        """Test manual activity logging with workflow failure."""
        # Mock workflow failure
        failed_result = Mock()
        failed_result.success = False
        failed_result.warnings = ["Validation error"]
        failed_result.activity = None

        mock_workflow.return_value = failed_result

        result = log_activity(
            sport_type="run",
            duration_minutes=45,
        )

        # Should return SyncError
        assert isinstance(result, SyncError)
        assert result.error_type == "validation"

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.run_manual_activity_workflow")
    def test_log_activity_exception_handling(self, mock_workflow, mock_log):
        """Test exception handling in manual activity logging."""
        # Mock exception
        mock_workflow.side_effect = Exception("Unexpected error")

        result = log_activity(
            sport_type="run",
            duration_minutes=45,
        )

        # Should return SyncError
        assert isinstance(result, SyncError)
        assert result.error_type == "unknown"


# ============================================================
# ERROR CLASSIFICATION TESTS
# ============================================================


class TestErrorClassification:
    """Test error classification helper."""

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    @patch("sports_coach_engine.api.sync.run_sync_workflow")
    def test_strava_error_classification(self, mock_workflow, mock_config, mock_log):
        """Test Strava auth errors are classified correctly."""
        from sports_coach_engine.core.workflows import WorkflowError

        mock_config.return_value = Mock()
        mock_workflow.side_effect = WorkflowError("Strava auth token expired")

        result = sync_strava()

        assert isinstance(result, SyncError)
        assert result.error_type == "auth"

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    @patch("sports_coach_engine.api.sync.run_sync_workflow")
    def test_rate_limit_error_classification(self, mock_workflow, mock_config, mock_log):
        """Test rate limit errors are classified correctly."""
        from sports_coach_engine.core.workflows import WorkflowError

        mock_config.return_value = Mock()
        mock_workflow.side_effect = WorkflowError("API rate limit exceeded")

        result = sync_strava()

        assert isinstance(result, SyncError)
        assert result.error_type == "rate_limit"

    @patch("sports_coach_engine.api.sync.log_message")
    @patch("sports_coach_engine.api.sync.load_config")
    @patch("sports_coach_engine.api.sync.run_sync_workflow")
    def test_network_error_classification(self, mock_workflow, mock_config, mock_log):
        """Test network errors are classified correctly."""
        from sports_coach_engine.core.workflows import WorkflowError

        mock_config.return_value = Mock()
        mock_workflow.side_effect = WorkflowError("Network connection failed")

        result = sync_strava()

        assert isinstance(result, SyncError)
        assert result.error_type == "network"
