"""
Unit tests for Metrics API (api/metrics.py).

Tests get_current_metrics(), get_readiness(), and get_intensity_distribution().
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch, MagicMock

from sports_coach_engine.api.metrics import (
    get_current_metrics,
    get_readiness,
    get_intensity_distribution,
    MetricsError,
    _find_latest_metrics_date,
)
from sports_coach_engine.schemas.metrics import (
    DailyMetrics,
    ReadinessScore,
    ReadinessLevel,
    IntensityDistribution,
    CTLATLMetrics,
)
from sports_coach_engine.schemas.enrichment import EnrichedMetrics, MetricInterpretation
from sports_coach_engine.schemas.repository import RepoError, RepoErrorType


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_daily_metrics():
    """Mock DailyMetrics with full data."""
    metrics = Mock(spec=DailyMetrics)
    metrics.date = date.today()
    metrics.ctl_atl = Mock(spec=CTLATLMetrics)
    metrics.ctl_atl.ctl = 44.0
    metrics.ctl_atl.atl = 52.0
    metrics.ctl_atl.tsb = -8.0

    metrics.readiness = Mock(spec=ReadinessScore)
    metrics.readiness.score = 68
    metrics.readiness.level = ReadinessLevel.READY

    metrics.intensity_distribution = Mock(spec=IntensityDistribution)
    metrics.intensity_distribution.low_minutes = 240
    metrics.intensity_distribution.moderate_minutes = 40
    metrics.intensity_distribution.high_minutes = 20

    return metrics


@pytest.fixture
def mock_enriched_metrics():
    """Mock EnrichedMetrics."""
    enriched = Mock(spec=EnrichedMetrics)
    enriched.date = date.today()
    enriched.ctl = Mock(spec=MetricInterpretation)
    enriched.ctl.formatted_value = "44"
    enriched.tsb = Mock(spec=MetricInterpretation)
    enriched.tsb.formatted_value = "-8"
    enriched.readiness = Mock(spec=MetricInterpretation)
    enriched.readiness.formatted_value = "68"
    return enriched


# ============================================================
# GET_CURRENT_METRICS TESTS
# ============================================================


class TestGetCurrentMetrics:
    """Test get_current_metrics() function."""

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    @patch("sports_coach_engine.api.metrics._find_latest_metrics_date")
    @patch("sports_coach_engine.api.metrics.enrich_metrics")
    def test_get_current_metrics_success(
        self, mock_enrich, mock_find_date, mock_repo_cls, mock_log, mock_daily_metrics, mock_enriched_metrics
    ):
        """Test successful metrics retrieval."""
        # Mock repository
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock finding latest date
        mock_find_date.return_value = date.today()

        # Mock loading metrics
        mock_repo.read_yaml.return_value = mock_daily_metrics

        # Mock enrichment
        mock_enrich.return_value = mock_enriched_metrics

        result = get_current_metrics()

        # Should return EnrichedMetrics
        assert isinstance(result, Mock)  # Mock of EnrichedMetrics
        assert result == mock_enriched_metrics

        # Verify enrichment was called with repo
        mock_enrich.assert_called_once_with(mock_daily_metrics, mock_repo)

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    @patch("sports_coach_engine.api.metrics._find_latest_metrics_date")
    def test_get_current_metrics_no_data(self, mock_find_date, mock_repo_cls, mock_log):
        """Test metrics retrieval when no data exists."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock no metrics found
        mock_find_date.return_value = None

        result = get_current_metrics()

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "not_found"
        assert "No metrics available" in result.message

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    @patch("sports_coach_engine.api.metrics._find_latest_metrics_date")
    def test_get_current_metrics_validation_error(self, mock_find_date, mock_repo_cls, mock_log):
        """Test metrics retrieval with validation error."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_find_date.return_value = date.today()

        # Mock validation error
        mock_repo.read_yaml.return_value = RepoError(RepoErrorType.VALIDATION_ERROR, "Invalid YAML")

        result = get_current_metrics()

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "validation"
        assert "Failed to load metrics" in result.message

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    @patch("sports_coach_engine.api.metrics._find_latest_metrics_date")
    @patch("sports_coach_engine.api.metrics.enrich_metrics")
    def test_get_current_metrics_enrichment_failure(
        self, mock_enrich, mock_find_date, mock_repo_cls, mock_log, mock_daily_metrics
    ):
        """Test metrics retrieval when enrichment fails."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_find_date.return_value = date.today()
        mock_repo.read_yaml.return_value = mock_daily_metrics

        # Mock enrichment failure
        mock_enrich.side_effect = Exception("Enrichment error")

        result = get_current_metrics()

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "unknown"
        assert "Failed to enrich metrics" in result.message


