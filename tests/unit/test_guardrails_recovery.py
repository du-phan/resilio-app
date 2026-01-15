"""
Unit tests for guardrails recovery planning module.

Tests recovery protocols based on Daniels' Table 9.2 and Pfitzinger's guidelines:
- Break return planning
- Masters recovery adjustments
- Race recovery protocols
- Illness recovery planning
"""

import pytest
from sports_coach_engine.core.guardrails.recovery import (
    calculate_break_return_plan,
    calculate_masters_recovery,
    calculate_race_recovery,
    generate_illness_recovery_plan,
)
from sports_coach_engine.schemas.guardrails import IllnessSeverity


# ============================================================
# BREAK RETURN PLAN TESTS
# ============================================================


class TestBreakReturnPlan:
    """Tests for return-to-training after breaks (Daniels Table 9.2)."""

    def test_short_break_5_days_or_less(self):
        """Break ≤5 days should require minimal adjustment."""
        result = calculate_break_return_plan(
            break_days=3,
            pre_break_ctl=44.0,
            cross_training_level="none",
        )

        assert result.load_phase_1_pct == 100  # Full load immediately
        assert result.vdot_adjustment_pct == 100  # No VDOT reduction
        assert result.estimated_full_return_weeks == 1  # One week monitoring period

    def test_medium_break_6_to_28_days_no_cross_training(self):
        """Break 6-28 days without cross-training should use 2-phase return."""
        result = calculate_break_return_plan(
            break_days=21,
            pre_break_ctl=44.0,
            cross_training_level="none",
        )

        assert result.load_phase_1_pct == 50   # 50% load first half
        assert result.load_phase_2_pct == 75   # 75% load second half
        assert 93 <= result.vdot_adjustment_pct <= 99  # VDOT reduction
        assert result.estimated_full_return_weeks == 4  # ~4 weeks return

    def test_medium_break_with_light_cross_training(self):
        """Light cross-training should improve VDOT retention."""
        result_none = calculate_break_return_plan(
            break_days=14,
            pre_break_ctl=44.0,
            cross_training_level="none",
        )

        result_light = calculate_break_return_plan(
            break_days=14,
            pre_break_ctl=44.0,
            cross_training_level="light",
        )

        # Light cross-training should retain more VDOT
        assert result_light.vdot_adjustment_pct >= result_none.vdot_adjustment_pct

    def test_medium_break_with_moderate_cross_training(self):
        """Moderate cross-training should significantly improve retention."""
        result = calculate_break_return_plan(
            break_days=21,
            pre_break_ctl=44.0,
            cross_training_level="moderate",
        )

        # Moderate cross-training: better VDOT retention than light
        assert result.vdot_adjustment_pct >= 97  # ~97-99%

    def test_medium_break_with_heavy_cross_training(self):
        """Heavy cross-training should maximize VDOT retention."""
        result = calculate_break_return_plan(
            break_days=21,
            pre_break_ctl=44.0,
            cross_training_level="heavy",
        )

        # Heavy cross-training: near-full VDOT retention
        assert result.vdot_adjustment_pct >= 99

    def test_long_break_8_plus_weeks(self):
        """Break >8 weeks should use multi-week structured return."""
        result = calculate_break_return_plan(
            break_days=70,  # 10 weeks
            pre_break_ctl=44.0,
            cross_training_level="none",
        )

        # Significant VDOT reduction
        assert 80 <= result.vdot_adjustment_pct <= 92
        # Longer return period
        assert result.estimated_full_return_weeks >= 6

    def test_return_schedule_structure(self):
        """Return schedule should have proper structure."""
        result = calculate_break_return_plan(
            break_days=21,
            pre_break_ctl=44.0,
            cross_training_level="moderate",
        )

        # Should have week-by-week schedule
        assert len(result.return_schedule) > 0
        # First week should be conservative
        first_week = result.return_schedule[0]
        assert first_week.week_number == 1
        assert first_week.load_pct <= 75

    def test_red_flags_included(self):
        """Return plan should include red flags to monitor."""
        result = calculate_break_return_plan(
            break_days=14,
            pre_break_ctl=44.0,
            cross_training_level="none",
        )

        assert len(result.red_flags) > 0
        # Should mention monitoring for issues
        red_flags_text = " ".join(result.red_flags).lower()
        assert "soreness" in red_flags_text or "fatigue" in red_flags_text

    def test_higher_ctl_athlete(self):
        """Higher CTL athlete should follow same return protocol."""
        result = calculate_break_return_plan(
            break_days=21,
            pre_break_ctl=65.0,  # Advanced athlete
            cross_training_level="none",
        )

        # Protocol based on break duration, not CTL
        assert result.load_phase_1_pct == 50
        assert result.load_phase_2_pct == 75


