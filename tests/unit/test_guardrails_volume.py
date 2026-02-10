"""
Unit tests for guardrails volume validation module.

Tests volume guardrails based on Daniels' Running Formula:
- Quality volume validation (T/I/R pace limits)
- Weekly progression (10% rule)
- Long run limits
- Safe volume range calculations
"""

import pytest
from sports_coach_engine.core.guardrails.volume import (
    validate_quality_volume,
    validate_weekly_progression,
    validate_long_run_limits,
    validate_weekly_volume_feasibility,
    calculate_safe_volume_range,
    analyze_weekly_progression_context,
)


# ============================================================
# QUALITY VOLUME VALIDATION TESTS
# ============================================================


class TestQualityVolumeValidation:
    """Tests for T/I/R pace volume validation against Daniels' limits."""

    def test_all_volumes_within_limits(self):
        """All quality volumes within Daniels' constraints should pass."""
        result = validate_quality_volume(
            t_pace_km=3.0,      # 6% of weekly (< 10% limit)
            i_pace_km=4.0,      # 8% of weekly (= 8% limit)
            r_pace_km=2.0,      # 4% of weekly (< 5% limit)
            weekly_mileage_km=50.0,
        )

        assert result.overall_ok is True
        assert result.t_pace_ok is True
        assert result.i_pace_ok is True
        assert result.r_pace_ok is True
        assert len(result.violations) == 0

    def test_t_pace_exceeds_10_percent(self):
        """T-pace exceeding 10% of weekly mileage should create violation."""
        result = validate_quality_volume(
            t_pace_km=6.0,      # 12% of weekly (> 10% limit)
            i_pace_km=3.0,
            r_pace_km=2.0,
            weekly_mileage_km=50.0,
        )

        assert result.overall_ok is False
        assert result.t_pace_ok is False
        assert result.t_pace_limit_km == 5.0  # 10% of 50km
        assert len(result.violations) == 1
        assert result.violations[0].type == "T_PACE_VOLUME_EXCEEDED"

    def test_i_pace_exceeds_8_percent_limit(self):
        """I-pace exceeding 8% of weekly mileage should create violation."""
        result = validate_quality_volume(
            t_pace_km=3.0,
            i_pace_km=6.0,      # 12% of weekly (> 8% limit)
            r_pace_km=2.0,
            weekly_mileage_km=50.0,
        )

        assert result.overall_ok is False
        assert result.i_pace_ok is False
        assert result.i_pace_limit_km == 4.0  # 8% of 50km = 4.0
        assert len(result.violations) == 1
        assert result.violations[0].type == "I_PACE_VOLUME_EXCEEDED"

    def test_i_pace_exceeds_10km_absolute_limit(self):
        """I-pace exceeding 10km absolute limit should create violation."""
        result = validate_quality_volume(
            t_pace_km=8.0,
            i_pace_km=12.0,     # > 10km absolute limit
            r_pace_km=3.0,
            weekly_mileage_km=150.0,  # High weekly so 8% would be 12km, but 10km is max
        )

        assert result.overall_ok is False
        assert result.i_pace_ok is False
        assert result.i_pace_limit_km == 10.0  # lesser of 10km or 12km (8% of 150)

    def test_r_pace_exceeds_5_percent_limit(self):
        """R-pace exceeding 5% of weekly mileage should create violation."""
        result = validate_quality_volume(
            t_pace_km=3.0,
            i_pace_km=4.0,
            r_pace_km=4.0,      # 8% of weekly (> 5% limit)
            weekly_mileage_km=50.0,
        )

        assert result.overall_ok is False
        assert result.r_pace_ok is False
        assert result.r_pace_limit_km == 2.5  # 5% of 50km
        assert len(result.violations) == 1
        assert result.violations[0].type == "R_PACE_VOLUME_EXCEEDED"

    def test_r_pace_exceeds_8km_absolute_limit(self):
        """R-pace exceeding 8km absolute limit should create violation."""
        result = validate_quality_volume(
            t_pace_km=10.0,
            i_pace_km=8.0,
            r_pace_km=10.0,     # > 8km absolute limit
            weekly_mileage_km=200.0,  # High weekly so 5% would be 10km, but 8km is max
        )

        assert result.overall_ok is False
        assert result.r_pace_ok is False
        assert result.r_pace_limit_km == 8.0  # lesser of 8km or 10km (5% of 200)

    def test_multiple_violations(self):
        """Multiple quality volume violations should all be captured."""
        result = validate_quality_volume(
            t_pace_km=6.0,      # > 10%
            i_pace_km=6.0,      # > 8%
            r_pace_km=4.0,      # > 5%
            weekly_mileage_km=50.0,
        )

        assert result.overall_ok is False
        assert len(result.violations) == 3
        violation_types = {v.type for v in result.violations}
        assert "T_PACE_VOLUME_EXCEEDED" in violation_types
        assert "I_PACE_VOLUME_EXCEEDED" in violation_types
        assert "R_PACE_VOLUME_EXCEEDED" in violation_types

    def test_beginner_weekly_volume(self):
        """Low weekly volume should still apply percentage constraints."""
        result = validate_quality_volume(
            t_pace_km=1.5,      # 7.5% of weekly
            i_pace_km=1.2,      # 6% of weekly
            r_pace_km=0.8,      # 4% of weekly
            weekly_mileage_km=20.0,
        )

        assert result.overall_ok is True
        assert result.t_pace_limit_km == 2.0  # 10% of 20km
        assert result.i_pace_limit_km == 1.6  # 8% of 20km
        assert result.r_pace_limit_km == 1.0  # 5% of 20km

    def test_zero_quality_volumes_valid(self):
        """Zero quality volumes (easy week) should be valid."""
        result = validate_quality_volume(
            t_pace_km=0.0,
            i_pace_km=0.0,
            r_pace_km=0.0,
            weekly_mileage_km=30.0,
        )

        assert result.overall_ok is True
        assert len(result.violations) == 0


