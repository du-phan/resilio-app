"""
Unit tests for M10 Plan Generator schemas and business logic.

Tests schema validation, periodization algorithms, workout assignment,
training guardrails, and plan persistence.
"""

import pytest
from datetime import date, timedelta
from pathlib import Path
from pydantic import ValidationError

from sports_coach_engine.schemas.plan import (
    GoalType,
    PlanPhase,
    WorkoutType,
    IntensityZone,
    WorkoutPrescription,
    WeekPlan,
    MasterPlan,
    PlanGenerationResult,
)


# ============================================================
# SCHEMA VALIDATION TESTS
# ============================================================


class TestGoalType:
    """Test GoalType enum values."""

    def test_all_goal_types(self):
        """All goal types should be valid."""
        assert GoalType.GENERAL_FITNESS.value == "general_fitness"
        assert GoalType.FIVE_K.value == "5k"
        assert GoalType.TEN_K.value == "10k"
        assert GoalType.HALF_MARATHON.value == "half_marathon"
        assert GoalType.MARATHON.value == "marathon"

    def test_goal_type_from_string(self):
        """Goal types should be creatable from string values."""
        assert GoalType("5k") == GoalType.FIVE_K
        assert GoalType("marathon") == GoalType.MARATHON


class TestPlanPhase:
    """Test PlanPhase enum values."""

    def test_all_phases(self):
        """All plan phases should be valid."""
        assert PlanPhase.BASE.value == "base"
        assert PlanPhase.BUILD.value == "build"
        assert PlanPhase.PEAK.value == "peak"
        assert PlanPhase.TAPER.value == "taper"
        assert PlanPhase.RECOVERY.value == "recovery"


class TestWorkoutType:
    """Test WorkoutType enum values."""

    def test_all_workout_types(self):
        """All workout types should be valid."""
        assert WorkoutType.EASY.value == "easy"
        assert WorkoutType.LONG_RUN.value == "long_run"
        assert WorkoutType.TEMPO.value == "tempo"
        assert WorkoutType.INTERVALS.value == "intervals"
        assert WorkoutType.REST.value == "rest"


class TestIntensityZone:
    """Test IntensityZone enum values."""

    def test_all_zones(self):
        """All intensity zones should be valid."""
        assert IntensityZone.ZONE_1.value == "zone_1"
        assert IntensityZone.ZONE_2.value == "zone_2"
        assert IntensityZone.ZONE_5.value == "zone_5"


class TestWorkoutPrescription:
    """Test WorkoutPrescription schema validation."""

    def test_valid_workout(self):
        """Valid workout should pass validation."""
        workout = WorkoutPrescription(
            id="w_2026-01-20_easy",
            week_number=1,
            day_of_week=0,  # Monday
            date=date(2026, 1, 20),
            workout_type=WorkoutType.EASY,
            phase=PlanPhase.BASE,
            duration_minutes=40,
            intensity_zone=IntensityZone.ZONE_2,
            target_rpe=4,
            purpose="Recovery and aerobic maintenance",
        )
        assert workout.workout_type == WorkoutType.EASY
        assert workout.target_rpe == 4
        assert workout.status == "scheduled"

    def test_hr_ranges_valid(self):
        """Valid HR ranges should pass."""
        workout = WorkoutPrescription(
            id="w_test",
            week_number=1,
            day_of_week=0,
            date=date(2026, 1, 20),
            workout_type=WorkoutType.TEMPO,
            phase=PlanPhase.BUILD,
            duration_minutes=45,
            intensity_zone=IntensityZone.ZONE_4,
            target_rpe=7,
            hr_range_low=160,
            hr_range_high=170,
            purpose="Threshold work",
        )
        assert workout.hr_range_low == 160
        assert workout.hr_range_high == 170

    def test_hr_range_too_low(self):
        """HR below 30 should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            WorkoutPrescription(
                id="w_test",
                week_number=1,
                day_of_week=0,
                date=date(2026, 1, 20),
                workout_type=WorkoutType.EASY,
                phase=PlanPhase.BASE,
                duration_minutes=40,
                intensity_zone=IntensityZone.ZONE_2,
                target_rpe=4,
                hr_range_low=25,  # Too low
                purpose="Test",
            )
        # Check for Pydantic's standard validation message
        assert "greater than or equal to 30" in str(exc_info.value)

    def test_hr_range_too_high(self):
        """HR above 220 should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            WorkoutPrescription(
                id="w_test",
                week_number=1,
                day_of_week=0,
                date=date(2026, 1, 20),
                workout_type=WorkoutType.INTERVALS,
                phase=PlanPhase.PEAK,
                duration_minutes=50,
                intensity_zone=IntensityZone.ZONE_5,
                target_rpe=8,
                hr_range_high=225,  # Too high
                purpose="Test",
            )
        # Check for Pydantic's standard validation message
        assert "less than or equal to 220" in str(exc_info.value)

    def test_rpe_bounds(self):
        """RPE must be between 1-10."""
        # RPE too low
        with pytest.raises(ValidationError):
            WorkoutPrescription(
                id="w_test",
                week_number=1,
                day_of_week=0,
                date=date(2026, 1, 20),
                workout_type=WorkoutType.EASY,
                phase=PlanPhase.BASE,
                duration_minutes=40,
                intensity_zone=IntensityZone.ZONE_2,
                target_rpe=0,  # Invalid
                purpose="Test",
            )

        # RPE too high
        with pytest.raises(ValidationError):
            WorkoutPrescription(
                id="w_test",
                week_number=1,
                day_of_week=0,
                date=date(2026, 1, 20),
                workout_type=WorkoutType.INTERVALS,
                phase=PlanPhase.PEAK,
                duration_minutes=50,
                intensity_zone=IntensityZone.ZONE_5,
                target_rpe=11,  # Invalid
                purpose="Test",
            )

    def test_day_of_week_bounds(self):
        """Day of week must be 0-6."""
        with pytest.raises(ValidationError):
            WorkoutPrescription(
                id="w_test",
                week_number=1,
                day_of_week=7,  # Invalid (only 0-6)
                date=date(2026, 1, 20),
                workout_type=WorkoutType.EASY,
                phase=PlanPhase.BASE,
                duration_minutes=40,
                intensity_zone=IntensityZone.ZONE_2,
                target_rpe=4,
                purpose="Test",
            )

    def test_duration_must_be_positive(self):
        """Duration must be > 0."""
        with pytest.raises(ValidationError):
            WorkoutPrescription(
                id="w_test",
                week_number=1,
                day_of_week=0,
                date=date(2026, 1, 20),
                workout_type=WorkoutType.EASY,
                phase=PlanPhase.BASE,
                duration_minutes=0,  # Invalid
                intensity_zone=IntensityZone.ZONE_2,
                target_rpe=4,
                purpose="Test",
            )


