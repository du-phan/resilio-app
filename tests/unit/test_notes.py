"""
Unit tests for M7 - Notes & RPE Analyzer (Toolkit Paradigm).

Tests quantitative toolkit functions:
- RPE estimation from multiple sources (HR, pace, Strava, duration)
- Treadmill detection using multi-signal scoring
- Integration with activity analysis

Qualitative functions (injury/illness extraction, RPE conflict resolution)
are handled by Claude Code and are not tested here.
"""

import pytest
from datetime import date, datetime, timezone
from sports_coach_engine.core.notes import (
    analyze_activity,
    estimate_rpe,
    estimate_rpe_from_hr,
    estimate_rpe_from_pace,
    estimate_rpe_from_strava_relative,
    estimate_rpe_from_duration,
    detect_treadmill,
    AnalysisError,
    InsufficientDataError,
)
from sports_coach_engine.schemas.activity import (
    NormalizedActivity,
    SportType,
    SurfaceType,
    DataQuality,
    RPESource,
)
from sports_coach_engine.schemas.profile import (
    AthleteProfile,
    VitalSigns,
    Goal,
    GoalType,
    TrainingConstraints,
    Weekday,
    RunningPriority,
    ConflictPolicy,
)


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture
def basic_athlete():
    """Basic athlete profile for testing."""
    return AthleteProfile(
        name="Test Athlete",
        created_at="2026-01-01",
        vital_signs=VitalSigns(
            max_hr=185,
            lthr=165,
            weight_kg=70,
        ),
        vdot=45.0,  # VDOT for pace-based estimation
        constraints=TrainingConstraints(
            available_run_days=[
                Weekday.MONDAY,
                Weekday.WEDNESDAY,
                Weekday.FRIDAY,
                Weekday.SATURDAY,
            ],
            min_run_days_per_week=3,
            max_run_days_per_week=5,
        ),
        running_priority=RunningPriority.PRIMARY,
        conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS,
        goal=Goal(type=GoalType.HALF_MARATHON),
    )


@pytest.fixture
def basic_activity():
    """Basic normalized activity for testing."""
    return NormalizedActivity(
        id="test_activity_001",
        source="strava",
        sport_type=SportType.RUN,
        name="Morning Run",
        date=date(2026, 1, 10),
        duration_minutes=45,
        duration_seconds=2700,
        distance_km=7.0,
        distance_meters=7000,
        has_hr_data=True,
        average_hr=150.0,
        max_hr=175.0,
        created_at=datetime(2026, 1, 10, 7, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 10, 7, 50, 0, tzinfo=timezone.utc),
        data_quality=DataQuality.HIGH,
        surface_type=SurfaceType.ROAD,
    )


# ============================================================
# RPE ESTIMATION TESTS (Quantitative Toolkit Functions)
# ============================================================