# ============================================================
# WEEKLY PROGRESSION VALIDATION TESTS
# ============================================================


class TestWeeklyProgressionValidation:
    """Tests for weekly volume progression (10% rule)."""

    def test_safe_10_percent_increase(self):
        """Exactly 10% increase should be safe."""
        result = validate_weekly_progression(
            previous_volume_km=40.0,
            current_volume_km=44.0,  # +10%
        )

        assert result.ok is True
        assert result.increase_pct == 10.0
        assert result.safe_max_km == 44.0
        assert result.violation is None

    def test_safe_5_percent_increase(self):
        """Conservative <10% increase should be safe."""
        result = validate_weekly_progression(
            previous_volume_km=40.0,
            current_volume_km=42.0,  # +5%
        )

        assert result.ok is True
        assert result.increase_pct == 5.0

    def test_volume_decrease_is_safe(self):
        """Decreasing volume should always be safe."""
        result = validate_weekly_progression(
            previous_volume_km=50.0,
            current_volume_km=30.0,  # -40%
        )

        assert result.ok is True
        assert result.increase_km < 0
        assert result.violation is None

    def test_same_volume_is_safe(self):
        """Maintaining same volume should be safe."""
        result = validate_weekly_progression(
            previous_volume_km=40.0,
            current_volume_km=40.0,  # 0% change
        )

        assert result.ok is True
        assert result.increase_pct == 0.0

    def test_15_percent_increase_unsafe(self):
        """15% increase should violate 10% rule."""
        result = validate_weekly_progression(
            previous_volume_km=40.0,
            current_volume_km=46.0,  # +15%
        )

        assert result.ok is False
        assert result.increase_pct == 15.0
        assert result.violation is not None
        assert "15%" in result.violation

    def test_25_percent_increase_unsafe(self):
        """Aggressive 25% increase should clearly violate."""
        result = validate_weekly_progression(
            previous_volume_km=40.0,
            current_volume_km=50.0,  # +25%
        )

        assert result.ok is False
        assert result.increase_pct == 25.0
        assert result.recommendation is not None

    def test_from_zero_volume_first_week(self):
        """First week of training (from 0 volume) should be safe."""
        result = validate_weekly_progression(
            previous_volume_km=0.0,
            current_volume_km=20.0,
        )

        # No percentage calculation possible from 0, but should be safe
        assert result.ok is True

    def test_very_low_volume_increase(self):
        """Small absolute increases on low volume should be safe."""
        result = validate_weekly_progression(
            previous_volume_km=10.0,
            current_volume_km=11.0,  # +10%
        )

        assert result.ok is True