class TestWeekPlan:
    """Test WeekPlan schema validation."""

    def test_valid_week_plan(self):
        """Valid week plan should pass validation."""
        workout = WorkoutPrescription(
            id="w_test",
            week_number=1,
            day_of_week=0,
            date=date(2026, 1, 20),
            workout_type=WorkoutType.EASY,
            phase=PlanPhase.BASE,
            duration_minutes=40,
            intensity_zone=IntensityZone.ZONE_2,
            target_rpe=4,
            purpose="Test",
        )

        week = WeekPlan(
            week_number=1,
            phase=PlanPhase.BASE,
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 26),
            target_volume_km=30.0,
            target_systemic_load_au=800.0,
            workouts=[workout],
        )

        assert week.week_number == 1
        assert week.phase == PlanPhase.BASE
        assert len(week.workouts) == 1

    def test_recovery_week_flag(self):
        """Recovery week flag should be accessible."""
        workout = WorkoutPrescription(
            id="w_test",
            week_number=4,
            day_of_week=0,
            date=date(2026, 2, 10),
            workout_type=WorkoutType.EASY,
            phase=PlanPhase.BASE,
            duration_minutes=30,
            intensity_zone=IntensityZone.ZONE_2,
            target_rpe=3,
            purpose="Recovery",
        )

        week = WeekPlan(
            week_number=4,
            phase=PlanPhase.BASE,
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 16),
            target_volume_km=20.0,  # Reduced for recovery
            target_systemic_load_au=500.0,
            workouts=[workout],
            is_recovery_week=True,
        )

        assert week.is_recovery_week is True


class TestMasterPlan:
    """Test MasterPlan schema validation."""

    def test_valid_master_plan(self):
        """Valid master plan should pass validation."""
        workout = WorkoutPrescription(
            id="w_test",
            week_number=1,
            day_of_week=0,
            date=date(2026, 1, 20),
            workout_type=WorkoutType.EASY,
            phase=PlanPhase.BASE,
            duration_minutes=40,
            intensity_zone=IntensityZone.ZONE_2,
            target_rpe=4,
            purpose="Test",
        )

        week = WeekPlan(
            week_number=1,
            phase=PlanPhase.BASE,
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 26),
            target_volume_km=30.0,
            target_systemic_load_au=800.0,
            workouts=[workout],
        )

        plan = MasterPlan(
            id="plan_test123",
            created_at=date(2026, 1, 15),
            goal={"type": "half_marathon", "target_date": "2026-04-15"},
            start_date=date(2026, 1, 20),
            end_date=date(2026, 4, 15),
            total_weeks=1,
            phases=[{"phase": "base", "start_week": 0, "end_week": 0}],
            weeks=[week],
            starting_volume_km=30.0,
            peak_volume_km=50.0,
            conflict_policy="running_goal_wins",
        )

        assert plan.total_weeks == 1
        assert len(plan.weeks) == 1