# ============================================================
# MASTERS RECOVERY TESTS
# ============================================================


class TestMastersRecovery:
    """Tests for age-specific recovery adjustments (Pfitzinger)."""

    def test_young_athlete_base_recovery(self):
        """Athletes 18-35 should have base recovery (no adjustment)."""
        result = calculate_masters_recovery(
            age=28,
            workout_type="vo2max",
        )

        assert result.age_bracket == "18-35"
        # Base recovery, no additional days
        assert result.adjustments["vo2max"] == 0
        assert result.recommended_recovery_days["vo2max"] == 1  # 1 base day

    def test_masters_36_to_45_small_adjustment(self):
        """Masters 36-45 should have small adjustments (+0-1 day)."""
        result = calculate_masters_recovery(
            age=42,
            workout_type="vo2max",
        )

        assert result.age_bracket == "36-45"
        # Should have minimal adjustment
        assert 0 <= result.adjustments["vo2max"] <= 1

    def test_masters_46_to_55_moderate_adjustment(self):
        """Masters 46-55 should have moderate adjustments (+1-2 days)."""
        result = calculate_masters_recovery(
            age=52,
            workout_type="vo2max",
        )

        assert result.age_bracket == "46-55"
        # VO2max hardest, should require more recovery
        assert result.adjustments["vo2max"] == 2
        assert result.recommended_recovery_days["vo2max"] == 3  # 1 base + 2

    def test_masters_56_plus_significant_adjustment(self):
        """Masters 56+ should have significant adjustments (+2-3 days)."""
        result = calculate_masters_recovery(
            age=62,
            workout_type="vo2max",
        )

        assert result.age_bracket == "56+"
        # Significant additional recovery needed
        assert result.adjustments["vo2max"] >= 2

    def test_vo2max_workout_most_demanding(self):
        """VO2max workouts should require most recovery."""
        result_vo2 = calculate_masters_recovery(age=52, workout_type="vo2max")
        result_tempo = calculate_masters_recovery(age=52, workout_type="tempo")
        result_long = calculate_masters_recovery(age=52, workout_type="long_run")

        # VO2max should have longest recovery
        assert result_vo2.adjustments["vo2max"] >= result_tempo.adjustments["tempo"]
        assert result_vo2.adjustments["vo2max"] >= result_long.adjustments["long_run"]

    def test_tempo_workout_moderate_recovery(self):
        """Tempo workouts should require moderate recovery."""
        result = calculate_masters_recovery(
            age=52,
            workout_type="tempo",
        )

        # Tempo less demanding than VO2max
        assert result.adjustments["tempo"] < result.adjustments["vo2max"]

    def test_long_run_recovery(self):
        """Long runs should require adequate recovery."""
        result = calculate_masters_recovery(
            age=52,
            workout_type="long_run",
        )

        # Long run recovery similar to tempo
        assert result.adjustments["long_run"] >= 1

    def test_race_recovery(self):
        """Races should require significant recovery."""
        result = calculate_masters_recovery(
            age=52,
            workout_type="race",
        )

        # Race should require substantial recovery
        assert result.adjustments["race"] >= 2


