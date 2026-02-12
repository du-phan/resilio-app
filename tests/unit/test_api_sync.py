"""
Unit tests for API sync operations (api/sync.py).
"""

from datetime import date, datetime
from unittest.mock import Mock, patch

import pytest

from resilio.api.sync import SyncError, log_activity, sync_strava
from resilio.core.config import ConfigError
from resilio.core.workflows import ManualActivityResult, WorkflowError
from resilio.schemas.activity import NormalizedActivity
from resilio.schemas.config import ConfigErrorType
from resilio.schemas.sync import SyncPhase, SyncReport


@pytest.fixture
def mock_log():
    return Mock()


@pytest.fixture
def mock_sync_report() -> SyncReport:
    return SyncReport(
        activities_imported=2,
        activities_skipped=1,
        activities_failed=0,
        laps_fetched=1,
        laps_skipped_age=0,
        lap_fetch_failures=0,
        phase=SyncPhase.DONE,
        rate_limited=False,
        errors=[],
    )


@pytest.fixture
def mock_activity():
    activity = Mock(spec=NormalizedActivity)
    activity.sport_type = "run"
    activity.duration_minutes = 45
    return activity


@pytest.fixture
def mock_manual_result(mock_activity):
    return ManualActivityResult(
        success=True,
        warnings=[],
        activity=mock_activity,
        metrics_updated=None,
    )


class TestSyncStrava:
    @patch("resilio.api.sync.load_config")
    @patch("resilio.api.sync.run_sync_workflow")
    def test_sync_strava_success(self, mock_workflow, mock_config, mock_log, mock_sync_report):
        mock_config.return_value = Mock()
        mock_workflow.return_value = mock_sync_report

        result = sync_strava()

        assert isinstance(result, SyncReport)
        assert result.activities_imported == 2
        mock_workflow.assert_called_once()

    @patch("resilio.api.sync.load_config")
    def test_sync_strava_config_error(self, mock_config, mock_log):
        mock_config.return_value = ConfigError(
            error_type=ConfigErrorType.FILE_NOT_FOUND,
            message="Config not found",
        )

        result = sync_strava()

        assert isinstance(result, SyncError)
        assert result.error_type == "config"

    @patch("resilio.api.sync.load_config")
    @patch("resilio.api.sync.run_sync_workflow")
    def test_sync_strava_workflow_error(self, mock_workflow, mock_config, mock_log):
        mock_config.return_value = Mock()
        mock_workflow.side_effect = WorkflowError("Network connection failed")

        result = sync_strava()

        assert isinstance(result, SyncError)
        assert result.error_type == "network"

    @patch("resilio.api.sync.load_config")
    @patch("resilio.api.sync.run_sync_workflow")
    def test_sync_strava_with_since_parameter(
        self,
        mock_workflow,
        mock_config,
        mock_log,
        mock_sync_report,
    ):
        mock_config.return_value = Mock()
        mock_workflow.return_value = mock_sync_report
        since_date = datetime(2024, 1, 1)

        _ = sync_strava(since=since_date)

        mock_workflow.assert_called_once()
        assert mock_workflow.call_args.kwargs["since"] == since_date

    @patch("resilio.api.sync.load_config")
    @patch("resilio.api.sync.run_sync_workflow")
    def test_sync_strava_auth_error_classification(self, mock_workflow, mock_config, mock_log):
        mock_config.return_value = Mock()
        mock_workflow.side_effect = WorkflowError("Strava auth token expired")

        result = sync_strava()
        assert isinstance(result, SyncError)
        assert result.error_type == "auth"

    @patch("resilio.api.sync.load_config")
    @patch("resilio.api.sync.run_sync_workflow")
    def test_sync_strava_rate_limit_error_classification(self, mock_workflow, mock_config, mock_log):
        mock_config.return_value = Mock()
        mock_workflow.side_effect = WorkflowError("API rate limit exceeded")

        result = sync_strava()
        assert isinstance(result, SyncError)
        assert result.error_type == "rate_limit"


class TestLogActivity:
    @patch("resilio.api.sync.run_manual_activity_workflow")
    def test_log_activity_success(self, mock_workflow, mock_log, mock_manual_result):
        mock_workflow.return_value = mock_manual_result

        result = log_activity(
            sport_type="run",
            duration_minutes=45,
            rpe=6,
            notes="Felt good",
        )

        assert isinstance(result, NormalizedActivity)
        assert result.sport_type == "run"
        mock_workflow.assert_called_once()

    @patch("resilio.api.sync.run_manual_activity_workflow")
    def test_log_activity_with_distance(self, mock_workflow, mock_log, mock_manual_result):
        mock_workflow.return_value = mock_manual_result

        _ = log_activity(
            sport_type="run",
            duration_minutes=45,
            distance_km=10.5,
        )

        assert mock_workflow.call_args.kwargs["distance_km"] == 10.5

    @patch("resilio.api.sync.run_manual_activity_workflow")
    def test_log_activity_defaults_to_today(self, mock_workflow, mock_log, mock_manual_result):
        mock_workflow.return_value = mock_manual_result

        _ = log_activity(sport_type="run", duration_minutes=45)

        assert mock_workflow.call_args.kwargs["activity_date"] == date.today()

    @patch("resilio.api.sync.run_manual_activity_workflow")
    def test_log_activity_workflow_failure(self, mock_workflow, mock_log):
        mock_workflow.return_value = ManualActivityResult(
            success=False,
            warnings=["Validation error"],
            activity=None,
            metrics_updated=None,
        )

        result = log_activity(sport_type="run", duration_minutes=45)

        assert isinstance(result, SyncError)
        assert result.error_type == "validation"

    @patch("resilio.api.sync.run_manual_activity_workflow")
    def test_log_activity_exception_handling(self, mock_workflow, mock_log):
        mock_workflow.side_effect = Exception("Unexpected error")

        result = log_activity(sport_type="run", duration_minutes=45)

        assert isinstance(result, SyncError)
        assert result.error_type == "unknown"