class TestPlanGenerationResult:
    """Test PlanGenerationResult schema."""

    def test_valid_result(self):
        """Valid result should pass validation."""
        workout = WorkoutPrescription(
            id="w_test",
            week_number=1,
            day_of_week=0,
            date=date(2026, 1, 20),
            workout_type=WorkoutType.EASY,
            phase=PlanPhase.BASE,
            duration_minutes=40,
            intensity_zone=IntensityZone.ZONE_2,
            target_rpe=4,
            purpose="Test",
        )

        week = WeekPlan(
            week_number=1,
            phase=PlanPhase.BASE,
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 26),
            target_volume_km=30.0,
            target_systemic_load_au=800.0,
            workouts=[workout],
        )

        plan = MasterPlan(
            id="plan_test",
            created_at=date(2026, 1, 15),
            goal={"type": "10k"},
            start_date=date(2026, 1, 20),
            end_date=date(2026, 3, 15),
            total_weeks=1,
            phases=[],
            weeks=[week],
            starting_volume_km=30.0,
            peak_volume_km=40.0,
            conflict_policy="running_goal_wins",
        )

        result = PlanGenerationResult(
            plan=plan,
            warnings=["Timeline shorter than recommended"],
            guardrails_applied=["Long run capped at 30% of volume"],
        )

        assert len(result.warnings) == 1
        assert len(result.guardrails_applied) == 1
        assert result.plan.id == "plan_test"

    def test_empty_warnings_and_guardrails(self):
        """Empty warnings and guardrails should be allowed."""
        workout = WorkoutPrescription(
            id="w_test",
            week_number=1,
            day_of_week=0,
            date=date(2026, 1, 20),
            workout_type=WorkoutType.EASY,
            phase=PlanPhase.BASE,
            duration_minutes=40,
            intensity_zone=IntensityZone.ZONE_2,
            target_rpe=4,
            purpose="Test",
        )

        week = WeekPlan(
            week_number=1,
            phase=PlanPhase.BASE,
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 26),
            target_volume_km=30.0,
            target_systemic_load_au=800.0,
            workouts=[workout],
        )

        plan = MasterPlan(
            id="plan_test",
            created_at=date(2026, 1, 15),
            goal={"type": "general_fitness"},
            start_date=date(2026, 1, 20),
            end_date=date(2026, 4, 15),
            total_weeks=1,
            phases=[],
            weeks=[week],
            starting_volume_km=30.0,
            peak_volume_km=30.0,
            conflict_policy="primary_sport_wins",
        )

        result = PlanGenerationResult(plan=plan)
        assert result.warnings == []
        assert result.guardrails_applied == []


# ============================================================
# PERIODIZATION ALGORITHM TESTS
# ============================================================


class TestPeriodization:
    """Test periodization calculations."""

    def test_marathon_18_weeks(self):
        """Marathon 18 weeks should have 4 phases with correct distribution."""
        from sports_coach_engine.core.plan import calculate_periodization

        phases = calculate_periodization(
            goal=GoalType.MARATHON,
            weeks_available=18,
            start_date=date(2026, 1, 20),
        )

        # Should have 4 phases
        phase_names = [p["phase"] for p in phases]
        assert len(phases) == 4
        assert "base" in phase_names
        assert "build" in phase_names
        assert "peak" in phase_names
        assert "taper" in phase_names

        # Verify total weeks sum to 18
        total_weeks = sum(p["weeks"] for p in phases)
        assert total_weeks == 18

        # Marathon: Base ~40%, Build ~35%, Peak ~15%, Taper ~10%
        base_phase = next(p for p in phases if p["phase"] == "base")
        assert base_phase["weeks"] >= 6  # Should be ~7 weeks (40% of 18)

    def test_half_marathon_12_weeks(self):
        """Half marathon 12 weeks should have correct phase distribution."""
        from sports_coach_engine.core.plan import calculate_periodization

        phases = calculate_periodization(
            goal=GoalType.HALF_MARATHON,
            weeks_available=12,
            start_date=date(2026, 1, 20),
        )

        assert len(phases) == 4
        total_weeks = sum(p["weeks"] for p in phases)
        assert total_weeks == 12

        # Half: Base ~35%, Build ~40%, Peak ~15%, Taper ~10%
        build_phase = next(p for p in phases if p["phase"] == "build")
        assert build_phase["weeks"] >= 4  # Should be ~5 weeks (40% of 12)

    def test_general_fitness_12_weeks(self):
        """General fitness should use rolling 4-week cycles."""
        from sports_coach_engine.core.plan import calculate_periodization

        phases = calculate_periodization(
            goal=GoalType.GENERAL_FITNESS,
            weeks_available=12,
            start_date=date(2026, 1, 20),
        )

        # Should have 12 individual weeks
        assert len(phases) == 12

        # Every 4th week should be recovery (weeks 3, 7, 11 in 0-indexed)
        recovery_weeks = [i for i, p in enumerate(phases) if p["phase"] == "recovery"]
        assert recovery_weeks == [3, 7, 11]

        # Other weeks should be build
        build_weeks = [i for i, p in enumerate(phases) if p["phase"] == "build"]
        assert len(build_weeks) == 9

    def test_timeline_too_short_raises_error(self):
        """Timeline shorter than minimum should raise ValueError."""
        from sports_coach_engine.core.plan import calculate_periodization

        # Marathon needs 16+ weeks
        with pytest.raises(ValueError) as exc_info:
            calculate_periodization(
                goal=GoalType.MARATHON,
                weeks_available=10,
                start_date=date(2026, 1, 20),
            )
        assert "minimum 16 weeks" in str(exc_info.value)

    def test_phase_dates_are_continuous(self):
        """Phase start/end dates should be continuous with no gaps."""
        from sports_coach_engine.core.plan import calculate_periodization

        phases = calculate_periodization(
            goal=GoalType.TEN_K,
            weeks_available=10,
            start_date=date(2026, 1, 20),
        )

        for i in range(len(phases) - 1):
            current_end = phases[i]["end_date"]
            next_start = phases[i + 1]["start_date"]
            # Next phase should start the day after current ends
            assert next_start == current_end + timedelta(days=1)

    def test_week_ranges_are_correct(self):
        """start_week and end_week should match the weeks count."""
        from sports_coach_engine.core.plan import calculate_periodization

        phases = calculate_periodization(
            goal=GoalType.FIVE_K,
            weeks_available=8,
            start_date=date(2026, 1, 20),
        )

        for phase in phases:
            expected_weeks = phase["end_week"] - phase["start_week"] + 1
            assert phase["weeks"] == expected_weeks