# ============================================================
# RACE RECOVERY TESTS
# ============================================================


class TestRaceRecovery:
    """Tests for post-race recovery protocols."""

    def test_5k_recovery_young_athlete(self):
        """5K recovery for young athlete should be 4-7 days."""
        result = calculate_race_recovery(
            race_distance="5k",
            athlete_age=28,
            finishing_effort="hard",
        )

        assert result.race_distance == "5k"
        assert 4 <= result.minimum_recovery_days <= 7
        assert result.quality_work_resume_day >= result.minimum_recovery_days

    def test_10k_recovery_young_athlete(self):
        """10K recovery should be 6-10 days."""
        result = calculate_race_recovery(
            race_distance="10k",
            athlete_age=28,
            finishing_effort="hard",
        )

        assert 6 <= result.minimum_recovery_days <= 10

    def test_half_marathon_recovery_young_athlete(self):
        """Half marathon recovery should be 7-14 days."""
        result = calculate_race_recovery(
            race_distance="half_marathon",
            athlete_age=28,
            finishing_effort="hard",
        )

        assert 7 <= result.minimum_recovery_days <= 14

    def test_marathon_recovery_young_athlete(self):
        """Marathon recovery should be 14-28 days."""
        result = calculate_race_recovery(
            race_distance="marathon",
            athlete_age=28,
            finishing_effort="hard",
        )

        assert 14 <= result.minimum_recovery_days <= 28

    def test_masters_athlete_longer_recovery(self):
        """Masters athletes should need longer recovery than young athletes."""
        young_result = calculate_race_recovery(
            race_distance="half_marathon",
            athlete_age=28,
            finishing_effort="hard",
        )

        masters_result = calculate_race_recovery(
            race_distance="half_marathon",
            athlete_age=52,
            finishing_effort="hard",
        )

        # Masters should need more recovery
        assert masters_result.minimum_recovery_days >= young_result.minimum_recovery_days

    def test_easy_effort_shorter_recovery(self):
        """Easy effort should require less recovery than hard effort."""
        hard_result = calculate_race_recovery(
            race_distance="10k",
            athlete_age=28,
            finishing_effort="hard",
        )

        easy_result = calculate_race_recovery(
            race_distance="10k",
            athlete_age=28,
            finishing_effort="easy",
        )

        # Easy effort should recover faster
        assert easy_result.recommended_recovery_days <= hard_result.recommended_recovery_days

    def test_max_effort_longest_recovery(self):
        """Max effort should require longest recovery."""
        max_result = calculate_race_recovery(
            race_distance="10k",
            athlete_age=28,
            finishing_effort="max",
        )

        moderate_result = calculate_race_recovery(
            race_distance="10k",
            athlete_age=28,
            finishing_effort="moderate",
        )

        # Max effort needs more recovery
        assert max_result.recommended_recovery_days >= moderate_result.recommended_recovery_days

    def test_recovery_schedule_provided(self):
        """Recovery plan should include day-by-day schedule."""
        result = calculate_race_recovery(
            race_distance="half_marathon",
            athlete_age=52,
            finishing_effort="hard",
        )

        assert len(result.recovery_schedule) > 0
        # Should cover immediate post-race period
        assert len(result.recovery_schedule) >= 3

    def test_red_flags_included(self):
        """Recovery plan should include warning signs."""
        result = calculate_race_recovery(
            race_distance="marathon",
            athlete_age=52,
            finishing_effort="hard",
        )

        assert len(result.red_flags) > 0


# ============================================================
# ILLNESS RECOVERY TESTS
# ============================================================


