"""
Unit tests for Coach API (api/coach.py).

Tests get_todays_workout(), get_weekly_status(), and get_training_status().
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

from sports_coach_engine.api.coach import (
    get_todays_workout,
    get_weekly_status,
    get_training_status,
    CoachError,
    WeeklyStatus,
)
from sports_coach_engine.schemas.enrichment import EnrichedWorkout, EnrichedMetrics
from sports_coach_engine.schemas.metrics import DailyMetrics
from sports_coach_engine.schemas.profile import AthleteProfile
from sports_coach_engine.schemas.plan import WorkoutPrescription
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_workout():
    """Mock WorkoutPrescription."""
    workout = Mock(spec=WorkoutPrescription)
    workout.workout_id = "2024-01-15_tempo"
    workout.date = date.today()
    workout.workout_type = "tempo"
    workout.duration_minutes = 45
    workout.target_rpe = 7
    return workout


@pytest.fixture
def mock_enriched_workout():
    """Mock EnrichedWorkout."""
    enriched = Mock(spec=EnrichedWorkout)
    enriched.workout_type_display = "Tempo Run"
    enriched.duration_minutes = 45
    enriched.target_rpe = 7
    return enriched


@pytest.fixture
def mock_daily_metrics():
    """Mock DailyMetrics."""
    metrics = Mock(spec=DailyMetrics)
    metrics.date = date.today()
    metrics.ctl_atl = Mock()
    metrics.ctl_atl.ctl = 44.0
    metrics.ctl_atl.tsb = -8.0
    metrics.readiness = Mock()
    metrics.readiness.score = 68
    return metrics


@pytest.fixture
def mock_profile():
    """Mock AthleteProfile."""
    profile = Mock(spec=AthleteProfile)
    profile.name = "Test Athlete"
    return profile


# ============================================================
# GET_TODAYS_WORKOUT TESTS
# ============================================================


class TestGetTodaysWorkout:
    """Test get_todays_workout() function."""

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach.run_adaptation_check")
    @patch("sports_coach_engine.api.coach.enrich_workout")
    def test_get_todays_workout_success(
        self,
        mock_enrich,
        mock_workflow,
        mock_repo_cls,
        mock_log,
        mock_workout,
        mock_enriched_workout,
        mock_daily_metrics,
        mock_profile,
    ):
        """Test successful workout retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock successful workflow
        mock_result = Mock()
        mock_result.success = True
        mock_result.workout = mock_workout
        mock_result.triggers = []
        mock_result.warnings = []
        mock_workflow.return_value = mock_result

        # Mock loading metrics and profile
        mock_repo.read_yaml.side_effect = [mock_daily_metrics, mock_profile]

        # Mock enrichment
        mock_enrich.return_value = mock_enriched_workout

        result = get_todays_workout()

        # Should return EnrichedWorkout
        assert isinstance(result, Mock)
        assert result == mock_enriched_workout

        # Verify workflow was called
        mock_workflow.assert_called_once()

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach.run_adaptation_check")
    def test_get_todays_workout_no_workout(self, mock_workflow, mock_repo_cls, mock_log):
        """Test workout retrieval when no workout scheduled."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock workflow with no workout
        mock_result = Mock()
        mock_result.success = False
        mock_result.workout = None
        mock_result.warnings = ["No workout scheduled"]
        mock_workflow.return_value = mock_result

        result = get_todays_workout()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "not_found"
        assert "No workout scheduled" in result.message

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach.run_adaptation_check")
    def test_get_todays_workout_no_plan(self, mock_workflow, mock_repo_cls, mock_log):
        """Test workout retrieval when no plan exists."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock workflow failure due to no plan
        mock_result = Mock()
        mock_result.success = False
        mock_result.workout = None
        mock_result.warnings = ["No plan found"]
        mock_workflow.return_value = mock_result

        result = get_todays_workout()

        # Should return CoachError with no_plan type
        assert isinstance(result, CoachError)
        assert result.error_type == "no_plan"
        assert "No training plan found" in result.message

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach.run_adaptation_check")
    def test_get_todays_workout_no_metrics(
        self, mock_workflow, mock_repo_cls, mock_log, mock_workout
    ):
        """Test workout retrieval when no metrics available."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock successful workflow
        mock_result = Mock()
        mock_result.success = True
        mock_result.workout = mock_workout
        mock_result.triggers = []
        mock_workflow.return_value = mock_result

        # Mock no metrics available
        mock_repo.read_yaml.return_value = None

        result = get_todays_workout()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "insufficient_data"
        assert "No metrics available" in result.message

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach.run_adaptation_check")
    def test_get_todays_workout_workflow_error(self, mock_workflow, mock_repo_cls, mock_log):
        """Test workout retrieval with workflow error."""
        from sports_coach_engine.core.workflows import WorkflowError

        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock workflow error
        mock_workflow.side_effect = WorkflowError("Workflow failed")

        result = get_todays_workout()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "unknown"
        assert "Failed to check workout" in result.message

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach.run_adaptation_check")
    def test_get_todays_workout_custom_date(
        self, mock_workflow, mock_repo_cls, mock_log, mock_workout, mock_daily_metrics, mock_profile
    ):
        """Test workout retrieval for custom date."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock successful workflow
        mock_result = Mock()
        mock_result.success = True
        mock_result.workout = mock_workout
        mock_result.triggers = []
        mock_workflow.return_value = mock_result

        # Mock loading metrics and profile
        mock_repo.read_yaml.side_effect = [mock_daily_metrics, mock_profile]

        # Mock enrichment
        from sports_coach_engine.api.coach import enrich_workout
        with patch("sports_coach_engine.api.coach.enrich_workout") as mock_enrich:
            mock_enrich.return_value = Mock()

            target_date = date.today() + timedelta(days=1)
            result = get_todays_workout(target_date=target_date)

            # Verify workflow was called with custom date
            mock_workflow.assert_called_once()
            call_args = mock_workflow.call_args
            assert call_args.kwargs["target_date"] == target_date