class TestRPEEstimation:
    """Tests for RPE estimation from quantitative sources."""

    def test_user_input_included_in_estimates(self, basic_activity, basic_athlete):
        """User-entered RPE should be included in estimates list."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = 6

        estimates = estimate_rpe(activity, basic_athlete)

        # Find user input estimate
        user_estimate = next(
            (e for e in estimates if e.source == RPESource.USER_INPUT), None
        )
        assert user_estimate is not None
        assert user_estimate.value == 6
        assert user_estimate.confidence == "high"
        assert "explicitly entered" in user_estimate.reasoning.lower()

    def test_hr_based_estimation_zone_mapping(self, basic_activity, basic_athlete):
        """HR-based estimation should map % max HR to RPE zones."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.average_hr = 160.0  # 86.5% of max HR (185) → RPE 7

        estimates = estimate_rpe(activity, basic_athlete)

        # Find HR-based estimate
        hr_estimate = next(
            (e for e in estimates if e.source == RPESource.HR_BASED), None
        )
        assert hr_estimate is not None
        assert hr_estimate.value == 7
        assert "86%" in hr_estimate.reasoning

    def test_pace_based_estimation_for_running(self, basic_activity, basic_athlete):
        """Pace-based estimation should work for running activities with VDOT."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        # 7km in 2700s = 385.7s/km = 6:26/km (easy pace for VDOT 45)
        activity.distance_km = 7.0
        activity.duration_seconds = 2700

        estimates = estimate_rpe(activity, basic_athlete)

        # Find pace-based estimate
        pace_estimate = next(
            (e for e in estimates if e.source == RPESource.PACE_BASED), None
        )
        assert pace_estimate is not None
        assert pace_estimate.value == 4  # Easy pace
        assert pace_estimate.confidence == "high"
        assert "easy" in pace_estimate.reasoning.lower()

    def test_pace_based_skipped_without_vdot(self, basic_activity):
        """Pace-based estimation should be skipped if no VDOT available."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None

        # Athlete without VDOT
        athlete = AthleteProfile(
            name="Test Athlete",
            created_at="2026-01-01",
            vital_signs=VitalSigns(max_hr=185),
            vdot=None,  # No VDOT
            constraints=TrainingConstraints(
                available_run_days=[Weekday.MONDAY],
                min_run_days_per_week=1,
                max_run_days_per_week=5,
            ),
            running_priority=RunningPriority.PRIMARY,
            conflict_policy=ConflictPolicy.RUNNING_GOAL_WINS,
            goal=Goal(type=GoalType.GENERAL_FITNESS),
        )

        estimates = estimate_rpe(activity, athlete)

        # Should not have pace-based estimate
        pace_estimate = next(
            (e for e in estimates if e.source == RPESource.PACE_BASED), None
        )
        assert pace_estimate is None

    def test_strava_suffer_score_normalization(self, basic_activity, basic_athlete):
        """Strava suffer_score should normalize to RPE scale."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.suffer_score = 120  # 120 / 45min = 2.67 per min → RPE 7

        estimates = estimate_rpe(activity, basic_athlete)

        # Find Strava-based estimate
        strava_estimate = next(
            (e for e in estimates if e.source == RPESource.STRAVA_RELATIVE), None
        )
        assert strava_estimate is not None
        assert 6 <= strava_estimate.value <= 8
        assert "suffer score" in strava_estimate.reasoning.lower()

    def test_duration_heuristic_always_available(self, basic_activity, basic_athlete):
        """Duration heuristic should always provide a fallback estimate."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = None
        activity.has_hr_data = False
        activity.average_hr = None
        activity.suffer_score = None
        activity.distance_km = None  # No pace data

        estimates = estimate_rpe(activity, basic_athlete)

        # Should have duration heuristic
        duration_estimate = next(
            (e for e in estimates if e.source == RPESource.DURATION_HEURISTIC), None
        )
        assert duration_estimate is not None
        assert 3 <= duration_estimate.value <= 6
        assert duration_estimate.confidence == "low"

    def test_multiple_estimates_returned(self, basic_activity, basic_athlete):
        """Should return multiple estimates without resolution."""
        activity = basic_activity.model_copy()
        activity.perceived_exertion = 8  # User input
        activity.average_hr = 160.0  # HR-based
        activity.suffer_score = 120  # Strava-based
        # Also has pace data for pace-based

        estimates = estimate_rpe(activity, basic_athlete)

        # Should have at least 4 sources (user, HR, pace, Strava, duration)
        assert len(estimates) >= 4
        sources = {e.source for e in estimates}
        assert RPESource.USER_INPUT in sources
        assert RPESource.HR_BASED in sources
        assert RPESource.PACE_BASED in sources
        assert RPESource.STRAVA_RELATIVE in sources
        assert RPESource.DURATION_HEURISTIC in sources


class TestPaceBasedRPE:
    """Tests for pace-based RPE estimation using VDOT."""

    def test_easy_pace_returns_rpe_4(self):
        """Easy pace (slower than marathon) should return RPE 4."""
        # VDOT 45: easy pace = 5:30/km (330s)
        # Test with 6:00/km (360s) - slower than easy
        estimate = estimate_rpe_from_pace(
            avg_pace_per_km=360.0, athlete_vdot=45.0, sport_type="run"
        )

        assert estimate is not None
        assert estimate.value == 4
        assert estimate.source == RPESource.PACE_BASED
        assert "easy" in estimate.reasoning.lower()

    def test_tempo_pace_returns_rpe_7(self):
        """Tempo pace should return RPE 7."""
        # VDOT 45: tempo pace = 5:05/km (305s)
        estimate = estimate_rpe_from_pace(
            avg_pace_per_km=305.0, athlete_vdot=45.0, sport_type="run"
        )

        assert estimate is not None
        assert estimate.value == 7
        assert "tempo" in estimate.reasoning.lower()

    def test_interval_pace_returns_rpe_8(self):
        """Interval pace should return RPE 8."""
        # VDOT 45: interval pace = 4:32/km (272s)
        estimate = estimate_rpe_from_pace(
            avg_pace_per_km=272.0, athlete_vdot=45.0, sport_type="run"
        )

        assert estimate is not None
        assert estimate.value == 8
        assert "interval" in estimate.reasoning.lower()

    def test_trail_running_adds_one_rpe(self):
        """Trail running should add +1 RPE to account for terrain."""
        # Easy pace on trail
        estimate = estimate_rpe_from_pace(
            avg_pace_per_km=360.0, athlete_vdot=45.0, sport_type="trail_run"
        )

        assert estimate is not None
        assert estimate.value == 5  # Easy (4) + trail (+1)
        assert "trail" in estimate.reasoning.lower()

    def test_returns_none_without_pace_data(self):
        """Should return None if pace data unavailable."""
        estimate = estimate_rpe_from_pace(
            avg_pace_per_km=None, athlete_vdot=45.0, sport_type="run"
        )

        assert estimate is None

    def test_returns_none_without_vdot(self):
        """Should return None if VDOT unavailable."""
        estimate = estimate_rpe_from_pace(
            avg_pace_per_km=360.0, athlete_vdot=None, sport_type="run"
        )

        assert estimate is None


# ============================================================
# TREADMILL DETECTION TESTS
# ============================================================


