"""
Unit tests for VDOT pace analysis module - HR-based easy pace detection and VDOT inference.

Tests quality workout detection, HR-based easy pace classification, and VDOT inference.
"""

import pytest
from datetime import date, datetime, timedelta

from resilio.core.vdot.pace_analysis import (
    calculate_easy_hr_range,
    is_easy_effort_by_hr,
    is_quality_workout,
    find_vdot_from_pace,
    find_vdot_from_easy_pace,
    analyze_recent_paces,
)
from resilio.schemas.activity import NormalizedActivity


def create_run(
    activity_date: date,
    distance_km: float = 5.0,
    duration_seconds: int = 1800,
    name: str = "Run",
    average_hr: int = None,
    is_treadmill: bool = False
) -> NormalizedActivity:
    """Helper to create a run activity with specific properties."""
    from resilio.schemas.activity import SportType, SurfaceType, DataQuality

    duration_minutes = int(duration_seconds / 60)
    sport_type = SportType.TREADMILL_RUN if is_treadmill else SportType.RUN
    surface_type = SurfaceType.TREADMILL if is_treadmill else SurfaceType.ROAD
    has_gps_data = not is_treadmill

    return NormalizedActivity(
        id=f"test_{activity_date.isoformat()}_{name}",
        source="manual",
        date=activity_date,
        sport_type=sport_type,
        name=name,
        duration_minutes=duration_minutes,
        duration_seconds=duration_seconds,
        distance_km=distance_km,
        elevation_gain_m=0,
        average_hr=average_hr,
        has_gps_data=has_gps_data,
        surface_type=surface_type,
        data_quality=DataQuality.MEDIUM,
        description=None,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


class TestHRBasedDetection:
    """Tests for HR-based easy pace detection."""

    def test_calculate_easy_hr_range(self):
        """Easy HR range should be 65-78% of max HR."""
        max_hr = 200
        min_hr, max_hr_zone = calculate_easy_hr_range(max_hr)

        assert min_hr == 130  # 200 * 0.65
        assert max_hr_zone == 156  # 200 * 0.78

    def test_is_easy_effort_within_range(self):
        """Activity with HR in easy range should be detected."""
        max_hr = 200
        activity = create_run(
            activity_date=date(2026, 2, 1),
            average_hr=145  # 72.5% of max (within 65-78%)
        )

        assert is_easy_effort_by_hr(activity, max_hr) is True

    def test_is_easy_effort_too_high(self):
        """Activity with HR above easy range should not be detected."""
        max_hr = 200
        activity = create_run(
            activity_date=date(2026, 2, 1),
            average_hr=170  # 85% of max (too high)
        )

        assert is_easy_effort_by_hr(activity, max_hr) is False

    def test_is_easy_effort_too_low(self):
        """Activity with HR below easy range should not be detected."""
        max_hr = 200
        activity = create_run(
            activity_date=date(2026, 2, 1),
            average_hr=120  # 60% of max (too low)
        )

        assert is_easy_effort_by_hr(activity, max_hr) is False

    def test_is_easy_effort_no_hr_data(self):
        """Activity without HR data should return False."""
        max_hr = 200
        activity = create_run(
            activity_date=date(2026, 2, 1),
            average_hr=None  # No HR data
        )

        assert is_easy_effort_by_hr(activity, max_hr) is False


class TestQualityWorkoutDetection:
    """Tests for quality workout keyword detection."""

    def test_tempo_keyword_detected(self):
        """Tempo keyword in title should be detected."""
        activity = create_run(
            activity_date=date(2026, 2, 1),
            name="Tempo Run"
        )

        assert is_quality_workout(activity) is True

    def test_threshold_keyword_detected(self):
        """Threshold keyword in title should be detected."""
        activity = create_run(
            activity_date=date(2026, 2, 1),
            name="Threshold Workout"
        )

        assert is_quality_workout(activity) is True

    def test_interval_keyword_detected(self):
        """Interval keyword in title should be detected."""
        activity = create_run(
            activity_date=date(2026, 2, 1),
            name="8x400m Intervals"
        )

        assert is_quality_workout(activity) is True

    def test_easy_run_not_quality(self):
        """Easy run should not be detected as quality."""
        activity = create_run(
            activity_date=date(2026, 2, 1),
            name="Easy Morning Run"
        )

        assert is_quality_workout(activity) is False

    def test_long_run_not_quality(self):
        """Long run without keywords should not be detected as quality."""
        activity = create_run(
            activity_date=date(2026, 2, 1),
            name="Long Run"
        )

        assert is_quality_workout(activity) is False


class TestVDOTInference:
    """Tests for VDOT inference from paces."""

    def test_find_vdot_from_threshold_pace(self):
        """Threshold pace should map to appropriate VDOT."""
        # Rough approximation: 5:00/km threshold → VDOT ~45
        vdot = find_vdot_from_pace(300, "threshold")  # 5:00/km

        assert vdot is not None
        assert 40 <= vdot <= 50  # Should be in reasonable range

    def test_find_vdot_from_easy_pace(self):
        """Easy pace should map to appropriate VDOT."""
        # Rough approximation: 6:30/km easy → VDOT ~35-40
        vdot = find_vdot_from_easy_pace(390)  # 6:30/km

        assert vdot is not None
        assert 30 <= vdot <= 45  # Should be in reasonable range

    def test_find_vdot_out_of_range_pace(self):
        """Very slow pace should return None."""
        vdot = find_vdot_from_pace(600, "threshold")  # 10:00/km (too slow)

        # May return None or lowest VDOT depending on table
        assert vdot is None or vdot == 30

    def test_find_vdot_invalid_zone(self):
        """Invalid zone type should return None."""
        vdot = find_vdot_from_pace(300, "invalid_zone")

        assert vdot is None


class TestRecentPaceAnalysis:
    """Tests for complete pace analysis workflow."""

    def test_quality_workouts_detected(self):
        """Quality workouts should be detected and analyzed."""
        max_hr = 200
        today = date.today()

        activities = [
            # Quality workout: tempo at 5:00/km
            create_run(
                activity_date=today - timedelta(days=3),
                name="Tempo Run",
                distance_km=8.0,
                duration_seconds=40 * 60,  # 40 minutes = 5:00/km
                average_hr=165
            ),
            # Easy run: 6:30/km
            create_run(
                activity_date=today - timedelta(days=1),
                name="Easy Recovery",
                distance_km=5.0,
                duration_seconds=32 * 60 + 30,  # 32:30 = 6:30/km
                average_hr=145
            )
        ]

        result = analyze_recent_paces(activities, lookback_days=7, max_hr=max_hr)

        # Should detect quality workout
        assert len(result.quality_workouts) == 1
        assert result.quality_workouts[0].workout_type in ["tempo", "interval"]
        assert result.quality_workouts[0].implied_vdot > 0

    def test_easy_runs_detected_by_hr(self):
        """Easy runs should be detected by HR zone."""
        max_hr = 200
        today = date.today()

        activities = [
            # Easy run: 6:30/km at 145 bpm (72.5% max)
            create_run(
                activity_date=today - timedelta(days=1),
                name="Morning Run",  # No "easy" keyword
                distance_km=5.0,
                duration_seconds=32 * 60 + 30,  # 6:30/km
                average_hr=145  # Easy zone
            ),
            # Easy run: 6:45/km at 150 bpm (75% max)
            create_run(
                activity_date=today - timedelta(days=3),
                name="Recovery Jog",
                distance_km=5.0,
                duration_seconds=33 * 60 + 45,  # 6:45/km
                average_hr=150  # Easy zone
            )
        ]

        result = analyze_recent_paces(activities, lookback_days=7, max_hr=max_hr)

        # Should detect both easy runs by HR
        assert len(result.easy_runs) == 2
        assert result.detection_method == "heart_rate"
        assert all(er.detected_by == "heart_rate" for er in result.easy_runs)
        assert all(er.average_hr is not None for er in result.easy_runs)

    def test_no_hr_data_flag_set(self):
        """No HR data should set no_hr_data flag."""
        today = date.today()

        activities = [
            create_run(
                activity_date=today - timedelta(days=1),
                name="Morning Run",
                average_hr=None  # No HR data
            )
        ]

        result = analyze_recent_paces(activities, lookback_days=7, max_hr=None)

        assert result.no_hr_data is True
        assert result.detection_method == "none"

    def test_implied_vdot_range_calculated(self):
        """Implied VDOT range should span all detected runs."""
        max_hr = 200
        today = date.today()

        activities = [
            # Fast quality workout
            create_run(
                activity_date=today - timedelta(days=2),
                name="Tempo Run",
                distance_km=8.0,
                duration_seconds=40 * 60,  # 5:00/km
                average_hr=165
            ),
            # Slow easy run
            create_run(
                activity_date=today - timedelta(days=1),
                name="Easy Recovery",
                distance_km=5.0,
                duration_seconds=35 * 60,  # 7:00/km
                average_hr=140
            )
        ]

        result = analyze_recent_paces(activities, lookback_days=7, max_hr=max_hr)

        # Should have VDOT range
        assert result.implied_vdot_range is not None
        vdot_min, vdot_max = result.implied_vdot_range
        assert vdot_min < vdot_max
        assert vdot_min >= 30
        assert vdot_max <= 85

    def test_treadmill_runs_excluded(self):
        """Treadmill runs should be excluded from analysis."""
        max_hr = 200
        today = date.today()

        activities = [
            # Treadmill run (unreliable pace)
            create_run(
                activity_date=today - timedelta(days=1),
                name="Treadmill Run",
                distance_km=5.0,
                duration_seconds=30 * 60,
                average_hr=145,
                is_treadmill=True  # Treadmill flag
            )
        ]

        result = analyze_recent_paces(activities, lookback_days=7, max_hr=max_hr)

        # Should exclude treadmill runs
        assert len(result.quality_workouts) == 0
        assert len(result.easy_runs) == 0

    def test_short_runs_excluded(self):
        """Runs <1km or <5min should be excluded."""
        max_hr = 200
        today = date.today()

        activities = [
            # Too short (warmup)
            create_run(
                activity_date=today - timedelta(days=1),
                name="Warmup",
                distance_km=0.8,  # <1km
                duration_seconds=4 * 60,
                average_hr=120
            )
        ]

        result = analyze_recent_paces(activities, lookback_days=7, max_hr=max_hr)

        # Should exclude short runs
        assert len(result.quality_workouts) == 0
        assert len(result.easy_runs) == 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_activities_list(self):
        """Empty activities should return empty result."""
        result = analyze_recent_paces([], lookback_days=7, max_hr=200)

        assert len(result.quality_workouts) == 0
        assert len(result.easy_runs) == 0
        assert result.implied_vdot_range is None
        assert result.detection_method == "none"

    def test_quality_and_easy_not_double_counted(self):
        """Run should not be counted as both quality and easy."""
        max_hr = 200
        today = date.today()

        activities = [
            # Tempo run with easy HR (conflicting signals)
            create_run(
                activity_date=today - timedelta(days=1),
                name="Tempo Run",  # Quality keyword
                distance_km=8.0,
                duration_seconds=40 * 60,  # 5:00/km
                average_hr=145  # Easy zone HR
            )
        ]

        result = analyze_recent_paces(activities, lookback_days=7, max_hr=max_hr)

        # Should be quality (keyword takes precedence)
        assert len(result.quality_workouts) == 1
        assert len(result.easy_runs) == 0  # Not double-counted