# ============================================================
# GET_READINESS TESTS
# ============================================================


class TestGetReadiness:
    """Test get_readiness() function."""

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    @patch("sports_coach_engine.api.metrics._find_latest_metrics_date")
    def test_get_readiness_success(self, mock_find_date, mock_repo_cls, mock_log, mock_daily_metrics):
        """Test successful readiness retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_find_date.return_value = date.today()
        mock_repo.read_yaml.return_value = mock_daily_metrics

        result = get_readiness()

        # Should return ReadinessScore
        assert isinstance(result, Mock)  # Mock of ReadinessScore
        assert result == mock_daily_metrics.readiness
        assert result.score == 68

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    @patch("sports_coach_engine.api.metrics._find_latest_metrics_date")
    def test_get_readiness_no_data(self, mock_find_date, mock_repo_cls, mock_log):
        """Test readiness retrieval when no metrics exist."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_find_date.return_value = None

        result = get_readiness()

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "not_found"
        assert "No readiness data available" in result.message

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    @patch("sports_coach_engine.api.metrics._find_latest_metrics_date")
    def test_get_readiness_insufficient_data(self, mock_find_date, mock_repo_cls, mock_log):
        """Test readiness retrieval when readiness is not computed."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        mock_find_date.return_value = date.today()

        # Mock metrics without readiness
        mock_metrics = Mock()
        mock_metrics.readiness = None
        mock_repo.read_yaml.return_value = mock_metrics

        result = get_readiness()

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "insufficient_data"
        assert "7 days" in result.message
        assert result.minimum_days_needed == 7


# ============================================================
# GET_INTENSITY_DISTRIBUTION TESTS
# ============================================================


class TestGetIntensityDistribution:
    """Test get_intensity_distribution() function."""

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    def test_get_intensity_distribution_success(self, mock_repo_cls, mock_log):
        """Test successful intensity distribution retrieval."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock 7 days of metrics with intensity data
        def mock_read_yaml(path, schema, options):
            metrics = Mock()
            metrics.intensity_distribution = Mock()
            metrics.intensity_distribution.low_minutes = 30
            metrics.intensity_distribution.moderate_minutes = 5
            metrics.intensity_distribution.high_minutes = 5
            return metrics

        mock_repo.read_yaml.side_effect = mock_read_yaml

        result = get_intensity_distribution(days=7)

        # Should return IntensityDistribution
        assert isinstance(result, IntensityDistribution)
        assert result.low_minutes == 30 * 7  # 210
        assert result.moderate_minutes == 5 * 7  # 35
        assert result.high_minutes == 5 * 7  # 35

        # Check percentages
        total = 30 + 5 + 5  # 40 per day
        expected_low_percent = (30 / total) * 100  # 75%
        assert abs(result.low_percent - expected_low_percent) < 0.1

        # Check 80/20 compliance
        assert result.is_compliant is not None
        assert result.target_low_percent == 80.0

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    def test_get_intensity_distribution_no_data(self, mock_repo_cls, mock_log):
        """Test intensity distribution when no data exists."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock no metrics found
        mock_repo.read_yaml.return_value = None

        result = get_intensity_distribution(days=7)

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "not_found"
        assert "No training data" in result.message

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    def test_get_intensity_distribution_no_training_time(self, mock_repo_cls, mock_log):
        """Test intensity distribution when no training time recorded."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock metrics with zero intensity minutes
        def mock_read_yaml(path, schema, options):
            metrics = Mock()
            metrics.intensity_distribution = Mock()
            metrics.intensity_distribution.low_minutes = 0
            metrics.intensity_distribution.moderate_minutes = 0
            metrics.intensity_distribution.high_minutes = 0
            return metrics

        mock_repo.read_yaml.side_effect = mock_read_yaml

        result = get_intensity_distribution(days=7)

        # Should return MetricsError
        assert isinstance(result, MetricsError)
        assert result.error_type == "insufficient_data"
        assert "No training time recorded" in result.message

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    def test_get_intensity_distribution_partial_data(self, mock_repo_cls, mock_log):
        """Test intensity distribution with partial data (some days missing)."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock some days with data, some without
        call_count = 0
        def mock_read_yaml(path, schema, options):
            nonlocal call_count
            call_count += 1

            # Return data for 3 days, None for 4 days
            if call_count <= 3:
                metrics = Mock()
                metrics.intensity_distribution = Mock()
                metrics.intensity_distribution.low_minutes = 40
                metrics.intensity_distribution.moderate_minutes = 5
                metrics.intensity_distribution.high_minutes = 5
                return metrics
            else:
                return None

        mock_repo.read_yaml.side_effect = mock_read_yaml

        result = get_intensity_distribution(days=7)

        # Should return IntensityDistribution with partial data
        assert isinstance(result, IntensityDistribution)
        assert result.low_minutes == 40 * 3  # 120
        assert result.moderate_minutes == 5 * 3  # 15
        assert result.high_minutes == 5 * 3  # 15

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    def test_get_intensity_distribution_custom_days(self, mock_repo_cls, mock_log):
        """Test intensity distribution with custom day range."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock metrics
        def mock_read_yaml(path, schema, options):
            metrics = Mock()
            metrics.intensity_distribution = Mock()
            metrics.intensity_distribution.low_minutes = 30
            metrics.intensity_distribution.moderate_minutes = 5
            metrics.intensity_distribution.high_minutes = 5
            return metrics

        mock_repo.read_yaml.side_effect = mock_read_yaml

        result = get_intensity_distribution(days=14)

        # Should return IntensityDistribution for 14 days
        assert isinstance(result, IntensityDistribution)
        assert result.low_minutes == 30 * 14  # 420


