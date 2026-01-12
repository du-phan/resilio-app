"""
Unit tests for M6 - Activity Normalization module.

Tests sport type normalization, surface detection, data quality assessment,
unit conversions, and filename generation.
"""

import pytest
from datetime import date, datetime
from sports_coach_engine.core.normalization import (
    normalize_activity,
    normalize_and_persist,
    normalize_sport_type,
    determine_surface_type,
    determine_data_quality,
    generate_activity_filename,
    validate_activity,
    InvalidActivityError,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.activity import (
    RawActivity,
    NormalizedActivity,
    ActivitySource,
    SportType,
    SurfaceType,
    DataQuality,
)


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture
def basic_raw_activity():
    """Create basic raw activity for testing."""
    return RawActivity(
        id="strava_12345",
        source=ActivitySource.STRAVA,
        sport_type="Run",
        name="Morning Run",
        date=date(2026, 1, 12),
        start_time=datetime(2026, 1, 12, 7, 30),
        duration_seconds=2700,  # 45 minutes
        distance_meters=8000.0,
        elevation_gain_meters=50.0,
        average_hr=155,
        max_hr=170,
        has_hr_data=True,
        has_polyline=True,
    )


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """Create temporary repository for testing."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


# ============================================================
# SPORT TYPE NORMALIZATION TESTS (5 tests)
# ============================================================


class TestSportTypeNormalization:
    """Tests for sport type normalization."""

    def test_all_running_variants_map_correctly(self):
        """Should map all running variants to appropriate types."""
        assert normalize_sport_type("Run") == SportType.RUN
        assert normalize_sport_type("running") == SportType.RUN
        assert normalize_sport_type("TrailRun") == SportType.TRAIL_RUN
        assert normalize_sport_type("VirtualRun") == SportType.TREADMILL_RUN
        assert normalize_sport_type("TrackRun") == SportType.TRACK_RUN

    def test_all_cycling_variants_map_to_cycle(self):
        """Should map all cycling variants to CYCLE."""
        assert normalize_sport_type("Ride") == SportType.CYCLE
        assert normalize_sport_type("cycling") == SportType.CYCLE
        assert normalize_sport_type("VirtualRide") == SportType.CYCLE
        assert normalize_sport_type("MountainBikeRide") == SportType.CYCLE
        assert normalize_sport_type("GravelRide") == SportType.CYCLE

    def test_sub_type_takes_priority_over_main_type(self):
        """Sub-type should override main sport_type when present."""
        # Main type is Run, but sub-type is TrailRun
        result = normalize_sport_type("Run", sub_type="TrailRun")
        assert result == SportType.TRAIL_RUN

    def test_unknown_sports_map_to_other(self):
        """Unknown sports should default to OTHER."""
        assert normalize_sport_type("Paddleboarding") == SportType.OTHER
        assert normalize_sport_type("UnknownSport") == SportType.OTHER

    def test_case_insensitive_matching(self):
        """Sport type matching should be case-insensitive."""
        assert normalize_sport_type("RUN") == SportType.RUN
        assert normalize_sport_type("run") == SportType.RUN
        assert normalize_sport_type("Run") == SportType.RUN


# ============================================================
# SURFACE DETECTION TESTS (4 tests)
# ============================================================


class TestSurfaceDetection:
    """Tests for surface type detection."""

    def test_explicit_sport_types_determine_surface(self):
        """Sport types like TRAIL_RUN should directly determine surface."""
        # Trail run
        surface, conf = determine_surface_type(
            sport_type=SportType.TRAIL_RUN,
            original_sport_type="TrailRun",
            sub_type=None,
            activity_name="Trail Run",
            description=None,
            has_gps=True,
            device_name=None,
        )
        assert surface == SurfaceType.TRAIL
        assert conf == "high"

        # Treadmill run
        surface, conf = determine_surface_type(
            sport_type=SportType.TREADMILL_RUN,
            original_sport_type="VirtualRun",
            sub_type=None,
            activity_name="Zwift Run",
            description=None,
            has_gps=False,
            device_name=None,
        )
        assert surface == SurfaceType.TREADMILL
        assert conf == "high"

    def test_m7_treadmill_detection_integration(self):
        """Should use M7 treadmill detection for generic runs."""
        # Treadmill indicators (no GPS, treadmill in title)
        surface, conf = determine_surface_type(
            sport_type=SportType.RUN,
            original_sport_type="Run",
            sub_type=None,
            activity_name="Treadmill Run",
            description="Indoor workout",
            has_gps=False,
            device_name=None,
        )
        assert surface == SurfaceType.TREADMILL
        # M7 should detect this with high confidence

    def test_gps_presence_suggests_road_running(self):
        """GPS presence without other signals should suggest road."""
        surface, conf = determine_surface_type(
            sport_type=SportType.RUN,
            original_sport_type="Run",
            sub_type=None,
            activity_name="Morning Run",
            description="Great run",
            has_gps=True,
            device_name="Garmin Forerunner",
        )
        assert surface == SurfaceType.ROAD
        assert conf == "high"

    def test_non_running_sports_return_unknown(self):
        """Non-running sports should return UNKNOWN surface."""
        surface, conf = determine_surface_type(
            sport_type=SportType.CYCLE,
            original_sport_type="Ride",
            sub_type=None,
            activity_name="Bike Ride",
            description=None,
            has_gps=True,
            device_name=None,
        )
        assert surface == SurfaceType.UNKNOWN
        assert conf == "high"


# ============================================================
# DATA QUALITY TESTS (3 tests)
# ============================================================


class TestDataQuality:
    """Tests for data quality assessment."""

    def test_treadmill_gets_special_quality_marker(self):
        """Treadmill activities should get TREADMILL quality."""
        quality = determine_data_quality(
            source="strava",
            has_gps=False,
            has_hr=True,
            surface_type=SurfaceType.TREADMILL,
        )
        assert quality == DataQuality.TREADMILL

    def test_gps_and_hr_equals_high_quality(self):
        """GPS + HR + Strava source = HIGH quality."""
        quality = determine_data_quality(
            source="strava",
            has_gps=True,
            has_hr=True,
            surface_type=SurfaceType.ROAD,
        )
        assert quality == DataQuality.HIGH

    def test_manual_entry_equals_low_quality(self):
        """Manual entries always get LOW quality."""
        quality = determine_data_quality(
            source="manual",
            has_gps=False,
            has_hr=False,
            surface_type=SurfaceType.UNKNOWN,
        )
        assert quality == DataQuality.LOW


# ============================================================
# UNIT CONVERSION TESTS (2 tests)
# ============================================================


class TestUnitConversions:
    """Tests for unit conversion logic."""

    def test_meters_to_kilometers_conversion(self, basic_raw_activity):
        """Should convert meters to kilometers with proper rounding."""
        normalized = normalize_activity(basic_raw_activity)

        # 8000 meters = 8.0 km
        assert normalized.distance_km == 8.0
        assert normalized.distance_meters == 8000.0

    def test_seconds_to_minutes_conversion(self, basic_raw_activity):
        """Should convert seconds to minutes (integer division)."""
        normalized = normalize_activity(basic_raw_activity)

        # 2700 seconds = 45 minutes
        assert normalized.duration_minutes == 45
        assert normalized.duration_seconds == 2700


# ============================================================
# FILENAME GENERATION TESTS (3 tests)
# ============================================================


class TestFilenameGeneration:
    """Tests for filename generation."""

    def test_time_based_naming_when_start_time_present(self, temp_repo):
        """Should use HHmm format when start_time is present."""
        activity = NormalizedActivity(
            id="test_1",
            source="strava",
            sport_type=SportType.RUN,
            name="Morning Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 7, 30),
            duration_minutes=45,
            duration_seconds=2700,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        filename = generate_activity_filename(activity, temp_repo)

        assert filename == "activities/2026-01/2026-01-12_run_0730.yaml"

    def test_index_based_naming_when_start_time_missing(self, temp_repo):
        """Should use index when start_time is missing."""
        activity = NormalizedActivity(
            id="test_1",
            source="manual",
            sport_type=SportType.CLIMB,
            name="Bouldering Session",
            date=date(2026, 1, 12),
            start_time=None,
            duration_minutes=120,
            duration_seconds=7200,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        filename = generate_activity_filename(activity, temp_repo)

        assert filename == "activities/2026-01/2026-01-12_climb_1.yaml"

    def test_collision_handling_increments_index(self, temp_repo):
        """Should increment index when filename collision occurs."""
        activity = NormalizedActivity(
            id="test_1",
            source="strava",
            sport_type=SportType.RUN,
            name="Morning Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 7, 30),
            duration_minutes=45,
            duration_seconds=2700,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Create first file to cause collision
        first_path = "activities/2026-01/2026-01-12_run_0730.yaml"
        # Create a proper NormalizedActivity for the first file
        first_activity = NormalizedActivity(
            id="existing_activity",
            source="strava",
            sport_type=SportType.RUN,
            name="Existing Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 7, 30),
            duration_minutes=30,
            duration_seconds=1800,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        temp_repo.write_yaml(first_path, first_activity)

        # Generate filename for second activity at same time
        filename = generate_activity_filename(activity, temp_repo)

        # Should add _2 suffix
        assert filename == "activities/2026-01/2026-01-12_run_0730_2.yaml"


# ============================================================
# VALIDATION TESTS (3 tests)
# ============================================================


class TestActivityValidation:
    """Tests for activity validation."""

    def test_valid_activity_passes_all_checks(self):
        """Valid activity should return empty warnings list."""
        activity = NormalizedActivity(
            id="test_1",
            source="strava",
            sport_type=SportType.RUN,
            name="Morning Run",
            date=date(2026, 1, 12),
            duration_minutes=45,
            duration_seconds=2700,
            distance_km=8.0,
            average_hr=155,
            max_hr=170,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        warnings = validate_activity(activity)

        assert len(warnings) == 0

    def test_unrealistic_pace_triggers_warning(self):
        """Unrealistically fast pace should trigger warning."""
        activity = NormalizedActivity(
            id="test_1",
            source="strava",
            sport_type=SportType.RUN,
            name="Super Fast Run",
            date=date(2026, 1, 12),
            duration_minutes=10,  # 10 minutes
            duration_seconds=600,
            distance_km=10.0,  # 10 km = 1:00/km pace (way too fast)
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        warnings = validate_activity(activity)

        assert len(warnings) > 0
        assert any("pace" in w.lower() for w in warnings)

    def test_invalid_heart_rate_triggers_warning(self):
        """Invalid HR values should trigger warnings."""
        activity = NormalizedActivity(
            id="test_1",
            source="strava",
            sport_type=SportType.RUN,
            name="Run",
            date=date(2026, 1, 12),
            duration_minutes=45,
            duration_seconds=2700,
            average_hr=25,  # Too low
            max_hr=170,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        warnings = validate_activity(activity)

        assert len(warnings) > 0
        assert any("heart rate" in w.lower() for w in warnings)


# ============================================================
# INTEGRATION TESTS (3 tests)
# ============================================================


class TestNormalizationIntegration:
    """Integration tests for full normalization pipeline."""

    def test_full_normalization_pipeline(self, basic_raw_activity):
        """Should run complete normalization successfully."""
        normalized = normalize_activity(basic_raw_activity)

        # Verify all transformations
        assert normalized.id == "strava_12345"
        assert normalized.sport_type == SportType.RUN
        assert normalized.surface_type == SurfaceType.ROAD
        assert normalized.data_quality == DataQuality.HIGH
        assert normalized.duration_minutes == 45
        assert normalized.distance_km == 8.0
        assert normalized.created_at is not None
        assert normalized.synced_at is not None

    def test_normalize_and_persist_creates_file(self, basic_raw_activity, temp_repo):
        """Should normalize and persist activity to disk."""
        result = normalize_and_persist(basic_raw_activity, temp_repo)

        # Verify result
        assert result.activity.id == "strava_12345"
        assert result.was_updated is False  # First time
        assert len(result.warnings) == 0

        # Verify file was created
        assert temp_repo.file_exists(result.file_path)

        # Verify file path format
        assert "activities/2026-01/" in result.file_path
        assert "2026-01-12_run_" in result.file_path

    def test_treadmill_detection_affects_data_quality(self):
        """Treadmill detection should set TREADMILL data quality."""
        raw = RawActivity(
            id="test_treadmill",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Treadmill Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 7, 30),
            duration_seconds=2700,
            distance_meters=8000.0,
            average_hr=155,
            has_hr_data=True,
            has_polyline=False,  # No GPS
        )

        normalized = normalize_activity(raw)

        # Should detect treadmill and set appropriate quality
        assert normalized.surface_type == SurfaceType.TREADMILL
        assert normalized.data_quality == DataQuality.TREADMILL


# ============================================================
# ERROR HANDLING TESTS (2 tests)
# ============================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_sport_type_raises_error(self):
        """Should raise error when sport_type is missing."""
        raw = RawActivity(
            id="test_1",
            source=ActivitySource.STRAVA,
            sport_type="",  # Empty sport type
            name="Test Activity",
            date=date(2026, 1, 12),
            duration_seconds=2700,
        )

        with pytest.raises(InvalidActivityError, match="sport_type is required"):
            normalize_activity(raw)

    def test_invalid_duration_raises_error(self):
        """Should raise error when duration is invalid."""
        raw = RawActivity(
            id="test_1",
            source=ActivitySource.STRAVA,
            sport_type="Run",
            name="Test Activity",
            date=date(2026, 1, 12),
            duration_seconds=0,  # Invalid duration
        )

        with pytest.raises(InvalidActivityError, match="duration_seconds must be positive"):
            normalize_activity(raw)