class TestTreadmillDetection:
    """Tests for treadmill/indoor activity detection."""

    def test_detects_treadmill_from_title(self):
        """Should detect treadmill from activity title keywords."""
        detection = detect_treadmill(
            activity_name="Treadmill Run",
            description=None,
            has_gps=True,
            sport_type="run",
            sub_type=None,
            device_name=None,
        )

        assert detection.is_treadmill is True
        assert detection.confidence == "high"
        assert "title" in " ".join(detection.signals).lower()

    def test_detects_indoor_from_no_gps(self):
        """Should detect indoor activity from lack of GPS."""
        detection = detect_treadmill(
            activity_name="Morning Run",
            description=None,
            has_gps=False,
            sport_type="run",
            sub_type=None,
            device_name=None,
        )

        assert detection.is_treadmill is True
        assert "no gps" in " ".join(detection.signals).lower()

    def test_detects_zwift_from_description(self):
        """Should detect Zwift/indoor from description."""
        detection = detect_treadmill(
            activity_name="Run",
            description="Zwift workout",
            has_gps=False,
            sport_type="run",
            sub_type=None,
            device_name=None,
        )

        assert detection.is_treadmill is True
        assert "description" in " ".join(detection.signals).lower()

    def test_outdoor_run_not_detected_as_treadmill(self):
        """Outdoor run with GPS should not be detected as treadmill."""
        detection = detect_treadmill(
            activity_name="Morning Run",
            description="Beautiful weather today",
            has_gps=True,
            sport_type="run",
            sub_type=None,
            device_name=None,
        )

        assert detection.is_treadmill is False


# ============================================================
# ANALYSIS INTEGRATION TESTS
# ============================================================


class TestAnalysisIntegration:
    """Tests for complete activity analysis integration."""

    def test_analyze_activity_returns_multiple_rpe_estimates(
        self, basic_activity, basic_athlete
    ):
        """analyze_activity should return multiple RPE estimates."""
        result = analyze_activity(basic_activity, basic_athlete)

        assert result.activity_id == basic_activity.id
        assert len(result.rpe_estimates) >= 2  # At least HR + duration
        assert result.treadmill_detection is not None
        assert result.analyzed_at is not None

    def test_analyze_activity_includes_treadmill_detection(
        self, basic_activity, basic_athlete
    ):
        """Should include treadmill detection results."""
        activity = basic_activity.model_copy()
        activity.has_gps_data = False
        activity.name = "Treadmill Run"

        result = analyze_activity(activity, basic_athlete)

        assert result.treadmill_detection.is_treadmill is True

    def test_analyze_activity_sets_notes_present_flag(
        self, basic_activity, basic_athlete
    ):
        """Should set notes_present flag when notes available."""
        activity = basic_activity.model_copy()
        activity.description = "Felt good today"

        result = analyze_activity(activity, basic_athlete)

        assert result.notes_present is True

    def test_analyze_activity_with_no_notes(self, basic_activity, basic_athlete):
        """Should handle activity with no notes."""
        activity = basic_activity.model_copy()
        activity.description = None
        activity.private_note = None

        result = analyze_activity(activity, basic_athlete)

        assert result.notes_present is False
        assert len(result.rpe_estimates) >= 1  # Still has quantitative estimates


# ============================================================
# HELPER FUNCTION TESTS
# ============================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_estimate_rpe_from_hr_returns_estimate(self):
        """estimate_rpe_from_hr should return valid RPE estimate."""
        estimate = estimate_rpe_from_hr(
            average_hr=160,
            max_hr_activity=175,
            athlete_max_hr=185,
            athlete_lthr=165,
            duration_minutes=45,
        )

        assert estimate is not None
        assert 1 <= estimate.value <= 10
        assert estimate.source == RPESource.HR_BASED
        assert estimate.confidence in ["low", "medium", "high"]

    def test_estimate_rpe_from_duration_always_returns(self):
        """Duration heuristic should always return an estimate."""
        estimate = estimate_rpe_from_duration(sport_type="run", duration_minutes=45)

        assert estimate is not None
        assert 1 <= estimate.value <= 10
        assert estimate.source == RPESource.DURATION_HEURISTIC


# ============================================================
# ERROR HANDLING TESTS
# ============================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_analyze_activity_handles_missing_hr_data(
        self, basic_activity, basic_athlete
    ):
        """Should gracefully handle missing HR data."""
        activity = basic_activity.model_copy()
        activity.has_hr_data = False
        activity.average_hr = None

        result = analyze_activity(activity, basic_athlete)

        # Should still return estimates (pace, duration)
        assert len(result.rpe_estimates) >= 1

    def test_analyze_activity_handles_missing_pace_data(
        self, basic_activity, basic_athlete
    ):
        """Should gracefully handle missing pace data."""
        activity = basic_activity.model_copy()
        activity.distance_km = None

        result = analyze_activity(activity, basic_athlete)

        # Should still return estimates (HR, duration)
        assert len(result.rpe_estimates) >= 1

    def test_estimate_rpe_from_hr_returns_none_without_hr(self):
        """Should return None if HR data insufficient."""
        estimate = estimate_rpe_from_hr(
            average_hr=None,
            max_hr_activity=None,
            athlete_max_hr=None,
            athlete_lthr=None,
            duration_minutes=45,
        )

        assert estimate is None