# ============================================================
# HELPER FUNCTION TESTS
# ============================================================


class TestFindLatestMetricsDate:
    """Test _find_latest_metrics_date() helper."""

    def test_find_latest_metrics_date_today(self, tmp_path):
        """Test finding metrics for today."""
        from sports_coach_engine.core.repository import RepositoryIO

        repo = RepositoryIO()
        repo.repo_root = tmp_path

        # Create metrics file for today
        today = date.today()
        metrics_dir = tmp_path / "metrics" / "daily"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_file = metrics_dir / f"{today}.yaml"
        metrics_file.write_text("test: data")

        result = _find_latest_metrics_date(repo)

        assert result == today

    def test_find_latest_metrics_date_past(self, tmp_path):
        """Test finding metrics from several days ago."""
        from sports_coach_engine.core.repository import RepositoryIO

        repo = RepositoryIO()
        repo.repo_root = tmp_path

        # Create metrics file for 5 days ago
        past_date = date.today() - timedelta(days=5)
        metrics_dir = tmp_path / "metrics" / "daily"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_file = metrics_dir / f"{past_date}.yaml"
        metrics_file.write_text("test: data")

        result = _find_latest_metrics_date(repo)

        assert result == past_date

    def test_find_latest_metrics_date_none(self, tmp_path):
        """Test finding metrics when none exist."""
        from sports_coach_engine.core.repository import RepositoryIO

        repo = RepositoryIO()
        repo.repo_root = tmp_path

        result = _find_latest_metrics_date(repo)

        assert result is None


# ============================================================
# EDGE CASES
# ============================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("sports_coach_engine.api.metrics.log_message")
    @patch("sports_coach_engine.api.metrics.RepositoryIO")
    def test_intensity_distribution_skip_invalid_files(self, mock_repo_cls, mock_log):
        """Test that invalid metrics files are skipped gracefully."""
        mock_repo = Mock()
        mock_repo_cls.return_value = mock_repo

        # Mock some valid files, some invalid
        call_count = 0
        def mock_read_yaml(path, schema, options):
            nonlocal call_count
            call_count += 1

            if call_count == 2:
                # Return error for second file
                return RepoError(RepoErrorType.PARSE_ERROR, "Invalid YAML")
            elif call_count <= 4:
                # Return valid data for other files
                metrics = Mock()
                metrics.intensity_distribution = Mock()
                metrics.intensity_distribution.low_minutes = 30
                metrics.intensity_distribution.moderate_minutes = 5
                metrics.intensity_distribution.high_minutes = 5
                return metrics
            else:
                return None

        mock_repo.read_yaml.side_effect = mock_read_yaml

        result = get_intensity_distribution(days=7)

        # Should return IntensityDistribution, skipping invalid file
        assert isinstance(result, IntensityDistribution)
        # Should have 3 days of data (skipped 1 invalid, 3 missing)
        assert result.low_minutes == 30 * 3
