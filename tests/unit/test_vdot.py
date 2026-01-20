"""
Unit tests for VDOT module - Training pace calculations.

Tests VDOT calculations, training pace generation, race predictions,
six-second rule, and environmental pace adjustments based on Daniels' methodology.
"""

import pytest
from sports_coach_engine.core.vdot import (
    calculate_vdot,
    calculate_training_paces,
    calculate_race_equivalents,
    apply_six_second_rule,
    adjust_pace_for_altitude,
    adjust_pace_for_heat,
    adjust_pace_for_hills,
    parse_time_string,
    format_time_seconds,
)
from sports_coach_engine.schemas.vdot import (
    RaceDistance,
    PaceUnit,
    ConditionType,
    ConfidenceLevel,
)


# ============================================================
# TIME PARSING & FORMATTING TESTS
# ============================================================


class TestTimeFormatting:
    """Tests for time parsing and formatting utilities."""

    def test_parse_mm_ss_format(self):
        """Parse MM:SS format correctly."""
        assert parse_time_string("5:30") == 330  # 5 * 60 + 30
        assert parse_time_string("10:45") == 645  # 10 * 60 + 45

    def test_parse_hh_mm_ss_format(self):
        """Parse HH:MM:SS format correctly."""
        assert parse_time_string("1:30:00") == 5400  # 1 * 3600 + 30 * 60
        assert parse_time_string("2:45:30") == 9930  # 2 * 3600 + 45 * 60 + 30

    def test_parse_invalid_format_raises(self):
        """Invalid time format should raise ValueError."""
        with pytest.raises(ValueError):
            parse_time_string("invalid")
        with pytest.raises(ValueError):
            parse_time_string("5:30:45:10")  # Too many parts

    def test_format_time_short(self):
        """Format time < 1 hour as MM:SS."""
        assert format_time_seconds(150) == "2:30"
        assert format_time_seconds(645) == "10:45"

    def test_format_time_long(self):
        """Format time ≥ 1 hour as HH:MM:SS."""
        assert format_time_seconds(3665) == "1:01:05"
        assert format_time_seconds(5400) == "1:30:00"


# ============================================================
# VDOT CALCULATION TESTS
# ============================================================


