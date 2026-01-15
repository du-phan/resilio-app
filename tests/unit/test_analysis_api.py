"""
Unit tests for analysis API layer.

Tests error handling, input validation, and successful execution for all 9
analysis functions (5 weekly + 4 risk).
"""

import pytest
from datetime import date, timedelta

from sports_coach_engine.api.analysis import (
    api_analyze_week_adherence,
    api_validate_intensity_distribution,
    api_detect_activity_gaps,
    api_analyze_load_distribution_by_sport,
    api_check_weekly_capacity,
    api_assess_current_risk,
    api_estimate_recovery_window,
    api_forecast_training_stress,
    api_assess_taper_status,
    AnalysisError,
)

from sports_coach_engine.schemas.analysis import (
    WeekAdherenceAnalysis,
    IntensityDistributionAnalysis,
    ActivityGapAnalysis,
    LoadDistributionAnalysis,
    WeeklyCapacityCheck,
    CurrentRiskAssessment,
    RecoveryWindowEstimate,
    TrainingStressForecast,
    TaperStatusAssessment,
)


# ============================================================
# TEST DATA FIXTURES
# ============================================================


@pytest.fixture
def sample_planned_workouts():
    """Sample planned workouts for Week 5."""
    return [
        {
            "workout_type": "easy",
            "duration_minutes": 40,
            "distance_km": 6.0,
            "target_systemic_load_au": 160,
            "target_lower_body_load_au": 160,
        },
        {
            "workout_type": "tempo",
            "duration_minutes": 45,
            "distance_km": 8.0,
            "target_systemic_load_au": 315,
            "target_lower_body_load_au": 315,
        },
        {
            "workout_type": "easy",
            "duration_minutes": 30,
            "distance_km": 5.0,
            "target_systemic_load_au": 120,
            "target_lower_body_load_au": 120,
        },
        {
            "workout_type": "long_run",
            "duration_minutes": 65,
            "distance_km": 12.0,
            "target_systemic_load_au": 400,
            "target_lower_body_load_au": 400,
        },
    ]


@pytest.fixture
def sample_completed_activities():
    """Sample completed activities for Week 5."""
    return [
        {
            "sport": "running",
            "duration_minutes": 40,
            "distance_km": 6.0,
            "systemic_load_au": 160,
            "lower_body_load_au": 160,
            "workout_type": "easy",
        },
        {
            "sport": "running",
            "duration_minutes": 30,
            "distance_km": 5.0,
            "systemic_load_au": 120,
            "lower_body_load_au": 120,
            "workout_type": "easy",
        },
        {
            "sport": "running",
            "duration_minutes": 65,
            "distance_km": 12.0,
            "systemic_load_au": 400,
            "lower_body_load_au": 400,
            "workout_type": "long_run",
        },
    ]


@pytest.fixture
def sample_intensity_activities():
    """Sample activities for intensity distribution analysis."""
    return [
        {"intensity_zone": "z2", "duration_minutes": 40, "date": "2026-01-01"},
        {"intensity_zone": "z2", "duration_minutes": 30, "date": "2026-01-03"},
        {"intensity_zone": "z4", "duration_minutes": 45, "date": "2026-01-05"},
        {"intensity_zone": "z2", "duration_minutes": 60, "date": "2026-01-08"},
        {"intensity_zone": "z2", "duration_minutes": 40, "date": "2026-01-10"},
        {"intensity_zone": "z5", "duration_minutes": 30, "date": "2026-01-12"},
    ]


@pytest.fixture
def sample_gap_activities():
    """Sample activities with a 14-day gap."""
    return [
        {"date": "2025-11-10", "ctl": 44.0, "notes": "Easy run"},
        {"date": "2025-11-12", "ctl": 44.5, "notes": "Tempo"},
        {"date": "2025-11-13", "ctl": 45.0, "notes": "Left ankle pain"},
        # 14-day gap
        {"date": "2025-11-28", "ctl": 22.0, "notes": "Return from injury"},
        {"date": "2025-11-30", "ctl": 24.0, "notes": "Easy run"},
    ]


@pytest.fixture
def sample_multisport_activities():
    """Sample multi-sport activities for load distribution."""
    return [
        {
            "sport": "running",
            "systemic_load_au": 160,
            "lower_body_load_au": 160,
            "date": "2026-01-13",
        },
        {
            "sport": "climbing",
            "systemic_load_au": 340,
            "lower_body_load_au": 52,
            "date": "2026-01-14",
        },
        {
            "sport": "running",
            "systemic_load_au": 315,
            "lower_body_load_au": 315,
            "date": "2026-01-15",
        },
        {
            "sport": "yoga",
            "systemic_load_au": 70,
            "lower_body_load_au": 48,
            "date": "2026-01-16",
        },
        {
            "sport": "running",
            "systemic_load_au": 120,
            "lower_body_load_au": 120,
            "date": "2026-01-17",
        },
    ]