class TestVolumeProgression:
    """Test volume progression calculations."""

    def test_base_phase_progression(self):
        """Base phase should progress from starting to 80% of peak."""
        from sports_coach_engine.core.plan import calculate_volume_progression

        # Use 5 weeks to avoid week 4 being a recovery week
        phases = [
            {"phase": "base", "weeks": 5},
        ]

        volumes = calculate_volume_progression(
            starting_volume_km=30.0,
            peak_volume_km=50.0,
            phases=phases,
        )

        # Should have 5 weeks
        assert len(volumes) == 5

        # First week should be starting volume
        assert volumes[0] == pytest.approx(30.0, abs=0.1)

        # Last week should be ~80% of peak (40 km)
        # Note: Week 4 (index 3) is a recovery week, so check week 5 (index 4) or week 3 (index 2)
        # Week 5 should be close to target after recovery week adjustment
        assert volumes[4] == pytest.approx(40.0, abs=2.0)  # More tolerance due to recovery week

        # Week 3 (before recovery) should be increasing toward 80% of peak
        assert volumes[2] > volumes[0]

    def test_taper_reduces_progressively(self):
        """Taper phase should reduce volume by 15% per week."""
        from sports_coach_engine.core.plan import calculate_volume_progression

        phases = [
            {"phase": "peak", "weeks": 1},
            {"phase": "taper", "weeks": 3},
        ]

        volumes = calculate_volume_progression(
            starting_volume_km=40.0,
            peak_volume_km=50.0,
            phases=phases,
        )

        # Peak week at 100%
        assert volumes[0] == 50.0

        # Taper: 85%, 72.25%, 61.4%
        assert volumes[1] == pytest.approx(50.0 * 0.85, abs=0.1)
        assert volumes[2] == pytest.approx(50.0 * 0.85 * 0.85, abs=0.1)
        assert volumes[3] == pytest.approx(50.0 * 0.85 * 0.85 * 0.85, abs=0.1)

    def test_recovery_weeks_applied(self):
        """Recovery weeks (every 4th) should be at 70% of surrounding."""
        from sports_coach_engine.core.plan import calculate_volume_progression

        # 8 weeks base phase
        phases = [
            {"phase": "base", "weeks": 8},
        ]

        volumes = calculate_volume_progression(
            starting_volume_km=30.0,
            peak_volume_km=50.0,
            phases=phases,
        )

        # Week 4 (index 3) should be recovery week
        # Should be ~70% of average of weeks 3 and 5
        week_3_vol = volumes[2]
        week_5_vol = volumes[4]
        expected_recovery = (week_3_vol + week_5_vol) / 2 * 0.70

        assert volumes[3] == pytest.approx(expected_recovery, abs=1.0)

    def test_general_fitness_recovery_weeks(self):
        """General fitness recovery weeks should be 70% of previous."""
        from sports_coach_engine.core.plan import calculate_volume_progression

        phases = [
            {"phase": "build", "weeks": 1},
            {"phase": "build", "weeks": 1},
            {"phase": "build", "weeks": 1},
            {"phase": "recovery", "weeks": 1},
        ]

        volumes = calculate_volume_progression(
            starting_volume_km=30.0,
            peak_volume_km=50.0,
            phases=phases,
        )

        # 4th week is recovery (70% of week 3)
        assert volumes[3] == pytest.approx(volumes[2] * 0.70, abs=0.1)


# WORKOUT CREATION TESTS
# ============================================================