# ============================================================
# WEEKLY VOLUME FEASIBILITY TESTS
# ============================================================


class TestWeeklyVolumeFeasibility:
    """Tests for weekly volume feasibility vs. max session duration."""

    def test_target_at_limit_is_ok(self):
        """Target equal to feasible max should be valid."""
        result = validate_weekly_volume_feasibility(
            run_days_per_week=2,
            max_time_per_session_minutes=90,
            easy_pace_min_per_km=6.0,
            target_volume_km=30.0,
        )

        assert result.overall_ok is True
        assert result.max_weekly_volume_km == 30.0
        assert len(result.violations) == 0

    def test_target_over_limit_is_violation(self):
        """Target above feasible max should create a violation."""
        result = validate_weekly_volume_feasibility(
            run_days_per_week=2,
            max_time_per_session_minutes=90,
            easy_pace_min_per_km=6.0,
            target_volume_km=31.0,
        )

        assert result.overall_ok is False
        assert len(result.violations) == 1
        assert result.violations[0].type == "WEEKLY_VOLUME_EXCEEDS_MAX_SESSION_FEASIBILITY"

    def test_invalid_inputs_raise(self):
        """Invalid inputs should raise ValueError."""
        with pytest.raises(ValueError):
            validate_weekly_volume_feasibility(
                run_days_per_week=0,
                max_time_per_session_minutes=90,
                easy_pace_min_per_km=6.0,
            )


# ============================================================
# LONG RUN VALIDATION TESTS
# ============================================================


class TestLongRunValidation:
    """Tests for long run limits against weekly volume and duration."""

    def test_long_run_within_all_limits(self):
        """Long run within both percentage and duration limits should pass."""
        result = validate_long_run_limits(
            long_run_km=15.0,               # 30% of weekly
            long_run_duration_minutes=120,  # 2 hours
            weekly_volume_km=50.0,
        )

        assert result.overall_ok is True
        assert result.pct_ok is True
        assert result.duration_ok is True
        assert len(result.violations) == 0

    def test_long_run_exceeds_percentage_limit(self):
        """Long run exceeding 30% of weekly volume should create violation."""
        result = validate_long_run_limits(
            long_run_km=18.0,               # 36% of weekly
            long_run_duration_minutes=135,  # 2h 15min (ok)
            weekly_volume_km=50.0,
        )

        assert result.overall_ok is False
        assert result.pct_ok is False
        assert result.duration_ok is True
        assert result.pct_of_weekly == 36.0
        assert len(result.violations) == 1
        assert result.violations[0].type == "LONG_RUN_EXCEEDS_WEEKLY_PCT"

    def test_long_run_exceeds_duration_limit(self):
        """Long run exceeding 150 minutes should create violation."""
        result = validate_long_run_limits(
            long_run_km=15.0,               # 25% of weekly (ok)
            long_run_duration_minutes=165,  # 2h 45min (> 150min)
            weekly_volume_km=60.0,
        )

        assert result.overall_ok is False
        assert result.pct_ok is True
        assert result.duration_ok is False
        assert len(result.violations) == 1
        assert result.violations[0].type == "LONG_RUN_EXCEEDS_DURATION"

    def test_long_run_exceeds_both_limits(self):
        """Long run exceeding both limits should create two violations."""
        result = validate_long_run_limits(
            long_run_km=20.0,               # 40% of weekly (> 30%)
            long_run_duration_minutes=165,  # 2h 45min (> 150min)
            weekly_volume_km=50.0,
        )

        assert result.overall_ok is False
        assert result.pct_ok is False
        assert result.duration_ok is False
        assert len(result.violations) == 2

    def test_custom_percentage_limit(self):
        """Custom percentage limit (25%) should be applied."""
        result = validate_long_run_limits(
            long_run_km=14.0,               # 28% of weekly
            long_run_duration_minutes=120,
            weekly_volume_km=50.0,
            pct_limit=25.0,                 # Custom stricter limit
        )

        assert result.overall_ok is False
        assert result.pct_ok is False
        assert result.pct_limit == 25.0

    def test_custom_duration_limit(self):
        """Custom duration limit (180 min) should be applied."""
        result = validate_long_run_limits(
            long_run_km=15.0,
            long_run_duration_minutes=165,  # 2h 45min
            weekly_volume_km=60.0,
            duration_limit_minutes=180,     # Custom more lenient limit
        )

        assert result.overall_ok is True
        assert result.duration_ok is True
        assert result.duration_limit_minutes == 180

    def test_beginner_weekly_volume(self):
        """Low weekly volume should still apply percentage constraints."""
        result = validate_long_run_limits(
            long_run_km=6.0,                # 30% of weekly
            long_run_duration_minutes=55,   # < 1 hour
            weekly_volume_km=20.0,
        )

        assert result.overall_ok is True
        assert result.pct_of_weekly == 30.0