# ============================================================
# GET_WEEKLY_STATUS TESTS
# ============================================================


class TestGetWeeklyStatus:
    """Test get_weekly_status() function."""

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    def test_get_weekly_status_success(self, mock_repo_cls, mock_log):
        """Test successful weekly status retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock plan with planned workouts
        mock_plan = Mock()
        mock_plan.weeks = []
        mock_week = Mock()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        mock_week.week_start = week_start
        mock_week.week_end = week_start + timedelta(days=6)
        mock_week.workouts = [Mock(), Mock(), Mock()]  # 3 planned workouts
        mock_plan.weeks.append(mock_week)

        # Mock activities (no activities this week)
        def mock_read_yaml(path, schema, options):
            if "data/plans/current_plan" in path:
                return mock_plan
            elif "data/metrics/daily" in path:
                metrics = Mock()
                metrics.ctl_atl = Mock()
                metrics.ctl_atl.ctl = 44.0
                metrics.ctl_atl.tsb = -8.0
                metrics.readiness = Mock()
                metrics.readiness.score = 68
                return metrics
            else:
                return None

        mock_repo.read_yaml.side_effect = mock_read_yaml
        mock_repo.list_files.return_value = []

        result = get_weekly_status()

        # Should return WeeklyStatus
        assert isinstance(result, WeeklyStatus)
        assert result.planned_workouts == 3
        assert result.completed_workouts == 0
        assert result.completion_rate == 0.0

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    def test_get_weekly_status_no_plan(self, mock_repo_cls, mock_log):
        """Test weekly status when no plan exists."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock no plan
        def mock_read_yaml(path, schema, options):
            if "data/plans/current_plan" in path:
                return RepoError(RepoErrorType.FILE_NOT_FOUND, "Plan not found")
            elif "data/metrics/daily" in path:
                metrics = Mock()
                metrics.ctl_atl = Mock()
                metrics.ctl_atl.ctl = 44.0
                metrics.ctl_atl.tsb = -8.0
                return metrics
            else:
                return None

        mock_repo.read_yaml.side_effect = mock_read_yaml
        mock_repo.list_files.return_value = []

        result = get_weekly_status()

        # Should return WeeklyStatus with 0 planned workouts
        assert isinstance(result, WeeklyStatus)
        assert result.planned_workouts == 0