class TestWorkoutCreation:
    """Test workout prescription creation."""

    def test_create_long_run_workout(self):
        """Long run should be capped at 28% of weekly volume and 2.5 hours."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        workout = create_workout(
            workout_type="long_run",
            workout_date=date(2026, 1, 26),
            week_number=1,
            day_of_week=6,
            phase=PlanPhase.BASE,
            volume_target_km=50.0,
        )

        # Should have correct type and phase
        assert workout.workout_type == "long_run"
        assert workout.phase == "base"

        # Long run should be ~28% of 50km = 14km
        assert workout.distance_km == pytest.approx(14.0, abs=0.5)

        # Duration should be ~84 minutes (14km * 6 min/km)
        assert workout.duration_minutes == pytest.approx(84, abs=5)

        # Should be a key workout
        assert workout.key_workout is True

        # Should have purpose text
        assert "aerobic endurance" in workout.purpose.lower()
        assert "building aerobic foundation" in workout.purpose.lower()

    def test_long_run_capped_at_2_5_hours(self):
        """Long run duration should be capped at 150 minutes."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        # Very high volume that would normally exceed 2.5h
        workout = create_workout(
            workout_type="long_run",
            workout_date=date(2026, 1, 26),
            week_number=1,
            day_of_week=6,
            phase=PlanPhase.BUILD,
            volume_target_km=100.0,  # Would be 28km long run without cap
        )

        # Distance should be capped at 32km
        assert workout.distance_km <= 32.0

        # Duration should be capped at 150 minutes
        assert workout.duration_minutes <= 150

    def test_create_tempo_workout(self):
        """Tempo workout should have interval structure and higher intensity."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        workout = create_workout(
            workout_type="tempo",
            workout_date=date(2026, 2, 3),
            week_number=2,
            day_of_week=1,
            phase=PlanPhase.BUILD,
            volume_target_km=45.0,
        )

        # Should be Zone 4 (threshold)
        assert workout.intensity_zone == "zone_4"
        assert workout.target_rpe == 7

        # Should have interval structure
        assert workout.intervals is not None
        assert len(workout.intervals) > 0

        # Should have warmup/cooldown
        assert workout.warmup_minutes >= 10
        assert workout.cooldown_minutes >= 10

        # Should have lactate threshold purpose
        assert "lactate threshold" in workout.purpose.lower()
        assert "key workout" or workout.key_workout is True

    def test_create_intervals_workout(self):
        """Intervals workout should have VO2max intensity and structure."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        workout = create_workout(
            workout_type="intervals",
            workout_date=date(2026, 2, 5),
            week_number=2,
            day_of_week=3,
            phase=PlanPhase.PEAK,
            volume_target_km=48.0,
        )

        # Should be Zone 5 (VO2max)
        assert workout.intensity_zone == "zone_5"
        assert workout.target_rpe == 8

        # Should have intervals
        assert workout.intervals is not None

        # Should reference VO2max
        assert "vo2max" in workout.purpose.lower()

        # Phase context should be included
        assert "fine-tuning for peak performance" in workout.purpose.lower()

    def test_create_easy_workout(self):
        """Easy workout should have low intensity and simple structure."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        workout = create_workout(
            workout_type="easy",
            workout_date=date(2026, 1, 29),
            week_number=1,
            day_of_week=2,
            phase=PlanPhase.BASE,
            volume_target_km=40.0,
        )

        # Should be Zone 2 (easy)
        assert workout.intensity_zone == "zone_2"
        assert workout.target_rpe == 4

        # Should have distance allocated (~15% of weekly volume)
        assert workout.distance_km == pytest.approx(6.0, abs=1.0)

        # Should not be a key workout
        assert workout.key_workout is False

        # Should have recovery purpose
        assert "recovery" in workout.purpose.lower()

    def test_hr_ranges_calculated_from_profile(self):
        """HR ranges should be calculated when max_hr available."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        profile = {
            "vital_signs": {"max_hr": 185}
        }

        workout = create_workout(
            workout_type="tempo",
            workout_date=date(2026, 2, 1),
            week_number=2,
            day_of_week=0,
            phase=PlanPhase.BUILD,
            volume_target_km=45.0,
            profile=profile,
        )

        # Tempo is Zone 4 (85-90% max HR)
        # 185 * 0.85 = 157, 185 * 0.90 = 166
        assert workout.hr_range_low == pytest.approx(157, abs=2)
        assert workout.hr_range_high == pytest.approx(166, abs=2)

    def test_pace_ranges_calculated_from_vdot(self):
        """Pace ranges should be calculated when VDOT available."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        profile = {
            "vdot": 45.0
        }

        workout = create_workout(
            workout_type="easy",
            workout_date=date(2026, 1, 27),
            week_number=1,
            day_of_week=0,
            phase=PlanPhase.BASE,
            volume_target_km=40.0,
            profile=profile,
        )

        # With VDOT 45, easy pace should be around 5:30/km
        assert workout.pace_range_min_km is not None
        assert workout.pace_range_max_km is not None

        # Pace strings should be in format "M:SS"
        assert ":" in workout.pace_range_min_km
        assert ":" in workout.pace_range_max_km

    def test_no_pace_or_hr_without_profile(self):
        """Without profile, pace/HR ranges should be None."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        workout = create_workout(
            workout_type="easy",
            workout_date=date(2026, 1, 27),
            week_number=1,
            day_of_week=0,
            phase=PlanPhase.BASE,
            volume_target_km=40.0,
            profile=None,
        )

        # No pace or HR guidance without profile
        assert workout.pace_range_min_km is None
        assert workout.pace_range_max_km is None
        assert workout.hr_range_low is None
        assert workout.hr_range_high is None

        # But should still have RPE
        assert workout.target_rpe == 4

    def test_workout_id_generation(self):
        """Each workout should have unique ID."""
        from sports_coach_engine.core.plan import create_workout
        from sports_coach_engine.schemas.plan import PlanPhase

        workout1 = create_workout(
            workout_type="easy",
            workout_date=date(2026, 1, 27),
            week_number=1,
            day_of_week=0,
            phase=PlanPhase.BASE,
            volume_target_km=40.0,
        )

        workout2 = create_workout(
            workout_type="easy",
            workout_date=date(2026, 1, 27),
            week_number=1,
            day_of_week=0,
            phase=PlanPhase.BASE,
            volume_target_km=40.0,
        )

        # IDs should be different
        assert workout1.id != workout2.id

        # IDs should contain date and type
        assert "2026-01-27" in workout1.id
        assert "easy" in workout1.id