# ============================================================
# SAFE VOLUME RANGE TESTS
# ============================================================


class TestSafeVolumeRange:
    """Tests for safe weekly volume range calculations based on CTL."""

    def test_beginner_ctl_volume_range(self):
        """CTL <20 should map to beginner range (15-25 km)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=15.0,
            goal_type="fitness",
        )

        assert result.ctl_zone == "beginner"
        assert result.base_volume_range_km == (15, 25)
        assert result.recommended_start_km == 15
        assert result.recommended_peak_km == 25

    def test_recreational_ctl_volume_range(self):
        """CTL 20-35 should map to recreational range (25-40 km)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=28.0,
            goal_type="10k",
        )

        assert result.ctl_zone == "recreational"
        assert result.base_volume_range_km == (25, 40)

    def test_competitive_ctl_volume_range(self):
        """CTL 35-50 should map to competitive range (40-65 km)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=44.0,
            goal_type="half_marathon",
        )

        assert result.ctl_zone == "competitive"
        assert result.base_volume_range_km == (40, 65)

    def test_advanced_ctl_volume_range(self):
        """CTL >50 should map to advanced range (55-80 km)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=58.0,
            goal_type="marathon",
        )

        assert result.ctl_zone == "advanced"
        assert result.base_volume_range_km == (55, 80)

    def test_5k_goal_adjustment(self):
        """5K goal should reduce volume by 10% (0.9 factor)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=30.0,              # recreational
            goal_type="5k",
        )

        # Base: (25, 40), 5K adjustment: (22, 36)
        assert result.goal_adjusted_range_km == (22, 36)

    def test_half_marathon_goal_adjustment(self):
        """Half marathon goal should increase volume by 15% (1.15 factor)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=30.0,              # recreational
            goal_type="half_marathon",
        )

        # Base: (25, 40), half adjustment: (28, 46)
        assert result.goal_adjusted_range_km == (28, 46)

    def test_marathon_goal_adjustment(self):
        """Marathon goal should increase volume by 30% (1.3 factor)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=44.0,              # competitive
            goal_type="marathon",
        )

        # Base: (40, 65), marathon adjustment: (52, 84)
        assert result.goal_adjusted_range_km == (52, 84)

    def test_masters_adjustment_age_50_plus(self):
        """Age 50+ should reduce volume by 10% (0.9 factor)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=30.0,              # recreational
            goal_type="10k",
            athlete_age=52,
        )

        # Base: (25, 40), masters adjustment: (22, 36)
        assert result.masters_adjusted_range_km == (22, 36)
        assert result.recommended_start_km == 22
        assert result.recommended_peak_km == 36

    def test_masters_adjustment_under_50(self):
        """Age <50 should not apply masters adjustment."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=30.0,
            goal_type="10k",
            athlete_age=45,
        )

        # No masters adjustment
        assert result.masters_adjusted_range_km is None
        assert result.recommended_start_km == 25  # Base volume

    def test_combined_goal_and_masters_adjustments(self):
        """Marathon goal + masters age should apply both adjustments."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=44.0,              # competitive: (40, 65)
            goal_type="marathon",          # 1.3x: (52, 84)
            athlete_age=52,                # 0.9x: (46, 75)
        )

        # Final: (46, 75)
        assert result.goal_adjusted_range_km == (52, 84)
        assert result.masters_adjusted_range_km == (46, 75)
        assert result.recommended_start_km == 46
        assert result.recommended_peak_km == 75

    def test_zero_ctl_beginner_range(self):
        """CTL of 0 (complete beginner) should use beginner range."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=0.0,
            goal_type="fitness",
        )

        assert result.ctl_zone == "beginner"
        assert result.recommended_start_km == 15

    def test_fitness_goal_no_adjustment(self):
        """General fitness goal should use base volume (1.0 factor)."""
        result = calculate_safe_volume_range(
            running_priority="primary",
            current_ctl=30.0,
            goal_type="fitness",
        )

        assert result.goal_adjusted_range_km == result.base_volume_range_km

    def test_priority_primary_no_reduction(self):
        """PRIMARY priority should not reduce volume (1.0 multiplier)."""
        result = calculate_safe_volume_range(
            current_ctl=30.0,
            running_priority="primary",
            goal_type="10k",
        )

        # Base: (25, 40), no priority adjustment
        assert result.recommended_start_km == 25
        assert result.recommended_peak_km == 40

    def test_priority_equal_25_percent_reduction(self):
        """EQUAL priority should reduce volume by 25% (0.75 multiplier)."""
        result = calculate_safe_volume_range(
            current_ctl=30.0,
            running_priority="equal",
            goal_type="10k",
        )

        # Base: (25, 40), equal priority: (18, 30)
        assert result.recommended_start_km == 18
        assert result.recommended_peak_km == 30
        assert "25% volume reduction" in result.recommendation
        assert "EQUAL" in result.recommendation

    def test_priority_secondary_50_percent_reduction(self):
        """SECONDARY priority should reduce volume by 50% (0.50 multiplier)."""
        result = calculate_safe_volume_range(
            current_ctl=30.0,
            running_priority="secondary",
            goal_type="10k",
        )

        # Base: (25, 40), secondary priority: (12, 20)
        assert result.recommended_start_km == 12
        assert result.recommended_peak_km == 20
        assert "50% volume reduction" in result.recommendation
        assert "SECONDARY" in result.recommendation

    def test_priority_with_masters_stacking(self):
        """Priority and masters adjustments should stack correctly."""
        result = calculate_safe_volume_range(
            current_ctl=44.0,              # competitive: (40, 65)
            running_priority="equal",
            goal_type="half_marathon",     # 1.15x: (46, 74)
            athlete_age=52,                # 0.9x: (41, 66)
                                           # 0.75x: (30, 49)
        )

        # Final: equal priority on top of masters
        assert result.recommended_start_km == 30
        assert result.recommended_peak_km == 49

    def test_invalid_priority_raises_error(self):
        """Invalid priority value should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid running_priority"):
            calculate_safe_volume_range(
                current_ctl=30.0,
                running_priority="high",  # Invalid
                goal_type="10k",
            )