# ============================================================
# GET_TRAINING_STATUS TESTS
# ============================================================


class TestGetTrainingStatus:
    """Test get_training_status() function."""

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach._find_latest_metrics_date")
    @patch("sports_coach_engine.api.coach.enrich_metrics")
    def test_get_training_status_success(
        self, mock_enrich, mock_find_date, mock_repo_cls, mock_log, mock_daily_metrics
    ):
        """Test successful training status retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock finding latest metrics
        mock_find_date.return_value = date.today()

        # Mock loading metrics
        mock_repo.read_yaml.return_value = mock_daily_metrics

        # Mock enrichment
        mock_enriched = Mock(spec=EnrichedMetrics)
        mock_enriched.ctl = Mock()
        mock_enriched.ctl.formatted_value = "44"
        mock_enriched.tsb = Mock()
        mock_enriched.tsb.formatted_value = "-8"
        mock_enriched.readiness = Mock()
        mock_enriched.readiness.formatted_value = "68"
        mock_enrich.return_value = mock_enriched

        result = get_training_status()

        # Should return EnrichedMetrics
        assert isinstance(result, Mock)
        assert result == mock_enriched

        # Verify enrichment was called
        mock_enrich.assert_called_once()

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach._find_latest_metrics_date")
    def test_get_training_status_no_data(self, mock_find_date, mock_repo_cls, mock_log):
        """Test training status when no data available."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock no metrics found
        mock_find_date.return_value = None

        result = get_training_status()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "not_found"
        assert "No training data available" in result.message

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach._find_latest_metrics_date")
    def test_get_training_status_load_error(self, mock_find_date, mock_repo_cls, mock_log):
        """Test training status with metrics load error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_find_date.return_value = date.today()

        # Mock load error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.VALIDATION_ERROR, "Load failed")

        result = get_training_status()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "validation"
        assert "Failed to load metrics" in result.message

    @patch("sports_coach_engine.api.coach.log_message")
    @patch("sports_coach_engine.api.coach.RepositoryIO")
    @patch("sports_coach_engine.api.coach._find_latest_metrics_date")
    @patch("sports_coach_engine.api.coach.enrich_metrics")
    def test_get_training_status_enrichment_error(
        self, mock_enrich, mock_find_date, mock_repo_cls, mock_log, mock_daily_metrics
    ):
        """Test training status with enrichment error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_find_date.return_value = date.today()
        mock_repo.read_yaml.return_value = mock_daily_metrics

        # Mock enrichment error
        mock_enrich.side_effect = Exception("Enrichment failed")

        result = get_training_status()

        # Should return CoachError
        assert isinstance(result, CoachError)
        assert result.error_type == "unknown"
        assert "Failed to enrich metrics" in result.message


# ============================================================
# HELPER FUNCTION TESTS
# ============================================================


class TestFindLatestMetricsDate:
    """Test _find_latest_metrics_date() helper."""

    def test_find_latest_metrics_date_today(self, tmp_path):
        """Test finding metrics for today."""
        from sports_coach_engine.core.repository import RepositoryIO
        from sports_coach_engine.api.coach import _find_latest_metrics_date

        repo = RepositoryIO()
        repo.repo_root = tmp_path

        # Create metrics file for today
        today = date.today()
        metrics_dir = tmp_path / "data" / "metrics" / "daily"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_file = metrics_dir / f"{today}.yaml"
        metrics_file.write_text("test: data")

        result = _find_latest_metrics_date(repo)

        assert result == today

    def test_find_latest_metrics_date_none(self, tmp_path):
        """Test finding metrics when none exist."""
        from sports_coach_engine.core.repository import RepositoryIO
        from sports_coach_engine.api.coach import _find_latest_metrics_date

        repo = RepositoryIO()
        repo.repo_root = tmp_path

        result = _find_latest_metrics_date(repo)

        assert result is None