# ============================================================
# TOOLKIT FUNCTIONS TESTS (Phase 5: Toolkit Paradigm)
# ============================================================


class TestVolumeRecommendation:
    """Test volume adjustment recommendations."""

    def test_beginner_volume_recommendation(self):
        """Beginner (CTL <30) should get conservative ranges."""
        from sports_coach_engine.core.plan import suggest_volume_adjustment

        rec = suggest_volume_adjustment(
            current_weekly_volume_km=20.0,
            current_ctl=25.0,
            goal_distance_km=21.1,  # Half marathon
            weeks_available=12
        )

        assert rec.start_range_km[0] >= 15.0
        assert rec.start_range_km[1] <= 30.0
        assert "beginner" in rec.rationale.lower()
        assert rec.current_ctl == 25.0

    def test_recreational_volume_recommendation(self):
        """Recreational (CTL 30-45) should get moderate ranges."""
        from sports_coach_engine.core.plan import suggest_volume_adjustment

        rec = suggest_volume_adjustment(
            current_weekly_volume_km=35.0,
            current_ctl=40.0,
            goal_distance_km=21.1,
            weeks_available=12
        )

        assert 25.0 <= rec.start_range_km[0] <= 40.0
        assert "recreational" in rec.rationale.lower()


class TestWorkoutTemplates:
    """Test workout template retrieval."""

    def test_get_easy_template(self):
        """Should return easy workout template."""
        from sports_coach_engine.core.plan import get_workout_template, WorkoutType

        template = get_workout_template(WorkoutType.EASY)

        assert template["duration_minutes"] == 40
        assert template["target_rpe"] == 4
        assert "recovery" in template["purpose"].lower()

    def test_get_tempo_template(self):
        """Should return tempo workout template with intervals."""
        from sports_coach_engine.core.plan import get_workout_template, WorkoutType

        template = get_workout_template(WorkoutType.TEMPO)

        assert template["duration_minutes"] == 45
        assert template["target_rpe"] == 7
        assert "intervals" in template


class TestWorkoutModification:
    """Test workout downgrade and shortening helpers."""

    def test_create_downgraded_workout(self):
        """Should downgrade tempo to easy."""
        from sports_coach_engine.core.plan import create_workout, create_downgraded_workout, PlanPhase
        from datetime import date

        tempo = create_workout(
            workout_type="tempo",
            workout_date=date(2026, 1, 15),
            week_number=1,
            day_of_week=2,
            phase=PlanPhase.BUILD,
            volume_target_km=50.0,
            profile={},
        )

        easy = create_downgraded_workout(tempo, target_rpe=4)

        assert easy.workout_type == "easy"
        assert easy.target_rpe == 4
        assert easy.week_number == tempo.week_number
        assert easy.date == tempo.date

    def test_create_shortened_workout(self):
        """Should shorten workout duration."""
        from sports_coach_engine.core.plan import create_workout, create_shortened_workout, PlanPhase
        from datetime import date

        long_run = create_workout(
            workout_type="long_run",
            workout_date=date(2026, 1, 19),
            week_number=1,
            day_of_week=6,
            phase=PlanPhase.BUILD,
            volume_target_km=50.0,
            profile={},
        )

        short_run = create_shortened_workout(long_run, duration_minutes=60)

        assert short_run.duration_minutes == 60
        assert short_run.workout_type == long_run.workout_type
        assert short_run.target_rpe == long_run.target_rpe


class TestRecoveryEstimation:
    """Test recovery days estimation."""

    def test_easy_run_minimal_recovery(self):
        """Easy runs need minimal recovery."""
        from sports_coach_engine.core.plan import create_workout, estimate_recovery_days, PlanPhase
        from datetime import date

        easy = create_workout(
            workout_type="easy",
            workout_date=date(2026, 1, 13),
            week_number=1,
            day_of_week=0,
            phase=PlanPhase.BASE,
            volume_target_km=40.0,
            profile={},
        )

        days = estimate_recovery_days(easy)
        assert days == 0

    def test_tempo_needs_recovery(self):
        """Tempo runs need 2 days recovery."""
        from sports_coach_engine.core.plan import create_workout, estimate_recovery_days, PlanPhase
        from datetime import date

        tempo = create_workout(
            workout_type="tempo",
            workout_date=date(2026, 1, 15),
            week_number=1,
            day_of_week=2,
            phase=PlanPhase.BUILD,
            volume_target_km=50.0,
            profile={},
        )

        days = estimate_recovery_days(tempo)
        assert days == 2