@pytest.fixture
def sample_historical_activities():
    """Sample historical activities for capacity check."""
    return [
        {"distance_km": 25.0, "systemic_load_au": 350, "date": "2025-12-01"},
        {"distance_km": 30.0, "systemic_load_au": 400, "date": "2025-12-08"},
        {"distance_km": 35.0, "systemic_load_au": 450, "date": "2025-12-15"},
        {"distance_km": 40.0, "systemic_load_au": 480, "date": "2025-12-22"},
        {"distance_km": 50.0, "systemic_load_au": 500, "date": "2025-12-29"},
    ]


@pytest.fixture
def sample_current_metrics():
    """Sample current metrics for risk assessment."""
    return {
        "ctl": 44.0,
        "atl": 52.0,
        "tsb": -8.0,
        "acwr": 1.18,
        "readiness": 65,
        "date": "2026-01-15",
    }


@pytest.fixture
def sample_recent_activities():
    """Sample recent activities for risk assessment."""
    return [
        {
            "sport": "climbing",
            "systemic_load_au": 340,
            "lower_body_load_au": 52,
            "date": "2026-01-14",
        },
        {
            "sport": "running",
            "systemic_load_au": 160,
            "lower_body_load_au": 160,
            "date": "2026-01-13",
        },
    ]


@pytest.fixture
def sample_planned_workout():
    """Sample planned workout for risk assessment."""
    return {
        "workout_type": "tempo",
        "expected_load_au": 315,
    }


@pytest.fixture
def sample_planned_weeks():
    """Sample planned weeks for forecasting."""
    today = date.today()
    return [
        {
            "week_number": 6,
            "target_systemic_load_au": 450,
            "end_date": (today + timedelta(days=7)).isoformat(),
        },
        {
            "week_number": 7,
            "target_systemic_load_au": 480,
            "end_date": (today + timedelta(days=14)).isoformat(),
        },
        {
            "week_number": 8,
            "target_systemic_load_au": 500,
            "end_date": (today + timedelta(days=21)).isoformat(),
        },
    ]


@pytest.fixture
def sample_recent_weeks():
    """Sample recent weeks for taper assessment."""
    today = date.today()
    return [
        {
            "week_number": 10,
            "actual_volume_km": 42.0,
            "end_date": (today - timedelta(days=14)).isoformat(),
        },
        {
            "week_number": 11,
            "actual_volume_km": 30.0,
            "end_date": (today - timedelta(days=7)).isoformat(),
        },
    ]


# ============================================================
# WEEKLY ANALYSIS TESTS
# ============================================================


