"""
Unit tests for M8 - Load Engine module.

Tests load calculation using two-channel model, sport multipliers,
multiplier adjustments, and session type classification.
"""

import pytest
from datetime import date, datetime
from sports_coach_engine.core.load import (
    compute_load,
    calculate_base_effort,
    get_multipliers,
    adjust_multipliers,
    classify_session_type,
    compute_loads_batch,
    validate_load,
    InvalidLoadInputError,
)
from sports_coach_engine.core.repository import RepositoryIO
from sports_coach_engine.schemas.activity import (
    NormalizedActivity,
    SessionType,
    SportType,
    SurfaceType,
)


# ============================================================
# TEST FIXTURES
# ============================================================


@pytest.fixture
def basic_run_activity():
    """Create basic running activity for testing."""
    return NormalizedActivity(
        id="test_run_1",
        source="strava",
        sport_type=SportType.RUN,
        name="Morning Run",
        date=date(2026, 1, 12),
        start_time=datetime(2026, 1, 12, 7, 30),
        duration_minutes=45,
        duration_seconds=2700,
        distance_km=8.0,
        distance_meters=8000.0,
        average_hr=155,
        has_hr_data=True,
        has_gps_data=True,
        surface_type=SurfaceType.ROAD,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def temp_repo(tmp_path, monkeypatch):
    """Create temporary repository for testing."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return RepositoryIO()


# ============================================================
# LOAD CALCULATION TESTS (6 tests)
# ============================================================


class TestLoadCalculation:
    """Tests for core load calculation."""

    def test_base_effort_calculation(self, basic_run_activity):
        """Base effort should be RPE × duration."""
        load = compute_load(basic_run_activity, estimated_rpe=6)

        # 6 RPE × 45 minutes = 270 AU
        assert load.base_effort_au == 270.0

    def test_road_running_uses_standard_multipliers(self, basic_run_activity):
        """Road running should use 1.0/1.0 multipliers."""
        load = compute_load(basic_run_activity, estimated_rpe=6)

        assert load.systemic_multiplier == 1.0
        assert load.lower_body_multiplier == 1.0
        assert load.systemic_load_au == 270.0
        assert load.lower_body_load_au == 270.0

    def test_treadmill_reduces_lower_body_load(self):
        """Treadmill should reduce lower-body multiplier to 0.9."""
        activity = NormalizedActivity(
            id="test_treadmill",
            source="strava",
            sport_type=SportType.RUN,
            surface_type=SurfaceType.TREADMILL,
            name="Treadmill Run",
            date=date(2026, 1, 12),
            duration_minutes=60,
            duration_seconds=3600,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=5)

        # 5 RPE × 60 min = 300 AU base
        assert load.base_effort_au == 300.0
        assert load.systemic_multiplier == 1.0
        assert load.lower_body_multiplier == 0.9
        assert load.systemic_load_au == 300.0
        assert load.lower_body_load_au == 270.0  # 300 × 0.9

    def test_trail_running_increases_both_loads(self):
        """Trail running should increase both multipliers."""
        activity = NormalizedActivity(
            id="test_trail",
            source="strava",
            sport_type=SportType.TRAIL_RUN,
            surface_type=SurfaceType.TRAIL,
            name="Trail Run",
            date=date(2026, 1, 12),
            duration_minutes=60,
            duration_seconds=3600,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=7)

        # 7 RPE × 60 min = 420 AU base
        assert load.base_effort_au == 420.0
        assert load.systemic_multiplier == 1.05
        assert load.lower_body_multiplier == 1.10
        assert load.systemic_load_au == 441.0  # 420 × 1.05
        assert load.lower_body_load_au == 462.0  # 420 × 1.10

    def test_climbing_is_mostly_upper_body(self):
        """Climbing should have low lower-body multiplier."""
        activity = NormalizedActivity(
            id="test_climb",
            source="strava",
            sport_type=SportType.CLIMB,
            name="Bouldering Session",
            date=date(2026, 1, 12),
            duration_minutes=120,
            duration_seconds=7200,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=6)

        # 6 RPE × 120 min = 720 AU base
        assert load.base_effort_au == 720.0
        assert load.systemic_multiplier == 0.6
        assert load.lower_body_multiplier == 0.1
        assert load.systemic_load_au == 432.0  # 720 × 0.6
        assert load.lower_body_load_au == 72.0  # 720 × 0.1

    def test_unknown_sports_use_conservative_defaults(self):
        """Unknown sports should use conservative multipliers."""
        activity = NormalizedActivity(
            id="test_other",
            source="manual",
            sport_type=SportType.OTHER,
            name="Paddleboarding",
            date=date(2026, 1, 12),
            duration_minutes=90,
            duration_seconds=5400,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=5)

        # Should use OTHER multipliers (0.7, 0.3)
        assert load.systemic_multiplier == 0.7
        assert load.lower_body_multiplier == 0.3


# ============================================================
# MULTIPLIER ADJUSTMENT TESTS (4 tests)
# ============================================================


class TestMultiplierAdjustments:
    """Tests for multiplier adjustments."""

    def test_leg_day_increases_lower_body_multiplier(self):
        """Leg-focused strength should add +0.25 lower-body."""
        activity = NormalizedActivity(
            id="test_strength",
            source="manual",
            sport_type=SportType.STRENGTH,
            name="Leg Day",
            description="Squats and deadlifts",
            date=date(2026, 1, 12),
            duration_minutes=60,
            duration_seconds=3600,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=7)

        # Base: 0.55 systemic, 0.40 lower-body
        # Leg day: +0.25 lower-body
        assert load.systemic_multiplier == 0.55
        assert load.lower_body_multiplier == 0.65  # 0.40 + 0.25
        assert "Leg-focused strength" in load.multiplier_adjustments[0]

    def test_upper_body_day_decreases_lower_body_multiplier(self):
        """Upper-body strength should reduce lower-body multiplier."""
        activity = NormalizedActivity(
            id="test_strength",
            source="manual",
            sport_type=SportType.STRENGTH,
            name="Upper Body Workout",
            description="Bench press and pull-ups",
            date=date(2026, 1, 12),
            duration_minutes=60,
            duration_seconds=3600,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=6)

        # Base: 0.55 systemic, 0.40 lower-body
        # Upper-body: -0.15 lower-body (but minimum 0.15)
        assert load.systemic_multiplier == 0.55
        assert load.lower_body_multiplier == 0.25  # 0.40 - 0.15
        assert "Upper-body strength" in load.multiplier_adjustments[0]

    def test_high_elevation_increases_both_multipliers(self):
        """High elevation should increase both multipliers."""
        activity = NormalizedActivity(
            id="test_hill_run",
            source="strava",
            sport_type=SportType.RUN,
            name="Hill Repeats",
            date=date(2026, 1, 12),
            duration_minutes=45,
            duration_seconds=2700,
            distance_km=6.0,
            distance_meters=6000.0,
            elevation_gain_m=250.0,  # 250m / 6km = 41.7 m/km
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=8)

        # Base: 1.0, 1.0
        # High elevation: +0.05 systemic, +0.10 lower-body
        assert load.systemic_multiplier == 1.05
        assert load.lower_body_multiplier == 1.10
        assert any("High elevation" in adj for adj in load.multiplier_adjustments)

    def test_race_effort_increases_systemic_multiplier(self):
        """Race effort should increase systemic multiplier."""
        activity = NormalizedActivity(
            id="test_race",
            source="strava",
            sport_type=SportType.RUN,
            name="10K Race",
            date=date(2026, 1, 12),
            duration_minutes=47,
            duration_seconds=2820,
            workout_type=1,  # Strava race flag
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=9)

        # Base: 1.0, 1.0
        # Race: +0.10 systemic
        assert load.systemic_multiplier == 1.10
        assert load.lower_body_multiplier == 1.0
        assert "Race effort" in load.multiplier_adjustments[0]


# ============================================================
# SESSION CLASSIFICATION TESTS (3 tests)
# ============================================================


class TestSessionClassification:
    """Tests for session type classification."""

    def test_rpe_ranges_map_correctly_to_session_types(self):
        """RPE ranges should classify session types correctly."""
        # Easy: RPE 1-4
        assert classify_session_type(2) == SessionType.EASY
        assert classify_session_type(4) == SessionType.EASY

        # Moderate: RPE 5-6
        assert classify_session_type(5) == SessionType.MODERATE
        assert classify_session_type(6) == SessionType.MODERATE

        # Quality: RPE 7-8
        assert classify_session_type(7) == SessionType.QUALITY
        assert classify_session_type(8) == SessionType.QUALITY

        # Race: RPE 9-10
        assert classify_session_type(9) == SessionType.RACE
        assert classify_session_type(10) == SessionType.RACE

    def test_workout_type_race_overrides_rpe(self):
        """workout_type=1 should override RPE classification."""
        # Even with low RPE, race flag should classify as RACE
        assert classify_session_type(5, workout_type=1) == SessionType.RACE
        assert classify_session_type(7, workout_type=1) == SessionType.RACE

    def test_session_type_included_in_load_calculation(self, basic_run_activity):
        """Session type should be included in LoadCalculation."""
        # Easy run
        load_easy = compute_load(basic_run_activity, estimated_rpe=3)
        assert load_easy.session_type == SessionType.EASY

        # Quality workout
        load_quality = compute_load(basic_run_activity, estimated_rpe=7)
        assert load_quality.session_type == SessionType.QUALITY


# ============================================================
# EDGE CASE TESTS (3 tests)
# ============================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_duration_raises_error(self):
        """Zero duration should raise InvalidLoadInputError."""
        activity = NormalizedActivity(
            id="test_invalid",
            source="manual",
            sport_type=SportType.RUN,
            name="Invalid",
            date=date(2026, 1, 12),
            duration_minutes=0,  # Invalid
            duration_seconds=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        with pytest.raises(InvalidLoadInputError, match="duration_minutes must be positive"):
            compute_load(activity, estimated_rpe=5)

    def test_invalid_rpe_raises_error(self, basic_run_activity):
        """RPE outside 1-10 range should raise error."""
        with pytest.raises(InvalidLoadInputError, match="RPE must be 1-10"):
            compute_load(basic_run_activity, estimated_rpe=0)

        with pytest.raises(InvalidLoadInputError, match="RPE must be 1-10"):
            compute_load(basic_run_activity, estimated_rpe=11)

    def test_long_duration_adjustment(self):
        """Duration >120min should increase systemic multiplier."""
        activity = NormalizedActivity(
            id="test_long",
            source="strava",
            sport_type=SportType.RUN,
            name="Long Run",
            date=date(2026, 1, 12),
            duration_minutes=150,  # >120 minutes
            duration_seconds=9000,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=5)

        # Base: 1.0, 1.0
        # Long duration: +0.05 systemic
        assert load.systemic_multiplier == 1.05
        assert "Long duration" in load.multiplier_adjustments[0]


# ============================================================
# VALIDATION TESTS (3 tests)
# ============================================================


class TestLoadValidation:
    """Tests for load validation."""

    def test_valid_load_passes_all_checks(self, basic_run_activity):
        """Valid load should return empty warnings list."""
        load = compute_load(basic_run_activity, estimated_rpe=6)
        warnings = validate_load(load)

        assert len(warnings) == 0

    def test_inconsistent_session_type_triggers_warning(self, basic_run_activity):
        """Session type inconsistent with RPE should trigger warning."""
        # Force an inconsistency by manually creating LoadCalculation
        # (This shouldn't happen in practice, but tests validation logic)
        from sports_coach_engine.schemas.activity import LoadCalculation

        load = LoadCalculation(
            activity_id="test",
            duration_minutes=45,
            estimated_rpe=8,  # High RPE
            sport_type="run",
            surface_type="road",
            base_effort_au=360.0,
            systemic_multiplier=1.0,
            lower_body_multiplier=1.0,
            systemic_load_au=360.0,
            lower_body_load_au=360.0,
            session_type=SessionType.EASY,  # Inconsistent: marked EASY but RPE=8
            multiplier_adjustments=[],
        )

        warnings = validate_load(load)
        assert len(warnings) > 0
        assert any("EASY" in w for w in warnings)

    def test_extreme_multipliers_trigger_warning(self, basic_run_activity):
        """Multipliers outside reasonable range should trigger warning."""
        from sports_coach_engine.schemas.activity import LoadCalculation

        load = LoadCalculation(
            activity_id="test",
            duration_minutes=45,
            estimated_rpe=6,
            sport_type="run",
            surface_type="road",
            base_effort_au=270.0,
            systemic_multiplier=2.5,  # Too high
            lower_body_multiplier=1.0,
            systemic_load_au=675.0,
            lower_body_load_au=270.0,
            session_type=SessionType.MODERATE,
            multiplier_adjustments=[],
        )

        warnings = validate_load(load)
        assert len(warnings) > 0
        assert any("multiplier outside expected range" in w for w in warnings)


# ============================================================
# BATCH OPERATIONS TESTS (2 tests)
# ============================================================


class TestBatchOperations:
    """Tests for batch load calculations."""

    def test_compute_loads_batch(self):
        """Should compute loads for multiple activities."""
        activities = [
            (
                NormalizedActivity(
                    id="run_1",
                    source="strava",
                    sport_type=SportType.RUN,
                    name="Run 1",
                    date=date(2026, 1, 12),
                    duration_minutes=45,
                    duration_seconds=2700,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                ),
                6,
            ),
            (
                NormalizedActivity(
                    id="climb_1",
                    source="manual",
                    sport_type=SportType.CLIMB,
                    name="Climb 1",
                    date=date(2026, 1, 12),
                    duration_minutes=120,
                    duration_seconds=7200,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                ),
                7,
            ),
        ]

        loads = compute_loads_batch(activities)

        assert len(loads) == 2
        assert loads[0].activity_id == "run_1"
        assert loads[0].base_effort_au == 270.0
        assert loads[1].activity_id == "climb_1"
        assert loads[1].base_effort_au == 840.0

    def test_batch_skips_invalid_activities(self):
        """Batch should skip activities with invalid data."""
        activities = [
            # Valid activity
            (
                NormalizedActivity(
                    id="valid",
                    source="strava",
                    sport_type=SportType.RUN,
                    name="Valid",
                    date=date(2026, 1, 12),
                    duration_minutes=45,
                    duration_seconds=2700,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                ),
                6,
            ),
            # Invalid activity (zero duration)
            (
                NormalizedActivity(
                    id="invalid",
                    source="manual",
                    sport_type=SportType.RUN,
                    name="Invalid",
                    date=date(2026, 1, 12),
                    duration_minutes=0,
                    duration_seconds=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                ),
                5,
            ),
        ]

        loads = compute_loads_batch(activities)

        # Should only return valid activity
        assert len(loads) == 1
        assert loads[0].activity_id == "valid"


# ============================================================
# INTEGRATION TESTS (2 tests)
# ============================================================


class TestLoadIntegration:
    """Integration tests for full load calculation pipeline."""

    def test_full_load_calculation_pipeline(self):
        """Should run complete load calculation successfully."""
        activity = NormalizedActivity(
            id="integration_test",
            source="strava",
            sport_type=SportType.TRAIL_RUN,
            surface_type=SurfaceType.TRAIL,
            name="Trail Run with Elevation",
            date=date(2026, 1, 12),
            duration_minutes=90,
            duration_seconds=5400,
            distance_km=12.0,
            distance_meters=12000.0,
            elevation_gain_m=400.0,  # ~33 m/km gradient
            average_hr=165,
            has_hr_data=True,
            has_gps_data=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        load = compute_load(activity, estimated_rpe=7)

        # Verify all transformations
        assert load.activity_id == "integration_test"
        assert load.base_effort_au == 630.0  # 7 × 90
        assert load.session_type == SessionType.QUALITY
        # Trail base (1.05, 1.10) + elevation adjustment
        assert load.systemic_multiplier == pytest.approx(1.10)  # 1.05 + 0.05
        assert load.lower_body_multiplier == pytest.approx(1.20)  # 1.10 + 0.10
        assert load.systemic_load_au == pytest.approx(693.0)  # 630 × 1.10
        assert load.lower_body_load_au == pytest.approx(756.0)  # 630 × 1.20
        assert len(load.multiplier_adjustments) > 0

        # Validate
        warnings = validate_load(load)
        assert len(warnings) == 0

    def test_multi_sport_day_different_loads(self):
        """Different sports should produce different load profiles."""
        # Morning run
        run = NormalizedActivity(
            id="morning_run",
            source="strava",
            sport_type=SportType.RUN,
            name="Easy Run",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 7, 0),
            duration_minutes=30,
            duration_seconds=1800,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Evening climb
        climb = NormalizedActivity(
            id="evening_climb",
            source="manual",
            sport_type=SportType.CLIMB,
            name="Bouldering",
            date=date(2026, 1, 12),
            start_time=datetime(2026, 1, 12, 19, 0),
            duration_minutes=90,
            duration_seconds=5400,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        run_load = compute_load(run, estimated_rpe=4)
        climb_load = compute_load(climb, estimated_rpe=6)

        # Different load profiles
        # Run: higher lower-body multiplier (legs are primary)
        # Climb: lower lower-body multiplier (upper-body dominant)
        assert run_load.lower_body_multiplier > climb_load.lower_body_multiplier
        assert run_load.systemic_multiplier > climb_load.systemic_multiplier

        # Even with lower RPE and shorter duration, run has higher lower-body load
        # because of multiplier difference
        assert run_load.lower_body_load_au > climb_load.lower_body_load_au
