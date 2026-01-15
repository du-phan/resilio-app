"""Unit tests for validation API functions."""

import pytest
from datetime import date, timedelta
from sports_coach_engine.api.validation import (
    api_validate_interval_structure,
    api_validate_plan_structure,
    api_assess_goal_feasibility,
    ValidationError,
)
from sports_coach_engine.schemas.validation import (
    IntervalStructureValidation,
    PlanStructureValidation,
    GoalFeasibilityAssessment,
)


class TestValidateIntervalStructure:
    """Tests for api_validate_interval_structure()."""

    @pytest.fixture
    def valid_ipace_work_bouts(self):
        """Valid I-pace work bouts (4 minutes each)."""
        return [
            {"duration_minutes": 4.0, "pace_per_km_seconds": 270, "distance_km": 1.0},
            {"duration_minutes": 4.0, "pace_per_km_seconds": 270, "distance_km": 1.0},
            {"duration_minutes": 4.0, "pace_per_km_seconds": 270, "distance_km": 1.0},
        ]

    @pytest.fixture
    def valid_ipace_recovery_bouts(self):
        """Valid I-pace recovery bouts (equal to work time)."""
        return [
            {"duration_minutes": 4.0, "type": "jog"},
            {"duration_minutes": 4.0, "type": "jog"},
            {"duration_minutes": 4.0, "type": "jog"},
        ]

    def test_valid_ipace_intervals(self, valid_ipace_work_bouts, valid_ipace_recovery_bouts):
        """Valid I-pace intervals return IntervalStructureValidation."""
        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=valid_ipace_work_bouts,
            recovery_bouts=valid_ipace_recovery_bouts,
            weekly_volume_km=50.0,
        )

        assert isinstance(result, IntervalStructureValidation)
        assert result.workout_type == "intervals"
        assert result.intensity == "I-pace"
        assert result.daniels_compliance is True
        assert len(result.violations) == 0
        assert result.total_work_volume_minutes == 12.0  # 3 x 4min
        assert result.total_work_volume_km == 3.0  # 3 x 1km
        assert result.total_volume_ok is True  # 3km < 4km (8% of 50km)

    def test_work_bout_too_short(self, valid_ipace_recovery_bouts):
        """Work bout below minimum duration triggers violation."""
        work_bouts = [
            {"duration_minutes": 2.0, "pace_per_km_seconds": 270, "distance_km": 0.5},
        ]
        recovery_bouts = [{"duration_minutes": 2.0, "type": "jog"}]

        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=work_bouts,
            recovery_bouts=recovery_bouts,
        )

        assert isinstance(result, IntervalStructureValidation)
        assert result.daniels_compliance is False
        assert len(result.violations) == 1
        assert result.violations[0].type == "I_PACE_WORK_BOUT_TOO_SHORT"

    def test_work_bout_too_long(self, valid_ipace_recovery_bouts):
        """Work bout above maximum duration triggers violation."""
        work_bouts = [
            {"duration_minutes": 6.0, "pace_per_km_seconds": 270, "distance_km": 1.5},
        ]
        recovery_bouts = [{"duration_minutes": 6.0, "type": "jog"}]

        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=work_bouts,
            recovery_bouts=recovery_bouts,
        )

        assert isinstance(result, IntervalStructureValidation)
        assert result.daniels_compliance is False
        assert len(result.violations) == 1
        assert result.violations[0].type == "I_PACE_WORK_BOUT_TOO_LONG"

    def test_recovery_too_short(self, valid_ipace_work_bouts):
        """Recovery shorter than work bout triggers violation."""
        recovery_bouts = [
            {"duration_minutes": 2.0, "type": "jog"},  # Half of work bout
            {"duration_minutes": 2.0, "type": "jog"},
            {"duration_minutes": 2.0, "type": "jog"},
        ]

        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=valid_ipace_work_bouts,
            recovery_bouts=recovery_bouts,
        )

        assert isinstance(result, IntervalStructureValidation)
        assert result.daniels_compliance is False
        assert any(v.type == "I_PACE_RECOVERY_TOO_SHORT" for v in result.violations)

    def test_total_volume_exceeded(self, valid_ipace_work_bouts, valid_ipace_recovery_bouts):
        """Total I-pace volume exceeding 8% weekly limit triggers violation."""
        # 6 x 1km = 6km, but 8% of 50km = 4km
        work_bouts = valid_ipace_work_bouts * 2  # 6 bouts
        recovery_bouts = valid_ipace_recovery_bouts * 2

        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=work_bouts,
            recovery_bouts=recovery_bouts,
            weekly_volume_km=50.0,
        )

        assert isinstance(result, IntervalStructureValidation)
        assert result.total_volume_ok is False
        assert any(v.type == "I_PACE_TOTAL_VOLUME_EXCEEDED" for v in result.violations)

    def test_tpace_intervals_valid(self):
        """Valid T-pace intervals with 1min recovery per 5min work."""
        work_bouts = [
            {"duration_minutes": 10.0, "pace_per_km_seconds": 300, "distance_km": 2.0},
            {"duration_minutes": 10.0, "pace_per_km_seconds": 300, "distance_km": 2.0},
        ]
        recovery_bouts = [
            {"duration_minutes": 2.0, "type": "jog"},  # 1min per 5min work
            {"duration_minutes": 2.0, "type": "jog"},
        ]

        result = api_validate_interval_structure(
            workout_type="tempo_intervals",
            intensity="T-pace",
            work_bouts=work_bouts,
            recovery_bouts=recovery_bouts,
            weekly_volume_km=50.0,
        )

        assert isinstance(result, IntervalStructureValidation)
        assert result.daniels_compliance is True
        assert len(result.violations) == 0
        assert result.total_work_volume_km == 4.0  # 2 x 2km
        assert result.total_volume_ok is True  # 4km < 5km (10% of 50km)

    def test_rpace_intervals_valid(self):
        """Valid R-pace intervals with 2-3x recovery."""
        work_bouts = [
            {"duration_minutes": 1.0, "pace_per_km_seconds": 240, "distance_km": 0.25},
            {"duration_minutes": 1.0, "pace_per_km_seconds": 240, "distance_km": 0.25},
        ]
        recovery_bouts = [
            {"duration_minutes": 2.5, "type": "walk"},  # 2.5x recovery
            {"duration_minutes": 2.5, "type": "walk"},
        ]

        result = api_validate_interval_structure(
            workout_type="repetitions",
            intensity="R-pace",
            work_bouts=work_bouts,
            recovery_bouts=recovery_bouts,
            weekly_volume_km=50.0,
        )

        assert isinstance(result, IntervalStructureValidation)
        assert result.daniels_compliance is True
        assert len(result.violations) == 0

    def test_invalid_workout_type(self, valid_ipace_work_bouts, valid_ipace_recovery_bouts):
        """Empty workout type returns ValidationError."""
        result = api_validate_interval_structure(
            workout_type="",
            intensity="I-pace",
            work_bouts=valid_ipace_work_bouts,
            recovery_bouts=valid_ipace_recovery_bouts,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_WORKOUT_TYPE"

    def test_invalid_intensity(self, valid_ipace_work_bouts, valid_ipace_recovery_bouts):
        """Empty intensity returns ValidationError."""
        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="",
            work_bouts=valid_ipace_work_bouts,
            recovery_bouts=valid_ipace_recovery_bouts,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_INTENSITY"

    def test_empty_work_bouts(self, valid_ipace_recovery_bouts):
        """Empty work_bouts list returns ValidationError."""
        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=[],
            recovery_bouts=valid_ipace_recovery_bouts,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_WORK_BOUTS"

    def test_invalid_work_bout_structure(self, valid_ipace_recovery_bouts):
        """Work bout missing duration_minutes returns ValidationError."""
        work_bouts = [
            {"pace_per_km_seconds": 270, "distance_km": 1.0},  # Missing duration_minutes
        ]

        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=work_bouts,
            recovery_bouts=valid_ipace_recovery_bouts,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "MISSING_WORK_BOUT_DURATION"

    def test_negative_weekly_volume(self, valid_ipace_work_bouts, valid_ipace_recovery_bouts):
        """Negative weekly volume returns ValidationError."""
        result = api_validate_interval_structure(
            workout_type="intervals",
            intensity="I-pace",
            work_bouts=valid_ipace_work_bouts,
            recovery_bouts=valid_ipace_recovery_bouts,
            weekly_volume_km=-10.0,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_WEEKLY_VOLUME"


class TestValidatePlanStructure:
    """Tests for api_validate_plan_structure()."""

    @pytest.fixture
    def valid_half_marathon_plan(self):
        """Valid 20-week half marathon plan data."""
        return {
            "total_weeks": 20,
            "goal_type": "half_marathon",
            "phases": {"base": 8, "build": 8, "peak": 2, "taper": 2},
            "weekly_volumes_km": [
                25, 27, 29, 22,  # Base weeks 1-4 (recovery)
                31, 33, 35, 28,  # Base weeks 5-8 (recovery)
                37, 40, 43, 35,  # Build weeks 9-12 (recovery)
                46, 50, 54, 43,  # Build weeks 13-16 (recovery)
                60, 58,          # Peak weeks 17-18
                35, 20,          # Taper weeks 19-20
            ],
            "recovery_weeks": [4, 8, 12, 16],
            "race_week": 20,
        }

    def test_valid_plan(self, valid_half_marathon_plan):
        """Valid plan returns PlanStructureValidation with reasonable score."""
        result = api_validate_plan_structure(**valid_half_marathon_plan)

        assert isinstance(result, PlanStructureValidation)
        assert result.total_weeks == 20
        assert result.goal_type == "half_marathon"
        assert result.overall_quality_score >= 60
        # Peak phase (2 weeks) may be flagged as short (recommend 3-5 for half marathon)
        # This brings score down to 60% (3 of 5 checks pass)

    def test_phase_too_short(self):
        """Phase below minimum weeks triggers violation."""
        result = api_validate_plan_structure(
            total_weeks=10,
            goal_type="half_marathon",
            phases={"base": 4, "build": 4, "peak": 1, "taper": 1},  # Peak too short
            weekly_volumes_km=[20, 22, 24, 26, 28, 30, 32, 34, 28, 15],
            recovery_weeks=[4, 8],
            race_week=10,
        )

        assert isinstance(result, PlanStructureValidation)
        assert any(v.type == "PEAK_PHASE_TOO_SHORT" for v in result.violations)

    def test_aggressive_volume_progression(self):
        """Volume increasing >10% per week triggers violation."""
        result = api_validate_plan_structure(
            total_weeks=10,
            goal_type="10k",
            phases={"base": 6, "build": 2, "peak": 1, "taper": 1},
            weekly_volumes_km=[20, 24, 29, 35, 42, 50, 60, 72, 50, 25],  # ~20% increase per week
            recovery_weeks=[3, 6],
            race_week=10,
        )

        assert isinstance(result, PlanStructureValidation)
        assert any(v.type == "VOLUME_PROGRESSION_TOO_AGGRESSIVE" for v in result.violations)
        assert result.volume_progression_check.safe is False

    def test_peak_too_close_to_race(self):
        """Peak week 1 week before race triggers violation."""
        weekly_volumes = [20, 22, 24, 26, 28, 30, 32, 34, 36, 40]  # Peak at week 10
        weekly_volumes.append(25)  # Week 11 (race week)

        result = api_validate_plan_structure(
            total_weeks=11,
            goal_type="10k",
            phases={"base": 6, "build": 3, "peak": 1, "taper": 1},
            weekly_volumes_km=weekly_volumes,
            recovery_weeks=[4, 8],
            race_week=11,
        )

        assert isinstance(result, PlanStructureValidation)
        assert any(v.type == "PEAK_TOO_CLOSE_TO_RACE" for v in result.violations)

    def test_no_recovery_weeks(self):
        """Plan with no recovery weeks triggers violation."""
        result = api_validate_plan_structure(
            total_weeks=10,
            goal_type="10k",
            phases={"base": 6, "build": 2, "peak": 1, "taper": 1},
            weekly_volumes_km=[20, 22, 24, 26, 28, 30, 32, 34, 28, 15],
            recovery_weeks=[],  # No recovery weeks
            race_week=10,
        )

        assert isinstance(result, PlanStructureValidation)
        assert any(v.type == "NO_RECOVERY_WEEKS" for v in result.violations)

    def test_recovery_weeks_too_infrequent(self):
        """Recovery weeks every 6 weeks triggers violation."""
        result = api_validate_plan_structure(
            total_weeks=18,
            goal_type="half_marathon",
            phases={"base": 10, "build": 6, "peak": 1, "taper": 1},
            weekly_volumes_km=[20] * 18,
            recovery_weeks=[6, 12],  # Every 6 weeks
            race_week=18,
        )

        assert isinstance(result, PlanStructureValidation)
        assert any(v.type == "RECOVERY_WEEKS_TOO_INFREQUENT" for v in result.violations)

    def test_invalid_total_weeks(self):
        """Zero total weeks returns ValidationError."""
        result = api_validate_plan_structure(
            total_weeks=0,
            goal_type="10k",
            phases={"base": 4},
            weekly_volumes_km=[20, 22],
            recovery_weeks=[2],
            race_week=2,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_TOTAL_WEEKS"

    def test_invalid_goal_type(self):
        """Empty goal type returns ValidationError."""
        result = api_validate_plan_structure(
            total_weeks=10,
            goal_type="",
            phases={"base": 8, "taper": 2},
            weekly_volumes_km=[20] * 10,
            recovery_weeks=[4],
            race_week=10,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_GOAL_TYPE"

    def test_race_week_exceeds_total(self):
        """Race week beyond total weeks returns ValidationError."""
        result = api_validate_plan_structure(
            total_weeks=10,
            goal_type="10k",
            phases={"base": 8, "taper": 2},
            weekly_volumes_km=[20] * 10,
            recovery_weeks=[4],
            race_week=15,  # Beyond total weeks
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "RACE_WEEK_OUT_OF_RANGE"


class TestAssessGoalFeasibility:
    """Tests for api_assess_goal_feasibility()."""

    def test_realistic_goal(self):
        """Realistic goal with sufficient time returns REALISTIC verdict."""
        goal_date = date.today() + timedelta(weeks=20)

        result = api_assess_goal_feasibility(
            goal_type="half_marathon",
            goal_time_seconds=5400,  # 1:30:00
            goal_date=goal_date,
            current_vdot=48,
            current_ctl=44.0,
            vdot_for_goal=52,  # 4-point gap
        )

        assert isinstance(result, GoalFeasibilityAssessment)
        assert "half marathon" in result.goal.lower()  # Note: space, not underscore
        assert result.feasibility_verdict in ["REALISTIC", "AMBITIOUS_BUT_REALISTIC", "VERY_REALISTIC"]
        assert result.time_available.weeks_until_race == 20

    def test_unrealistic_goal_insufficient_time(self):
        """Goal with insufficient training time returns UNREALISTIC."""
        goal_date = date.today() + timedelta(weeks=4)  # Only 4 weeks

        result = api_assess_goal_feasibility(
            goal_type="marathon",
            goal_time_seconds=10800,  # 3:00:00
            goal_date=goal_date,
            current_vdot=45,
            current_ctl=30.0,
            vdot_for_goal=58,  # Large gap
        )

        assert isinstance(result, GoalFeasibilityAssessment)
        assert result.feasibility_verdict == "UNREALISTIC"
        assert result.time_available.sufficient is False
        assert len(result.warnings) > 0

    def test_ambitious_goal_large_vdot_gap(self):
        """Goal requiring large VDOT improvement returns AMBITIOUS."""
        goal_date = date.today() + timedelta(weeks=16)

        result = api_assess_goal_feasibility(
            goal_type="10k",
            goal_time_seconds=2400,  # 40:00
            goal_date=goal_date,
            current_vdot=40,
            current_ctl=35.0,
            vdot_for_goal=50,  # 10-point gap (25% improvement)
        )

        assert isinstance(result, GoalFeasibilityAssessment)
        assert result.feasibility_verdict == "AMBITIOUS"
        assert result.feasibility_analysis.limiting_factor == "large_vdot_gap"

    def test_goal_without_vdot(self):
        """Goal assessment without VDOT still works (CTL-based)."""
        goal_date = date.today() + timedelta(weeks=16)

        result = api_assess_goal_feasibility(
            goal_type="half_marathon",
            goal_time_seconds=5400,  # 1:30:00
            goal_date=goal_date,
            current_vdot=None,  # No VDOT
            current_ctl=44.0,
            vdot_for_goal=None,
        )

        assert isinstance(result, GoalFeasibilityAssessment)
        assert result.current_fitness.vdot is None
        assert result.feasibility_verdict in ["REALISTIC", "AMBITIOUS_BUT_REALISTIC", "VERY_REALISTIC"]
        # Should still provide recommendations based on CTL

    def test_goal_date_as_string(self):
        """Goal date as ISO string is parsed correctly."""
        goal_date_str = (date.today() + timedelta(weeks=20)).isoformat()

        result = api_assess_goal_feasibility(
            goal_type="10k",
            goal_time_seconds=2700,  # 45:00
            goal_date=goal_date_str,
            current_vdot=45,
            current_ctl=38.0,
            vdot_for_goal=47,
        )

        assert isinstance(result, GoalFeasibilityAssessment)
        assert result.time_available.weeks_until_race == 20

    def test_invalid_goal_type(self):
        """Empty goal type returns ValidationError."""
        goal_date = date.today() + timedelta(weeks=16)

        result = api_assess_goal_feasibility(
            goal_type="",
            goal_time_seconds=2700,
            goal_date=goal_date,
            current_vdot=45,
            current_ctl=38.0,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_GOAL_TYPE"

    def test_invalid_goal_time(self):
        """Negative goal time returns ValidationError."""
        goal_date = date.today() + timedelta(weeks=16)

        result = api_assess_goal_feasibility(
            goal_type="10k",
            goal_time_seconds=-100,
            goal_date=goal_date,
            current_vdot=45,
            current_ctl=38.0,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_GOAL_TIME"

    def test_goal_date_in_past(self):
        """Goal date in past returns ValidationError."""
        goal_date = date.today() - timedelta(days=30)

        result = api_assess_goal_feasibility(
            goal_type="10k",
            goal_time_seconds=2700,
            goal_date=goal_date,
            current_vdot=45,
            current_ctl=38.0,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "GOAL_DATE_IN_PAST"

    def test_invalid_goal_date_format(self):
        """Invalid date string format returns ValidationError."""
        result = api_assess_goal_feasibility(
            goal_type="10k",
            goal_time_seconds=2700,
            goal_date="2026-13-45",  # Invalid date
            current_vdot=45,
            current_ctl=38.0,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_GOAL_DATE"

    def test_negative_current_ctl(self):
        """Negative CTL returns ValidationError."""
        goal_date = date.today() + timedelta(weeks=16)

        result = api_assess_goal_feasibility(
            goal_type="10k",
            goal_time_seconds=2700,
            goal_date=goal_date,
            current_vdot=45,
            current_ctl=-10.0,
        )

        assert isinstance(result, ValidationError)
        assert result.error_type == "INVALID_CURRENT_CTL"