class TestAnalyzeWeekAdherence:
    """Tests for api_analyze_week_adherence."""

    def test_valid_adherence_analysis(self, sample_planned_workouts, sample_completed_activities):
        """Valid adherence analysis returns WeekAdherenceAnalysis."""
        result = api_analyze_week_adherence(
            week_number=5,
            planned_workouts=sample_planned_workouts,
            completed_activities=sample_completed_activities,
        )

        assert isinstance(result, WeekAdherenceAnalysis)
        assert result.week_number == 5
        assert result.completion_stats.total_workouts_planned == 4
        assert result.completion_stats.total_workouts_completed == 3
        assert result.completion_stats.completion_rate_pct == 75.0

    def test_invalid_week_number(self, sample_planned_workouts, sample_completed_activities):
        """Week number < 1 returns error."""
        result = api_analyze_week_adherence(
            week_number=0,
            planned_workouts=sample_planned_workouts,
            completed_activities=sample_completed_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "Week number must be >= 1" in result.message

    def test_empty_planned_workouts(self, sample_completed_activities):
        """Empty planned workouts returns error."""
        result = api_analyze_week_adherence(
            week_number=5,
            planned_workouts=[],
            completed_activities=sample_completed_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "insufficient_data"

    def test_malformed_planned_workout(self, sample_completed_activities):
        """Missing required keys in planned workout returns error."""
        malformed = [{"workout_type": "easy"}]  # Missing duration, distance

        result = api_analyze_week_adherence(
            week_number=5,
            planned_workouts=malformed,
            completed_activities=sample_completed_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "missing required keys" in result.message


class TestValidateIntensityDistribution:
    """Tests for api_validate_intensity_distribution."""

    def test_valid_intensity_analysis(self, sample_intensity_activities):
        """Valid intensity distribution returns IntensityDistributionAnalysis."""
        result = api_validate_intensity_distribution(
            activities=sample_intensity_activities,
            date_range_days=28,
        )

        assert isinstance(result, IntensityDistributionAnalysis)
        assert result.date_range_days == 28
        assert result.total_activities == 6

    def test_invalid_date_range(self, sample_intensity_activities):
        """date_range_days < 7 returns error."""
        result = api_validate_intensity_distribution(
            activities=sample_intensity_activities,
            date_range_days=3,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "must be >= 7" in result.message

    def test_insufficient_activities(self):
        """Too few activities returns error."""
        result = api_validate_intensity_distribution(
            activities=[
                {"intensity_zone": "z2", "duration_minutes": 40, "date": "2026-01-01"}
            ],
            date_range_days=28,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "insufficient_data"
        assert "at least 3" in result.message

    def test_invalid_intensity_zone(self):
        """Invalid intensity zone returns error."""
        result = api_validate_intensity_distribution(
            activities=[
                {"intensity_zone": "z9", "duration_minutes": 40, "date": "2026-01-01"},
                {"intensity_zone": "z2", "duration_minutes": 30, "date": "2026-01-02"},
                {"intensity_zone": "z3", "duration_minutes": 45, "date": "2026-01-03"},
            ],
            date_range_days=28,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "invalid intensity_zone" in result.message


class TestDetectActivityGaps:
    """Tests for api_detect_activity_gaps."""

    def test_valid_gap_detection(self, sample_gap_activities):
        """Valid gap detection returns ActivityGapAnalysis."""
        result = api_detect_activity_gaps(
            activities=sample_gap_activities,
            min_gap_days=7,
        )

        assert isinstance(result, ActivityGapAnalysis)
        assert result.total_gaps >= 1

    def test_invalid_min_gap_days(self, sample_gap_activities):
        """min_gap_days < 1 returns error."""
        result = api_detect_activity_gaps(
            activities=sample_gap_activities,
            min_gap_days=0,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"

    def test_insufficient_activities(self):
        """Less than 2 activities returns error."""
        result = api_detect_activity_gaps(
            activities=[{"date": "2026-01-01"}],
            min_gap_days=7,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "insufficient_data"
        assert "at least 2 activities" in result.message


class TestAnalyzeLoadDistributionBySport:
    """Tests for api_analyze_load_distribution_by_sport."""

    def test_valid_load_analysis(self, sample_multisport_activities):
        """Valid load distribution returns LoadDistributionAnalysis."""
        result = api_analyze_load_distribution_by_sport(
            activities=sample_multisport_activities,
            date_range_days=7,
            sport_priority="equal",
        )

        assert isinstance(result, LoadDistributionAnalysis)
        assert result.date_range_days == 7

    def test_invalid_date_range(self, sample_multisport_activities):
        """date_range_days < 1 returns error."""
        result = api_analyze_load_distribution_by_sport(
            activities=sample_multisport_activities,
            date_range_days=0,
            sport_priority="equal",
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"

    def test_invalid_sport_priority(self, sample_multisport_activities):
        """Invalid sport_priority returns error."""
        result = api_analyze_load_distribution_by_sport(
            activities=sample_multisport_activities,
            date_range_days=7,
            sport_priority="invalid",
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "sport_priority must be one of" in result.message


class TestCheckWeeklyCapacity:
    """Tests for api_check_weekly_capacity."""

    def test_valid_capacity_check(self, sample_historical_activities):
        """Valid capacity check returns WeeklyCapacityCheck."""
        result = api_check_weekly_capacity(
            week_number=15,
            planned_volume_km=60.0,
            planned_systemic_load_au=550,
            historical_activities=sample_historical_activities,
        )

        assert isinstance(result, WeeklyCapacityCheck)
        assert result.week_number == 15
        assert result.planned_volume_km == 60.0

    def test_invalid_week_number(self, sample_historical_activities):
        """Week number < 1 returns error."""
        result = api_check_weekly_capacity(
            week_number=0,
            planned_volume_km=60.0,
            planned_systemic_load_au=550,
            historical_activities=sample_historical_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"

    def test_negative_planned_volume(self, sample_historical_activities):
        """Negative planned volume returns error."""
        result = api_check_weekly_capacity(
            week_number=15,
            planned_volume_km=-10.0,
            planned_systemic_load_au=550,
            historical_activities=sample_historical_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"

    def test_no_historical_data(self):
        """Empty historical activities returns error."""
        result = api_check_weekly_capacity(
            week_number=15,
            planned_volume_km=60.0,
            planned_systemic_load_au=550,
            historical_activities=[],
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "insufficient_data"


# ============================================================
# RISK ASSESSMENT TESTS
# ============================================================


class TestAssessCurrentRisk:
    """Tests for api_assess_current_risk."""

    def test_valid_risk_assessment(
        self,
        sample_current_metrics,
        sample_recent_activities,
        sample_planned_workout,
    ):
        """Valid risk assessment returns CurrentRiskAssessment."""
        result = api_assess_current_risk(
            current_metrics=sample_current_metrics,
            recent_activities=sample_recent_activities,
            planned_workout=sample_planned_workout,
        )

        assert isinstance(result, CurrentRiskAssessment)
        assert result.overall_risk_level in ["low", "moderate", "high", "danger"]

    def test_missing_required_metrics(self, sample_recent_activities):
        """Missing required metrics returns error."""
        result = api_assess_current_risk(
            current_metrics={"ctl": 44.0},  # Missing atl, tsb, acwr, readiness
            recent_activities=sample_recent_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "missing required keys" in result.message

    def test_negative_acwr(self, sample_recent_activities):
        """Negative ACWR returns error."""
        result = api_assess_current_risk(
            current_metrics={
                "ctl": 44.0,
                "atl": 52.0,
                "tsb": -8.0,
                "acwr": -1.0,
                "readiness": 65,
            },
            recent_activities=sample_recent_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "ACWR cannot be negative" in result.message

    def test_invalid_readiness_range(self, sample_recent_activities):
        """Readiness outside 0-100 returns error."""
        result = api_assess_current_risk(
            current_metrics={
                "ctl": 44.0,
                "atl": 52.0,
                "tsb": -8.0,
                "acwr": 1.18,
                "readiness": 150,
            },
            recent_activities=sample_recent_activities,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "Readiness must be 0-100" in result.message


class TestEstimateRecoveryWindow:
    """Tests for api_estimate_recovery_window."""

    def test_valid_recovery_estimate(self):
        """Valid recovery window estimate returns RecoveryWindowEstimate."""
        result = api_estimate_recovery_window(
            trigger_type="ACWR_ELEVATED",
            current_value=1.35,
            safe_threshold=1.3,
        )

        assert isinstance(result, RecoveryWindowEstimate)
        assert result.trigger == "ACWR_ELEVATED"

    def test_invalid_trigger_type(self):
        """Invalid trigger type returns error."""
        result = api_estimate_recovery_window(
            trigger_type="INVALID_TRIGGER",
            current_value=1.35,
            safe_threshold=1.3,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "trigger_type must be one of" in result.message


class TestForecastTrainingStress:
    """Tests for api_forecast_training_stress."""

    def test_valid_forecast(self, sample_current_metrics, sample_planned_weeks):
        """Valid forecast returns TrainingStressForecast."""
        result = api_forecast_training_stress(
            weeks_ahead=3,
            current_metrics=sample_current_metrics,
            planned_weeks=sample_planned_weeks,
        )

        assert isinstance(result, TrainingStressForecast)
        assert result.weeks_ahead == 3

    def test_invalid_weeks_ahead(self, sample_current_metrics, sample_planned_weeks):
        """weeks_ahead out of range returns error."""
        result = api_forecast_training_stress(
            weeks_ahead=5,  # Max is 4
            current_metrics=sample_current_metrics,
            planned_weeks=sample_planned_weeks,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "must be 1-4" in result.message

    def test_insufficient_planned_weeks(self, sample_current_metrics):
        """Not enough planned weeks returns error."""
        result = api_forecast_training_stress(
            weeks_ahead=3,
            current_metrics=sample_current_metrics,
            planned_weeks=[
                {
                    "week_number": 6,
                    "target_systemic_load_au": 450,
                    "end_date": "2026-01-22",
                }
            ],  # Only 1 week
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "insufficient_data"
        assert "Need 3 planned weeks" in result.message


class TestAssessTaperStatus:
    """Tests for api_assess_taper_status."""

    def test_valid_taper_assessment(self, sample_current_metrics, sample_recent_weeks):
        """Valid taper assessment returns TaperStatusAssessment."""
        race_date = date.today() + timedelta(days=14)

        result = api_assess_taper_status(
            race_date=race_date,
            current_metrics=sample_current_metrics,
            recent_weeks=sample_recent_weeks,
        )

        assert isinstance(result, TaperStatusAssessment)
        assert result.race_date == race_date

    def test_race_date_in_past(self, sample_current_metrics, sample_recent_weeks):
        """Race date in past returns error."""
        race_date = date.today() - timedelta(days=7)

        result = api_assess_taper_status(
            race_date=race_date,
            current_metrics=sample_current_metrics,
            recent_weeks=sample_recent_weeks,
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "invalid_input"
        assert "cannot be in the past" in result.message

    def test_insufficient_recent_weeks(self, sample_current_metrics):
        """Less than 2 recent weeks returns error."""
        race_date = date.today() + timedelta(days=14)

        result = api_assess_taper_status(
            race_date=race_date,
            current_metrics=sample_current_metrics,
            recent_weeks=[
                {
                    "week_number": 11,
                    "actual_volume_km": 30.0,
                    "end_date": "2026-01-08",
                }
            ],
        )

        assert isinstance(result, AnalysisError)
        assert result.error_type == "insufficient_data"
        assert "at least 2 recent weeks" in result.message