# ============================================================
# PROGRESSION CONTEXT ANALYSIS TESTS
# ============================================================


class TestProgressionContextAnalysis:
    """
    Tests for rich progression context analysis (AI coaching support).

    These tests verify that the function provides CONTEXT, not decisions.
    Tests focus on correct classification, analysis, and context provision.
    """

    # ============================================================
    # 1. VOLUME CLASSIFICATION TESTS (3 tests)
    # ============================================================

    def test_low_volume_classification(self):
        """Volume < 25km should be classified as low volume."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
        )

        assert context.volume_context.category == "low"
        assert context.volume_context.threshold_km == "<25km"
        assert context.volume_context.injury_risk_factor == "absolute_load"
        assert "absolute load per session" in context.volume_context.description

    def test_medium_volume_classification(self):
        """Volume 25-50km should be classified as medium volume."""
        context = analyze_weekly_progression_context(
            previous_volume_km=30.0,
            current_volume_km=35.0,
        )

        assert context.volume_context.category == "medium"
        assert context.volume_context.threshold_km == "25-50km"
        assert context.volume_context.injury_risk_factor == "both"
        assert "both absolute and cumulative" in context.volume_context.description

    def test_high_volume_classification(self):
        """Volume ≥50km should be classified as high volume."""
        context = analyze_weekly_progression_context(
            previous_volume_km=60.0,
            current_volume_km=75.0,
        )

        assert context.volume_context.category == "high"
        assert context.volume_context.threshold_km == "≥50km"
        assert context.volume_context.injury_risk_factor == "cumulative_load"
        assert "cumulative load" in context.volume_context.description

    # ============================================================
    # 2. ABSOLUTE LOAD ANALYSIS TESTS (3 tests)
    # ============================================================

    def test_absolute_load_with_run_days(self):
        """When run_days provided, should calculate per-session increase."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
            run_days_per_week=4,
        )

        assert context.absolute_load_analysis.per_session_increase_km == 1.25  # 5km / 4 days
        assert context.absolute_load_analysis.within_pfitzinger_guideline is True
        assert "1.25km/session" in context.absolute_load_analysis.assessment

    def test_absolute_load_without_run_days(self):
        """When run_days not provided, should skip per-session analysis."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
        )

        assert context.absolute_load_analysis.per_session_increase_km is None
        assert context.absolute_load_analysis.within_pfitzinger_guideline is None
        assert "run days not provided" in context.absolute_load_analysis.assessment

    def test_absolute_load_exceeds_pfitzinger(self):
        """Per-session increase >1.6km should be flagged."""
        context = analyze_weekly_progression_context(
            previous_volume_km=60.0,
            current_volume_km=75.0,
            run_days_per_week=4,
        )

        assert context.absolute_load_analysis.per_session_increase_km == 3.75  # 15km / 4 days
        assert context.absolute_load_analysis.within_pfitzinger_guideline is False
        assert "Exceeds Pfitzinger guideline" in context.absolute_load_analysis.assessment

    # ============================================================
    # 3. CTL CAPACITY CONTEXT TESTS (3 tests)
    # ============================================================

    def test_ctl_capacity_within_range(self):
        """Target volume within CTL capacity should be flagged."""
        context = analyze_weekly_progression_context(
            previous_volume_km=25.0,
            current_volume_km=30.0,  # Within recreational range (25-40km)
            current_ctl=27.0,  # Recreational zone (25-40km capacity)
        )

        assert context.athlete_context.ctl == 27.0
        assert context.athlete_context.ctl_zone == "recreational"
        assert context.athlete_context.ctl_based_capacity_km == (25, 40)
        assert context.athlete_context.target_within_capacity is True

    def test_ctl_capacity_outside_range(self):
        """Target volume outside CTL capacity should be flagged."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=50.0,  # Above recreational capacity
            current_ctl=27.0,  # Recreational zone (25-40km capacity)
        )

        assert context.athlete_context.ctl_zone == "recreational"
        assert context.athlete_context.target_within_capacity is False

    def test_no_ctl_provided(self):
        """When CTL not provided, capacity analysis should be skipped."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
        )

        assert context.athlete_context.ctl is None
        assert context.athlete_context.ctl_zone is None
        assert context.athlete_context.ctl_based_capacity_km is None
        assert context.athlete_context.target_within_capacity is None

    # ============================================================
    # 4. RISK FACTOR DETECTION TESTS (3 tests)
    # ============================================================

    def test_recent_injury_risk_factor(self):
        """Recent injury should be flagged as risk factor."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
            recent_injury=True,
        )

        risk_factors = [rf.factor for rf in context.risk_factors]
        assert any("Recent injury" in rf for rf in risk_factors)

        injury_risk = next(rf for rf in context.risk_factors if "Recent injury" in rf.factor)
        assert injury_risk.severity == "moderate"
        assert "Monitor discomfort" in injury_risk.recommendation

    def test_masters_athlete_risk_factor(self):
        """Masters athlete should be flagged as risk factor."""
        context = analyze_weekly_progression_context(
            previous_volume_km=40.0,
            current_volume_km=46.0,
            athlete_age=52,
        )

        risk_factors = [rf.factor for rf in context.risk_factors]
        assert any("Masters athlete" in rf for rf in risk_factors)

        masters_risk = next(rf for rf in context.risk_factors if "Masters athlete" in rf.factor)
        assert masters_risk.severity == "low"  # Age 52 is < 60
        assert "longer recovery" in masters_risk.recommendation

    def test_large_percentage_increase_risk_factor(self):
        """Large percentage increase (>20%) should be flagged."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,  # 33% increase
        )

        risk_factors = [rf.factor for rf in context.risk_factors]
        assert any("Large percentage increase" in rf for rf in risk_factors)

        pct_risk = next(rf for rf in context.risk_factors if "Large percentage" in rf.factor)
        assert pct_risk.severity in ["moderate", "high"]

    # ============================================================
    # 5. PROTECTIVE FACTOR DETECTION TESTS (2 tests)
    # ============================================================

    def test_low_volume_small_increase_protective(self):
        """Low volume + small absolute increase should be protective factor."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,  # 5km increase, < 10km threshold
        )

        protective_factors = [pf.factor for pf in context.protective_factors]
        assert any("Low volume level with small absolute increase" in pf for pf in protective_factors)

    def test_adequate_ctl_capacity_protective(self):
        """Target within CTL capacity should be protective factor."""
        context = analyze_weekly_progression_context(
            previous_volume_km=25.0,
            current_volume_km=30.0,  # Within recreational range (25-40km)
            current_ctl=27.0,  # Recreational (25-40km capacity)
        )

        protective_factors = [pf.factor for pf in context.protective_factors]
        assert any("Target volume within CTL capacity" in pf for pf in protective_factors)

        ctl_protective = next(
            pf for pf in context.protective_factors if "CTL capacity" in pf.factor
        )
        assert "25-40km" in ctl_protective.note

    # ============================================================
    # 6. COACHING CONSIDERATIONS TESTS (2 tests)
    # ============================================================

    def test_low_volume_coaching_considerations(self):
        """Low volume should include Pfitzinger absolute load guidance."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
        )

        considerations = context.coaching_considerations
        assert any("flexible percentage increases" in c for c in considerations)
        assert any("1.6km per session" in c for c in considerations)

    def test_high_volume_coaching_considerations(self):
        """High volume should emphasize 10% rule and cumulative load."""
        context = analyze_weekly_progression_context(
            previous_volume_km=60.0,
            current_volume_km=75.0,
        )

        considerations = context.coaching_considerations
        assert any("10% rule" in c for c in considerations)
        assert any("cumulative load" in c for c in considerations)

    # ============================================================
    # 7. TRADITIONAL 10% RULE REFERENCE TEST
    # ============================================================

    def test_traditional_10_pct_rule_reference(self):
        """Traditional 10% rule should be provided for reference."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
        )

        assert context.traditional_10pct_rule["safe_max_km"] == 16.5  # 15 * 1.10
        assert context.traditional_10pct_rule["exceeds_by_pct"] > 0
        assert "Traditional rule" in context.traditional_10pct_rule["note"]

    # ============================================================
    # 8. METHODOLOGY REFERENCES TEST
    # ============================================================

    def test_methodology_references_provided(self):
        """Should provide links to training methodology resources."""
        context = analyze_weekly_progression_context(
            previous_volume_km=15.0,
            current_volume_km=20.0,
        )

        assert len(context.methodology_references) > 0
        assert any("pfitzinger" in ref.lower() for ref in context.methodology_references)
        assert any("methodology.md" in ref for ref in context.methodology_references)