class TestIllnessRecovery:
    """Tests for illness recovery planning."""

    def test_mild_illness_short_duration(self):
        """Mild illness (1-3 days) should have quick return."""
        result = generate_illness_recovery_plan(
            illness_duration_days=2,
            severity=IllnessSeverity.MILD,
        )

        assert result.severity == IllnessSeverity.MILD
        assert result.estimated_ctl_drop <= 5.0  # Minimal fitness loss
        assert result.full_training_resume_day <= 7  # Quick return

    def test_moderate_illness_medium_duration(self):
        """Moderate illness (4-7 days) should have structured return."""
        result = generate_illness_recovery_plan(
            illness_duration_days=5,
            severity=IllnessSeverity.MODERATE,
        )

        assert result.severity == IllnessSeverity.MODERATE
        assert 5.0 <= result.estimated_ctl_drop <= 15.0  # Moderate fitness loss
        assert 7 <= result.full_training_resume_day <= 21  # Conservative return

    def test_severe_illness_long_duration(self):
        """Severe illness (8+ days) should have extended return."""
        result = generate_illness_recovery_plan(
            illness_duration_days=10,
            severity=IllnessSeverity.SEVERE,
        )

        assert result.severity == IllnessSeverity.SEVERE
        assert result.estimated_ctl_drop >= 15.0  # Significant fitness loss
        assert result.full_training_resume_day >= 21  # Long return period

    def test_return_protocol_structure(self):
        """Return protocol should have day-by-day activities."""
        result = generate_illness_recovery_plan(
            illness_duration_days=5,
            severity=IllnessSeverity.MODERATE,
        )

        assert len(result.return_protocol) > 0
        # First activities should be very easy
        first_day = result.return_protocol[0]
        assert first_day.day_number == 1
        # Should have low intensity
        if first_day.rpe_max:
            assert first_day.rpe_max <= 4

    def test_red_flags_health_monitoring(self):
        """Recovery plan should include health red flags."""
        result = generate_illness_recovery_plan(
            illness_duration_days=5,
            severity=IllnessSeverity.MODERATE,
        )

        assert len(result.red_flags) > 0
        # Should mention HR or symptoms
        red_flags_text = " ".join(result.red_flags).lower()
        assert "hr" in red_flags_text or "heart" in red_flags_text or "fatigue" in red_flags_text

    def test_medical_consultation_triggers(self):
        """Recovery plan should include when to seek medical advice."""
        result = generate_illness_recovery_plan(
            illness_duration_days=5,
            severity=IllnessSeverity.MODERATE,
        )

        assert len(result.medical_consultation_triggers) > 0

    def test_longer_illness_more_ctl_drop(self):
        """Longer illness should cause more CTL drop."""
        short_illness = generate_illness_recovery_plan(
            illness_duration_days=3,
            severity=IllnessSeverity.MILD,
        )

        long_illness = generate_illness_recovery_plan(
            illness_duration_days=10,
            severity=IllnessSeverity.SEVERE,
        )

        assert long_illness.estimated_ctl_drop > short_illness.estimated_ctl_drop

    def test_severe_illness_conservative_return(self):
        """Severe illness should have very conservative return."""
        result = generate_illness_recovery_plan(
            illness_duration_days=8,
            severity=IllnessSeverity.SEVERE,
        )

        # Should take 3-4 weeks to resume full training
        assert result.full_training_resume_day >= 21

    def test_mild_illness_quick_return(self):
        """Mild illness should allow relatively quick return."""
        result = generate_illness_recovery_plan(
            illness_duration_days=2,
            severity=IllnessSeverity.MILD,
        )

        # Should resume within a week
        assert result.full_training_resume_day <= 7

    def test_return_protocol_gradual_progression(self):
        """Return protocol should show gradual load increase."""
        result = generate_illness_recovery_plan(
            illness_duration_days=5,
            severity=IllnessSeverity.MODERATE,
        )

        # Activities should progress from easy to normal
        if len(result.return_protocol) >= 2:
            # Later activities should have higher load than early ones
            early_activity = result.return_protocol[0]
            late_activity = result.return_protocol[-1]

            # Compare load if both have load_au
            if early_activity.load_au and late_activity.load_au:
                assert late_activity.load_au >= early_activity.load_au