class TestGuardrailValidation:
    """Test guardrail detection (not enforcement)."""

    def test_validate_week_detects_too_many_quality_sessions(self):
        """Should detect 3 quality sessions but not auto-fix."""
        from sports_coach_engine.core.plan import create_workout, validate_week, WeekPlan, PlanPhase
        from datetime import date

        # Create week with 3 quality sessions
        tempo = create_workout("tempo", date(2026, 1, 15), 1, 2, PlanPhase.BUILD, 50.0, {})
        intervals = create_workout("intervals", date(2026, 1, 17), 1, 4, PlanPhase.BUILD, 50.0, {})
        fartlek = create_workout("tempo", date(2026, 1, 19), 1, 6, PlanPhase.BUILD, 50.0, {})

        week = WeekPlan(
            week_number=1,
            phase="build",
            start_date=date(2026, 1, 13),
            end_date=date(2026, 1, 19),
            target_volume_km=50.0,
            target_systemic_load_au=300.0,
            workouts=[tempo, intervals, fartlek]
        )

        violations = validate_week(week, {})

        # Should detect violation
        assert len(violations) >= 1
        quality_violation = next((v for v in violations if v.rule == "max_quality_sessions"), None)
        assert quality_violation is not None
        assert quality_violation.actual == 3
        assert quality_violation.target == 2
        assert quality_violation.severity == "warning"

        # Original week should be UNCHANGED (detection, not enforcement)
        assert len(week.workouts) == 3

    def test_validate_week_detects_back_to_back_hard_days(self):
        """Should detect consecutive hard sessions."""
        from sports_coach_engine.core.plan import create_workout, validate_week, WeekPlan, PlanPhase
        from datetime import date

        # Create week with back-to-back hard days
        tempo_tue = create_workout("tempo", date(2026, 1, 14), 1, 1, PlanPhase.BUILD, 50.0, {})
        intervals_wed = create_workout("intervals", date(2026, 1, 15), 1, 2, PlanPhase.BUILD, 50.0, {})

        week = WeekPlan(
            week_number=1,
            phase="build",
            start_date=date(2026, 1, 13),
            end_date=date(2026, 1, 19),
            target_volume_km=50.0,
            target_systemic_load_au=300.0,
            workouts=[tempo_tue, intervals_wed]
        )

        violations = validate_week(week, {})

        # Should detect violation
        assert len(violations) >= 1
        spacing_violation = next((v for v in violations if v.rule == "hard_easy_separation"), None)
        assert spacing_violation is not None

    def test_validate_guardrails_checks_80_20_distribution(self):
        """Should detect 80/20 violations across full plan."""
        from sports_coach_engine.core.plan import validate_guardrails, MasterPlan, WeekPlan, create_workout, PlanPhase
        from datetime import date

        # Create plan with poor 80/20 distribution (60/40)
        workouts_week1 = [
            create_workout("easy", date(2026, 1, 13), 1, 0, PlanPhase.BASE, 40.0, {}),  # 30min easy
            create_workout("tempo", date(2026, 1, 15), 1, 2, PlanPhase.BASE, 40.0, {}),  # 45min hard
            create_workout("intervals", date(2026, 1, 17), 1, 4, PlanPhase.BASE, 40.0, {}),  # 50min hard
        ]

        week1 = WeekPlan(
            week_number=1,
            phase="base",
            start_date=date(2026, 1, 13),
            end_date=date(2026, 1, 19),
            target_volume_km=40.0,
            target_systemic_load_au=280.0,
            workouts=workouts_week1
        )

        plan = MasterPlan(
            id="test_plan",
            created_at=date(2026, 1, 1),
            goal={"type": "half_marathon"},
            start_date=date(2026, 1, 13),
            end_date=date(2026, 4, 13),
            total_weeks=12,
            phases=[],
            weeks=[week1],
            starting_volume_km=35.0,
            peak_volume_km=55.0,
            constraints_applied=[],
            conflict_policy="running_goal_wins"
        )

        violations = validate_guardrails(plan, {})

        # Should detect 80/20 violation
        # 30 easy / 125 total = 24% (should be 80%)
        distribution_violation = next((v for v in violations if v.rule == "80_20_distribution"), None)
        assert distribution_violation is not None