class TestVDOTCalculation:
    """Tests for VDOT calculation from race performance."""

    def test_10k_42_30_vdot_calculation(self):
        """10K @ 42:30 should calculate to VDOT around 44-48 range."""
        result = calculate_vdot(RaceDistance.TEN_K, 2550)  # 42:30 = 2550s

        # Table is simplified, should be in reasonable range
        assert 43 <= result.vdot <= 48
        assert result.source_race == RaceDistance.TEN_K
        assert result.source_time_seconds == 2550
        assert result.confidence == ConfidenceLevel.HIGH

    def test_half_marathon_90_min_vdot_calculation(self):
        """Half marathon @ 1:30:00 should calculate to valid VDOT."""
        result = calculate_vdot(RaceDistance.HALF_MARATHON, 5400)  # 1:30:00

        # Should be in competitive range
        assert 40 <= result.vdot <= 55

    def test_5k_20_15_vdot_calculation(self):
        """5K @ 20:15 should calculate to valid VDOT."""
        result = calculate_vdot(RaceDistance.FIVE_K, 1215)  # 20:15 = 1215s

        # Should be in recreational to competitive range
        assert 42 <= result.vdot <= 50

    def test_marathon_153_min_vdot_calculation(self):
        """Marathon @ 2:33:00 should calculate to valid VDOT."""
        result = calculate_vdot(RaceDistance.MARATHON, 9180)  # 2:33:00

        # Should be in competitive to advanced range
        assert 50 <= result.vdot <= 65

    def test_invalid_race_time_raises(self):
        """Zero or negative race time should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            calculate_vdot(RaceDistance.TEN_K, 0)

        with pytest.raises(ValueError, match="must be positive"):
            calculate_vdot(RaceDistance.TEN_K, -100)


# ============================================================
# TRAINING PACES TESTS
# ============================================================


class TestTrainingPaces:
    """Tests for training pace generation from VDOT."""

    def test_vdot_48_paces(self):
        """VDOT 48 should generate correct pace ranges."""
        paces = calculate_training_paces(48, PaceUnit.MIN_PER_KM)

        # E-pace: 5:06-5:30/km (306-330 sec/km)
        assert paces.easy_pace_range == (306, 330)

        # M-pace: 4:18-4:30/km (258-270 sec/km)
        assert paces.marathon_pace_range == (258, 270)

        # T-pace: 4:00-4:12/km (240-252 sec/km)
        assert paces.threshold_pace_range == (240, 252)

        # I-pace: 3:36-3:48/km (216-228 sec/km)
        assert paces.interval_pace_range == (216, 228)

        # R-pace: 3:12-3:24/km (192-204 sec/km)
        assert paces.repetition_pace_range == (192, 204)

    def test_vdot_55_paces(self):
        """VDOT 55 should generate faster paces than VDOT 48."""
        paces_55 = calculate_training_paces(55)
        paces_48 = calculate_training_paces(48)

        # All paces should be faster (lower seconds) for higher VDOT
        assert paces_55.easy_pace_range[0] < paces_48.easy_pace_range[0]
        assert paces_55.threshold_pace_range[0] < paces_48.threshold_pace_range[0]
        assert paces_55.interval_pace_range[0] < paces_48.interval_pace_range[0]

    def test_vdot_out_of_range_raises(self):
        """VDOT outside 30-85 range should raise ValueError."""
        with pytest.raises(ValueError, match="between 30 and 85"):
            calculate_training_paces(25)

        with pytest.raises(ValueError, match="between 30 and 85"):
            calculate_training_paces(90)

    def test_interpolation_for_non_table_vdot(self):
        """VDOT not in table (e.g., 47) should be interpolated."""
        paces = calculate_training_paces(47)

        # Should have valid pace ranges
        assert paces.vdot == 47
        assert paces.easy_pace_range[0] > 0
        assert paces.threshold_pace_range[0] > 0

        # Should be between VDOT 45 and 48 values
        paces_45 = calculate_training_paces(45)
        paces_48 = calculate_training_paces(48)

        assert paces_45.easy_pace_range[0] > paces.easy_pace_range[0] > paces_48.easy_pace_range[0]

    def test_format_pace_method(self):
        """TrainingPaces.format_pace should format correctly."""
        paces = calculate_training_paces(48)

        # 306 seconds = 5:06
        assert paces.format_pace(306) == "5:06"

        # 240 seconds = 4:00
        assert paces.format_pace(240) == "4:00"

    def test_format_range_method(self):
        """TrainingPaces.format_range should format range correctly."""
        paces = calculate_training_paces(48)

        # E-pace: 306-330 = 5:06-5:30
        assert paces.format_range(paces.easy_pace_range) == "5:06-5:30"


# ============================================================
# RACE EQUIVALENTS TESTS
# ============================================================


class TestRaceEquivalents:
    """Tests for race time predictions."""

    def test_10k_42_30_predicts_all_distances(self):
        """10K @ 42:30 should predict times for all distances."""
        equiv = calculate_race_equivalents(RaceDistance.TEN_K, 2550)

        # VDOT should be in reasonable range
        assert 40 <= equiv.vdot <= 50
        assert equiv.source_race == RaceDistance.TEN_K

        # Should have predictions for all distances
        assert RaceDistance.FIVE_K in equiv.predictions
        assert RaceDistance.TEN_K in equiv.predictions
        assert RaceDistance.HALF_MARATHON in equiv.predictions
        assert RaceDistance.MARATHON in equiv.predictions

        # Source race time should match input
        assert equiv.source_time_formatted == "42:30"

    def test_5k_20_min_predicts_slower_10k(self):
        """5K @ 20:00 should predict slower 10K time."""
        equiv = calculate_race_equivalents(RaceDistance.FIVE_K, 1200)  # 20:00

        # 10K should be slower than 40:00 (not double the 5K time)
        ten_k_seconds = parse_time_string(equiv.predictions[RaceDistance.TEN_K])
        assert ten_k_seconds > 2400  # > 40:00

    def test_predictions_consistent_with_vdot(self):
        """Predictions should match VDOT table for that race distance."""
        # Use 10K @ 42:30
        equiv = calculate_race_equivalents(RaceDistance.TEN_K, 2550)
        original_vdot = equiv.vdot

        # Cross-check: Calculate VDOT from predicted half marathon time
        half_time_str = equiv.predictions[RaceDistance.HALF_MARATHON]
        half_time_seconds = parse_time_string(half_time_str)

        # Should calculate back to similar VDOT (allow 2 point tolerance for v0 table)
        vdot_check = calculate_vdot(RaceDistance.HALF_MARATHON, half_time_seconds)
        assert abs(vdot_check.vdot - original_vdot) <= 2


# ============================================================
# SIX-SECOND RULE TESTS
# ============================================================


class TestSixSecondRule:
    """Tests for six-second rule for novice runners."""

    def test_mile_6_00_generates_paces(self):
        """Mile @ 6:00 should generate R/I/T paces."""
        result = apply_six_second_rule(360)  # 6:00 = 360s

        # Mile = ~4 × 400m, so R-pace = 360 / 4 = 90s per 400m
        assert result.r_pace_400m == 90

        # I-pace = R + 6-8 seconds (depending on estimated VDOT)
        assert result.i_pace_400m >= 96
        assert result.i_pace_400m <= 98

        # T-pace = I + 6-8 seconds
        assert result.t_pace_400m >= 102
        assert result.t_pace_400m <= 106

    def test_slower_mile_uses_larger_adjustment(self):
        """Slower mile times (lower VDOT) should use 7-8 sec adjustment."""
        result_slow = apply_six_second_rule(540)  # 9:00 mile (slower)
        result_fast = apply_six_second_rule(300)  # 5:00 mile (faster)

        # Slower runner should have larger adjustment
        assert result_slow.adjustment_seconds >= result_fast.adjustment_seconds

    def test_estimated_vdot_range_provided(self):
        """Should provide estimated VDOT range."""
        result = apply_six_second_rule(360)

        assert len(result.estimated_vdot_range) == 2
        vdot_min, vdot_max = result.estimated_vdot_range
        assert 30 <= vdot_min <= 85
        assert 30 <= vdot_max <= 85
        assert vdot_min <= vdot_max


# ============================================================
# PACE ADJUSTMENT TESTS
# ============================================================


class TestAltitudeAdjustment:
    """Tests for altitude pace adjustments."""

    def test_low_altitude_no_adjustment(self):
        """Altitude < 3000ft should have no adjustment."""
        adj = adjust_pace_for_altitude(300, 2000.0)  # 5:00/km at 2000ft

        assert adj.adjustment_seconds == 0
        assert adj.adjusted_pace_sec_per_km == 300

    def test_moderate_altitude_adjustment(self):
        """Altitude 5000-7000ft should have moderate adjustment."""
        adj = adjust_pace_for_altitude(300, 6000.0)  # 5:00/km at 6000ft

        # Should have some slowdown
        assert adj.adjustment_seconds > 0
        assert adj.adjusted_pace_sec_per_km > 300
        assert "moderate" in adj.recommendation.lower() or "minor" in adj.recommendation.lower()

    def test_high_altitude_significant_adjustment(self):
        """Altitude >7000ft should have significant adjustment."""
        adj = adjust_pace_for_altitude(300, 8000.0)  # 5:00/km at 8000ft

        # Should have larger slowdown
        assert adj.adjustment_seconds > 10
        assert adj.adjusted_pace_sec_per_km > 310
        assert "significant" in adj.recommendation.lower()


class TestHeatAdjustment:
    """Tests for heat/humidity pace adjustments."""

    def test_optimal_temp_no_adjustment(self):
        """Temperature ≤20°C should have no adjustment."""
        adj = adjust_pace_for_heat(300, 18.0)  # 5:00/km at 18°C

        assert adj.adjustment_seconds == 0
        assert adj.adjusted_pace_sec_per_km == 300

    def test_moderate_heat_adjustment(self):
        """Temperature 25-30°C should have moderate adjustment."""
        adj = adjust_pace_for_heat(300, 28.0)  # 5:00/km at 28°C

        # Should have ~5-8% slowdown
        assert adj.adjustment_seconds > 10
        assert adj.adjusted_pace_sec_per_km >= 315
        assert "moderate" in adj.recommendation.lower()

    def test_extreme_heat_significant_adjustment(self):
        """Temperature >30°C should have significant adjustment."""
        adj = adjust_pace_for_heat(300, 35.0)  # 5:00/km at 35°C

        # Should have ~10-15% slowdown
        assert adj.adjustment_seconds > 30
        assert adj.adjusted_pace_sec_per_km >= 330
        assert "significant" in adj.recommendation.lower() or "heat stress" in adj.recommendation.lower()

    def test_humidity_amplifies_heat(self):
        """High humidity should increase heat adjustment."""
        adj_low_humidity = adjust_pace_for_heat(300, 28.0, 50.0)
        adj_high_humidity = adjust_pace_for_heat(300, 28.0, 80.0)

        # High humidity should have larger adjustment
        assert adj_high_humidity.adjustment_seconds > adj_low_humidity.adjustment_seconds


class TestHillAdjustment:
    """Tests for hill grade pace adjustments."""

    def test_flat_no_adjustment(self):
        """Grade <1% should have no adjustment."""
        adj = adjust_pace_for_hills(300, 0.5)  # 5:00/km at 0.5% grade

        assert adj.adjustment_seconds == 0
        assert adj.adjusted_pace_sec_per_km == 300

    def test_moderate_hill_adjustment(self):
        """Grade 3-5% should have moderate adjustment."""
        adj = adjust_pace_for_hills(300, 4.0)  # 5:00/km at 4% grade

        # Should have ~10-15 seconds/km adjustment
        assert adj.adjustment_seconds >= 10
        assert adj.adjusted_pace_sec_per_km >= 310
        assert "effort" in adj.recommendation.lower()

    def test_steep_hill_recommend_effort_based(self):
        """Grade >5% should strongly recommend effort-based pacing."""
        adj = adjust_pace_for_hills(300, 7.0)  # 5:00/km at 7% grade

        assert adj.adjustment_seconds > 20
        assert "steep" in adj.recommendation.lower() or "effort" in adj.recommendation.lower()


# ============================================================
# API INTEGRATION TESTS
# ============================================================


class TestVDOTAPIFunctions:
    """Tests for high-level API functions."""

    def test_api_calculate_vdot_from_race(self):
        """API function should parse string inputs and return result."""
        from sports_coach_engine.api.vdot import calculate_vdot_from_race

        result = calculate_vdot_from_race("10k", "42:30")

        # Should return VDOTResult, not error
        assert hasattr(result, "vdot")
        assert 40 <= result.vdot <= 50  # Reasonable range for 42:30 10K

    def test_api_get_training_paces(self):
        """API function should return training paces."""
        from sports_coach_engine.api.vdot import get_training_paces

        result = get_training_paces(48)

        assert hasattr(result, "easy_pace_range")
        assert result.easy_pace_range == (306, 330)

    def test_api_predict_race_times(self):
        """API function should predict race times."""
        from sports_coach_engine.api.vdot import predict_race_times

        result = predict_race_times("10k", "42:30")

        assert hasattr(result, "predictions")
        assert RaceDistance.HALF_MARATHON in result.predictions

    def test_api_invalid_race_distance_returns_error(self):
        """API should return error for invalid race distance."""
        from sports_coach_engine.api.vdot import calculate_vdot_from_race

        result = calculate_vdot_from_race("100k", "5:00:00")  # Invalid distance

        # Should return VDOTError
        assert hasattr(result, "error_type")
        assert result.error_type == "invalid_input"

    def test_api_invalid_time_format_returns_error(self):
        """API should return error for invalid time format."""
        from sports_coach_engine.api.vdot import calculate_vdot_from_race

        result = calculate_vdot_from_race("10k", "invalid")

        assert hasattr(result, "error_type")
        assert result.error_type == "invalid_input"


# ============================================================
# VDOT ESTIMATION TESTS (RACE HISTORY FALLBACK)
# ============================================================


class TestVDOTEstimationRaceHistoryFallback:
    """Tests for estimate_current_vdot() race history fallback."""

    def _create_dummy_activity_file(self, activities_dir, days_ago=0):
        """Create a dummy activity file (empty, just for glob detection)."""
        from datetime import date, timedelta
        activity_date = date.today() - timedelta(days=days_ago)
        activity_file = activities_dir / f"activity_{activity_date.isoformat()}.json"
        activity_file.touch()  # Create empty file

    def _mock_repository_with_easy_run(self, monkeypatch, days_ago=5):
        """Mock RepositoryIO to return a dummy easy run (not a quality workout)."""
        from unittest.mock import Mock
        from datetime import date, timedelta
        from sports_coach_engine.schemas.activity import NormalizedActivity

        activity_date = date.today() - timedelta(days=days_ago)
        dummy_activity = Mock(spec=NormalizedActivity)
        dummy_activity.sport_type = "Run"
        dummy_activity.start_date = f"{activity_date.isoformat()}T08:00:00Z"
        dummy_activity.distance_km = 5.0
        dummy_activity.moving_time_seconds = 1800  # 30 min = 6:00/km (easy)
        dummy_activity.title = "Morning Easy Run"  # No quality keywords
        dummy_activity.description = None

        # Mock RepositoryIO.read_json to return our dummy activity
        mock_repo = Mock()
        mock_repo.read_json.return_value = dummy_activity

        def mock_repo_init(*args, **kwargs):
            return mock_repo

        monkeypatch.setattr("sports_coach_engine.core.repository.RepositoryIO", mock_repo_init)

    def test_fallback_recent_race_no_decay(self, tmp_path, monkeypatch):
        """Test VDOT estimation fallback with recent race (<3 months) - no decay."""
        from sports_coach_engine.api.vdot import estimate_current_vdot
        from sports_coach_engine.schemas.vdot import VDOTEstimate
        from sports_coach_engine.schemas.profile import RacePerformance, RaceSource
        from datetime import date, timedelta
        from unittest.mock import Mock

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("SCE_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("sports_coach_engine.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create dummy activity file and mock repository
        self._create_dummy_activity_file(activities_dir, days_ago=5)
        self._mock_repository_with_easy_run(monkeypatch, days_ago=5)

        # Create mock profile with recent race (2 months ago)
        mock_profile = Mock()
        recent_race_date = (date.today() - timedelta(days=60)).isoformat()  # 2 months ago
        mock_profile.race_history = [
            Mock(
                distance="10k",
                time="42:30",
                date=recent_race_date,
                vdot=45.0,
            )
        ]

        # Mock get_profile to return our mock profile
        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr("sports_coach_engine.api.profile.get_profile", mock_get_profile)

        # Execute
        result = estimate_current_vdot(lookback_days=28)

        # Verify
        assert isinstance(result, VDOTEstimate)
        assert result.estimated_vdot == 45  # No decay for recent race
        assert result.confidence == ConfidenceLevel.HIGH
        assert "race_history" in result.source
        assert "10k" in result.source
        assert "months ago" in result.source  # 60 days ≈ 1-2 months

    def test_fallback_moderate_age_race_3pct_decay(self, tmp_path, monkeypatch):
        """Test VDOT estimation fallback with 3-6 month old race - 3% decay."""
        from sports_coach_engine.api.vdot import estimate_current_vdot
        from sports_coach_engine.schemas.vdot import VDOTEstimate
        from datetime import date, timedelta
        from unittest.mock import Mock

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("SCE_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("sports_coach_engine.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create dummy activity file and mock repository
        self._create_dummy_activity_file(activities_dir, days_ago=5)
        self._mock_repository_with_easy_run(monkeypatch, days_ago=5)

        # Create mock profile with 4-month old race
        mock_profile = Mock()
        old_race_date = (date.today() - timedelta(days=120)).isoformat()  # 4 months ago
        mock_profile.race_history = [
            Mock(
                distance="10k",
                time="42:30",
                date=old_race_date,
                vdot=45.0,
            )
        ]

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr("sports_coach_engine.api.profile.get_profile", mock_get_profile)

        # Execute
        result = estimate_current_vdot(lookback_days=28)

        # Verify
        assert isinstance(result, VDOTEstimate)
        # 45 * 0.97 = 43.65, rounds to 44
        assert result.estimated_vdot == 44
        assert result.confidence == ConfidenceLevel.MEDIUM
        assert "race_history" in result.source
        assert "months ago" in result.source  # 120 days ≈ 3-4 months

    def test_fallback_old_race_progressive_decay(self, tmp_path, monkeypatch):
        """Test VDOT estimation fallback with 12-month old race - progressive decay."""
        from sports_coach_engine.api.vdot import estimate_current_vdot
        from sports_coach_engine.schemas.vdot import VDOTEstimate
        from datetime import date, timedelta
        from unittest.mock import Mock

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("SCE_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("sports_coach_engine.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create dummy activity file and mock repository
        self._create_dummy_activity_file(activities_dir, days_ago=5)
        self._mock_repository_with_easy_run(monkeypatch, days_ago=5)

        # Create mock profile with 12-month old race
        mock_profile = Mock()
        old_race_date = (date.today() - timedelta(days=365)).isoformat()  # 12 months ago
        mock_profile.race_history = [
            Mock(
                distance="10k",
                time="49:33",
                date=old_race_date,
                vdot=38.0,
            )
        ]

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr("sports_coach_engine.api.profile.get_profile", mock_get_profile)

        # Execute
        result = estimate_current_vdot(lookback_days=28)

        # Verify
        assert isinstance(result, VDOTEstimate)
        # At 12 months: 7 + (12 - 6) * 0.5 = 7 + 3 = 10% decay
        # 38 * 0.90 = 34.2, rounds to 34
        assert result.estimated_vdot == 34
        assert result.confidence == ConfidenceLevel.LOW
        assert "race_history" in result.source
        assert "months ago" in result.source  # 365 days ≈ 11-12 months

    def test_fallback_uses_most_recent_race(self, tmp_path, monkeypatch):
        """Test that fallback uses the most recent race when multiple exist."""
        from sports_coach_engine.api.vdot import estimate_current_vdot
        from sports_coach_engine.schemas.vdot import VDOTEstimate
        from datetime import date, timedelta
        from unittest.mock import Mock

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("SCE_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("sports_coach_engine.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create dummy activity file and mock repository
        self._create_dummy_activity_file(activities_dir, days_ago=5)
        self._mock_repository_with_easy_run(monkeypatch, days_ago=5)

        # Create mock profile with multiple races
        mock_profile = Mock()
        mock_profile.race_history = [
            Mock(  # Older race
                distance="10k",
                time="50:00",
                date=(date.today() - timedelta(days=365)).isoformat(),
                vdot=35.0,
            ),
            Mock(  # More recent race - should be used
                distance="5k",
                time="22:30",
                date=(date.today() - timedelta(days=60)).isoformat(),
                vdot=42.0,
            ),
        ]

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr("sports_coach_engine.api.profile.get_profile", mock_get_profile)

        # Execute
        result = estimate_current_vdot(lookback_days=28)

        # Verify - should use the 5K race (more recent, VDOT 42)
        assert isinstance(result, VDOTEstimate)
        assert result.estimated_vdot == 42
        assert "5k" in result.source
        assert "months ago" in result.source  # 60 days ≈ 1-2 months

    def test_no_workouts_no_race_history_returns_error(self, tmp_path, monkeypatch):
        """Test that error is returned when no workouts and no race history."""
        from sports_coach_engine.api.vdot import estimate_current_vdot, VDOTError
        from unittest.mock import Mock

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("SCE_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("sports_coach_engine.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create dummy activity file and mock repository
        self._create_dummy_activity_file(activities_dir, days_ago=5)
        self._mock_repository_with_easy_run(monkeypatch, days_ago=5)

        # Create mock profile with no race history
        mock_profile = Mock()
        mock_profile.race_history = []

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr("sports_coach_engine.api.profile.get_profile", mock_get_profile)

        # Execute
        result = estimate_current_vdot(lookback_days=28)

        # Verify
        assert isinstance(result, VDOTError)
        assert result.error_type == "not_found"
        assert "No quality workouts" in result.message
        assert "no race history available" in result.message

    def test_fallback_clamps_vdot_to_valid_range(self, tmp_path, monkeypatch):
        """Test that fallback clamps decayed VDOT to valid 30-85 range."""
        from sports_coach_engine.api.vdot import estimate_current_vdot
        from sports_coach_engine.schemas.vdot import VDOTEstimate
        from datetime import date, timedelta
        from unittest.mock import Mock

        # Setup paths
        activities_dir = tmp_path / "activities"
        activities_dir.mkdir(parents=True)
        monkeypatch.setenv("SCE_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("sports_coach_engine.core.paths.get_activities_dir", lambda: str(activities_dir))

        # Create dummy activity file and mock repository
        self._create_dummy_activity_file(activities_dir, days_ago=5)
        self._mock_repository_with_easy_run(monkeypatch, days_ago=5)

        # Create mock profile with very old, low VDOT race
        mock_profile = Mock()
        old_race_date = (date.today() - timedelta(days=730)).isoformat()  # 2 years ago
        mock_profile.race_history = [
            Mock(
                distance="10k",
                time="55:00",
                date=old_race_date,
                vdot=32.0,
            )
        ]

        def mock_get_profile():
            return mock_profile

        monkeypatch.setattr("sports_coach_engine.api.profile.get_profile", mock_get_profile)

        # Execute
        result = estimate_current_vdot(lookback_days=28)

        # Verify - should clamp to minimum of 30
        assert isinstance(result, VDOTEstimate)
        # 32 * 0.85 (15% decay) = 27.2, but should be clamped to 30
        assert result.estimated_vdot >= 30
        assert result.estimated_vdot <= 85