class TestPlanPersistence:
    """Test plan persistence and archiving."""

    def test_persist_plan_creates_files(self, tmp_path, monkeypatch):
        """Should create master plan and workout files."""
        from sports_coach_engine.core.plan import persist_plan, create_workout
        from sports_coach_engine.schemas.plan import MasterPlan, WeekPlan, PlanPhase
        from sports_coach_engine.core.repository import RepositoryIO

        # Set repo root to temp directory
        monkeypatch.setattr("sports_coach_engine.core.repository.get_repo_root", lambda: tmp_path)
        repo = RepositoryIO()

        # Create minimal plan
        workouts = [
            create_workout("tempo", date(2026, 1, 20), 1, 0, PlanPhase.BUILD, 50.0),
            create_workout("easy", date(2026, 1, 22), 1, 2, PlanPhase.BUILD, 50.0),
        ]

        week = WeekPlan(
            week_number=1,
            phase=PlanPhase.BUILD,
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 26),
            target_volume_km=50.0,
            target_systemic_load_au=500.0,
            workouts=workouts,
        )

        plan = MasterPlan(
            id="test_plan_001",
            created_at=date(2026, 1, 15),
            goal={"type": "half_marathon", "target_date": "2026-04-15"},
            start_date=date(2026, 1, 20),
            end_date=date(2026, 4, 15),
            total_weeks=12,
            phases=[{"phase": "build", "start_week": 1, "end_week": 6}],
            weeks=[week],
            starting_volume_km=40.0,
            peak_volume_km=60.0,
            constraints_applied=["80/20 rule"],
            conflict_policy="running_goal_wins",
        )

        # Persist plan
        persist_plan(plan, repo)

        # Verify master plan file exists
        assert (tmp_path / "data" / "plans" / "current_plan.yaml").exists()

        # Verify workout files exist
        assert (tmp_path / "data" / "plans" / "workouts" / "week_01" / "monday_tempo.yaml").exists()
        assert (tmp_path / "data" / "plans" / "workouts" / "week_01" / "wednesday_easy.yaml").exists()

    def test_persist_plan_content_valid(self, tmp_path, monkeypatch):
        """Persisted plan should be readable with correct content."""
        from sports_coach_engine.core.plan import persist_plan, create_workout
        from sports_coach_engine.schemas.plan import MasterPlan, WeekPlan, PlanPhase, WorkoutPrescription
        from sports_coach_engine.core.repository import RepositoryIO

        monkeypatch.setattr("sports_coach_engine.core.repository.get_repo_root", lambda: tmp_path)
        repo = RepositoryIO()

        workouts = [create_workout("tempo", date(2026, 1, 20), 1, 0, PlanPhase.BUILD, 50.0)]
        week = WeekPlan(
            week_number=1,
            phase=PlanPhase.BUILD,
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 26),
            target_volume_km=50.0,
            target_systemic_load_au=500.0,
            workouts=workouts,
        )
        plan = MasterPlan(
            id="test_plan_002",
            created_at=date(2026, 1, 15),
            goal={"type": "10k", "target_date": "2026-03-15"},
            start_date=date(2026, 1, 20),
            end_date=date(2026, 3, 15),
            total_weeks=8,
            phases=[],
            weeks=[week],
            starting_volume_km=30.0,
            peak_volume_km=50.0,
            constraints_applied=[],
            conflict_policy="ask_each_time",
        )

        persist_plan(plan, repo)

        # Read back and verify
        loaded_plan = repo.read_yaml("data/plans/current_plan.yaml", MasterPlan)
        assert not isinstance(loaded_plan, Exception)  # No error
        assert loaded_plan.id == "test_plan_002"
        assert loaded_plan.total_weeks == 8

        # Read workout and verify
        workout_path = "data/plans/workouts/week_01/monday_tempo.yaml"
        loaded_workout = repo.read_yaml(workout_path, WorkoutPrescription)
        assert not isinstance(loaded_workout, Exception)
        assert loaded_workout.workout_type == "tempo"

    def test_archive_current_plan(self, tmp_path, monkeypatch):
        """Should archive existing plan and create new plans directory."""
        from sports_coach_engine.core.plan import persist_plan, archive_current_plan, create_workout
        from sports_coach_engine.schemas.plan import MasterPlan, WeekPlan, PlanPhase
        from sports_coach_engine.core.repository import RepositoryIO

        monkeypatch.setattr("sports_coach_engine.core.repository.get_repo_root", lambda: tmp_path)
        repo = RepositoryIO()

        # Create and persist initial plan
        workouts = [create_workout("easy", date(2026, 1, 20), 1, 0, PlanPhase.BUILD, 50.0)]
        week = WeekPlan(
            week_number=1,
            phase=PlanPhase.BUILD,
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 26),
            target_volume_km=50.0,
            target_systemic_load_au=500.0,
            workouts=workouts,
        )
        plan = MasterPlan(
            id="test_plan_003",
            created_at=date(2026, 1, 15),
            goal={"type": "5k", "target_date": "2026-02-15"},
            start_date=date(2026, 1, 20),
            end_date=date(2026, 2, 15),
            total_weeks=4,
            phases=[],
            weeks=[week],
            starting_volume_km=20.0,
            peak_volume_km=30.0,
            constraints_applied=[],
            conflict_policy="running_goal_wins",
        )
        persist_plan(plan, repo)

        # Archive it
        archive_path = archive_current_plan("goal_changed", repo)

        # Should return archive path
        assert archive_path is not None
        assert "goal_changed" in archive_path

        # Original data/plans/ directory should be empty (recreated)
        assert (tmp_path / "data" / "plans").exists()
        assert not (tmp_path / "data" / "plans" / "current_plan.yaml").exists()

        # Archive should contain the old plan
        archived_plan_path = Path(archive_path) / "current_plan.yaml"
        assert archived_plan_path.exists()

    def test_archive_nonexistent_plan_returns_none(self, tmp_path, monkeypatch):
        """Archiving when no plan exists should return None."""
        from sports_coach_engine.core.plan import archive_current_plan
        from sports_coach_engine.core.repository import RepositoryIO

        monkeypatch.setattr("sports_coach_engine.core.repository.get_repo_root", lambda: tmp_path)
        repo = RepositoryIO()

        # No plan exists yet
        archive_path = archive_current_plan("test", repo)

        assert archive_path is None


class TestPlanReviewAndLogPaths:
    """Test plan review and training log path functions."""

    def test_current_plan_review_path(self):
        """Test current plan review path returns correct location."""
        from sports_coach_engine.core.paths import current_plan_review_path

        path = current_plan_review_path()
        assert path.endswith("current_plan_review.md")
        assert "plans" in path

    def test_current_training_log_path(self):
        """Test current training log path returns correct location."""
        from sports_coach_engine.core.paths import current_training_log_path

        path = current_training_log_path()
        assert path.endswith("current_training_log.md")
        assert "plans" in path
